import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Thai month mapping
THAI_MONTHS: Dict[str, str] = {
    "มกราคม": "01", "กุมภาพันธ์": "02", "มีนาคม": "03", "เมษายน": "04",
    "พฤษภาคม": "05", "มิถุนายน": "06", "กรกฎาคม": "07", "สิงหาคม": "08",
    "กันยายน": "09", "ตุลาคม": "10", "พฤศจิกายน": "11", "ธันวาคม": "12"
}

# Currency symbol mapping
CURRENCY_SYMBOLS: Dict[str, str] = {
    'THB': 'THB', '฿': 'THB',
    'USD': 'USD', '$': 'USD',
    'EUR': 'EUR', '€': 'EUR',
}

NUMERIC_FIELDS: List[str] = [
    "quantity", "unit_price", "discount", "amount",
    "subtotal_amount", "total_discount", "vat_amount", "total_amount"
]

# Helper to trim whitespace from all strings in a dict
def trim_strings(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: trim_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [trim_strings(i) for i in obj]
    elif isinstance(obj, str):
        return obj.strip()
    else:
        return obj

def normalize_date(value: str) -> Optional[str]:
    value = value.strip()
    if value == "":
        return None
    # Try standard formats first
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
        
    m = re.match(r"(\d{1,2})\s+([ก-๙]+)\s+(\d{4})", value)
    if m:
        day, thai_month, year = m.groups()
        month = THAI_MONTHS.get(thai_month)
        year = int(year)
        if year > 2500:
            year -= 543
        return f"{year:04d}-{month}-{int(day):02d}"
    return value

def extract_currency(value: str) -> Optional[str]:
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in value:
            return code
    return None

def normalize_numeric(value: str) -> Tuple[Optional[float], Optional[str]]:
    value = value.strip()
    if value == "":
        return None, None
    m = re.match(r"([\d,\.]+)\s*([A-Za-zก-๙$€฿]*)", value)
    if m:
        num, currency = m.groups()
        num = num.replace(",", "")
        currency_code = CURRENCY_SYMBOLS.get(currency, currency) if currency else None
        try:
            num = float(num)
        except Exception:
            num = None
        return num, currency_code
    try:
        return float(value), None
    except Exception:
        return None, None

def normalize_line_items(line_items: List[Dict[str, Any]], currency_holder: List[Optional[str]]) -> List[Dict[str, Any]]:
    normalized_items: List[Dict[str, Any]] = []
    for item in line_items:
        norm_item: Dict[str, Any] = {}
        for k, v in item.items():
            if v is None or (isinstance(v, str) and v.strip() == ""):
                norm_item[k] = None
                continue
            if k in NUMERIC_FIELDS:
                num, currency = normalize_numeric(str(v))
                norm_item[k] = num
                if currency and not currency_holder[0]:
                    currency_holder[0] = currency
            else:
                norm_item[k] = v.strip() if isinstance(v, str) else v
        normalized_items.append(norm_item)
    return normalized_items

def normalize(data: Dict[str, Any], key: Optional[str] = None) -> Dict[str, Any]:
    def normalize_single_value(key: str, value: Any, normalized_data: Optional[Dict[str, Any]] = None, currency_holder: Optional[List[Optional[str]]] = None) -> Any:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        if key in NUMERIC_FIELDS:
            num, currency = normalize_numeric(str(value))
            if currency and currency_holder is not None and not currency_holder[0]:
                currency_holder[0] = currency
            return num
        if key and "date" in key.lower():
            return normalize_date(str(value))
        return value.strip() if isinstance(value, str) else value

    if key is not None:
        return normalize_single_value(key, data, {}, [None])

    normalized_data: Dict[str, Any] = {}
    currency_holder: List[Optional[str]] = [None]
    data = trim_strings(data)
    for k, v in data.items():
        if k == "item_details" and isinstance(v, list):
            normalized_data[k] = normalize_line_items(v, currency_holder)
        else:
            normalized_data[k] = normalize_single_value(k, v, normalized_data, currency_holder)

    # Recalculate subtotal_amount from item_details if present
    if "item_details" in normalized_data and isinstance(normalized_data["item_details"], list):
        def safe_float(val: Any) -> float:
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0
        subtotal = sum(safe_float(item.get("amount", 0)) for item in normalized_data["item_details"] if item.get("amount") is not None)
        normalized_data["subtotal_amount"] = subtotal
        # If vat_amount exists, recalc total_amount
        tax = normalized_data.get("vat_amount")
        if tax is not None:
            try:
                normalized_data["total_amount"] = subtotal + float(tax)
            except Exception:
                pass

    if not normalized_data.get("currency") and currency_holder[0]:
        normalized_data["currency"] = currency_holder[0]

    # Enrichment: infer currency if missing
    if not normalized_data.get("currency"):
        vendor = None
        if "vendor_information" in normalized_data and isinstance(normalized_data["vendor_information"], dict):
            vendor = normalized_data["vendor_information"].get("name", "")
        elif "vendor_name" in normalized_data:
            vendor = normalized_data["vendor_name"]
        if vendor and ("ไทย" in vendor or "บริษัท" in vendor):
            normalized_data["currency"] = "THB"

    return normalized_data

# === Compare raw input with normalized ===
def compare_after_normalization(raw_json: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    normalized = normalize(raw_json)
    diffs: Dict[str, Any] = {}
    for key in raw_json.keys():
        raw_val = raw_json[key]
        norm_val = normalized.get(key)
        if normalize(raw_val, key) != norm_val:
            diffs[key] = {
                "raw": raw_val,
                "normalized": norm_val
            }
    return normalized, diffs

# === Process all JSON files in a folder ===
def process_json_folder(folder_path: str) -> None:
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    raw_json = json.load(f)
                except json.JSONDecodeError:
                    print(f"Skipping invalid JSON: {filename}")
                    continue

                normalized, diff = compare_after_normalization(raw_json)

                # Add 'ensure_ascii=False' to make Thai word readable in Terminal
                print(f"\nFile: {filename}")
                print("Raw JSON:")
                print(json.dumps(raw_json, indent=2, ensure_ascii=False))

                print("\nNormalized JSON:")
                print(json.dumps(normalized, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    folder_path = (r"C:\Users\wasin.j\Desktop\data_normalize-validate\sample-normalize")  # replace with folder path
    process_json_folder(folder_path)