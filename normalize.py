import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

MONTHS = {
    "มกราคม": "01", "กุมภาพันธ์": "02", "มีนาคม": "03", "เมษายน": "04",
    "พฤษภาคม": "05", "มิถุนายน": "06", "กรกฎาคม": "07", "สิงหาคม": "08",
    "กันยายน": "09", "ตุลาคม": "10", "พฤศจิกายน": "11", "ธันวาคม": "12",
    "ม.ค.": "01", "ก.พ.": "02", "มี.ค.": "03", "เม.ย.": "04",
    "พ.ค.": "05", "มิ.ย.": "06", "ก.ค.": "07", "ส.ค.": "08",
    "ก.ย.": "09", "ต.ค.": "10", "พ.ย.": "11", "ธ.ค.": "12",
}

CURRENCY_SYMBOL = {
    'THB': 'THB', '฿': 'THB', 'บาท': 'THB'
}

INVOICE_NUM_FIELDS = [
    "quantity", "unit_price", "discount", "amount",
    "subtotal_amount", "total_discount", "vat_amount", "total_amount"
]

INVOICE_DATE_FIELDS = [
    "invoice_date", "due_date"
]

EXPENSE_NUM_FIELDS = [
    "quantity", "amount", "subtotal_amount", "vat_amount", "total_amount"
]

EXPENSE_DATE_FIELDS = [
    "report_date", "period_start", "period_end"
]

# --- Utility Functions ---

def trim_strings(obj: Any) -> Any:
    """Recursively trims whitespace from strings in dicts/lists."""
    if isinstance(obj, dict):
        return {k: trim_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [trim_strings(i) for i in obj]
    elif isinstance(obj, str):
        return obj.strip()
    return obj

def normalize_date(value: str) -> Optional[str]:
    """Normalizes date strings to YYYY-MM-DD format, supports Thai months."""
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    m = re.match(r"(\d{1,2})\s+([ก-๙\.]+)\s+(\d{4})", value)
    if m:
        day, thai_month, year = m.groups()
        month = MONTHS.get(thai_month)
        year = int(year)
        if year > 2500:
            year -= 543
        if month:
            return f"{year:04d}-{month}-{int(day):02d}"
    return value

def set_null(data: Dict[str, Any], optional_fields: List[str]) -> None:
    """Sets empty string or None fields to None for given keys."""
    for field in optional_fields:
        if field in data and (data[field] == "" or data[field] is None):
            data[field] = None

def normalize_numeric(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """Extracts numeric value and currency code from a string."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    value = str(value).strip()
    if not value:
        return None, None
    m = re.match(r"([\d,\.]+)\s*([A-Za-zก-๙$€฿]*)", value)
    if m:
        num, currency = m.groups()
        num = num.replace(",", "")
        currency_code = CURRENCY_SYMBOL.get(currency, currency) if currency else None
        try:
            num = float(num)
        except Exception:
            num = None
        return num, currency_code
    try:
        return float(value), None
    except Exception:
        return None, None

# --- Normalization Functions ---

def normalize_invoice_item(item: Dict[str, Any], currency_holder: List[Optional[str]]) -> Dict[str, Any]:
    norm_item = {}
    for k, v in item.items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            norm_item[k] = None
            continue
        if k in INVOICE_NUM_FIELDS:
            num, currency = normalize_numeric(v)
            norm_item[k] = num
            if currency and not currency_holder[0]:
                currency_holder[0] = currency
        elif "date" in k.lower():
            norm_item[k] = normalize_date(str(v))
        else:
            norm_item[k] = v.strip() if isinstance(v, str) else v
    return norm_item

def normalize_expense_item(item: Dict[str, Any], currency_holder: List[Optional[str]]) -> Dict[str, Any]:
    norm_item = {}
    for k, v in item.items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            norm_item[k] = None
            continue
        if k in EXPENSE_NUM_FIELDS:
            num, currency = normalize_numeric(v)
            norm_item[k] = num
            if currency and not currency_holder[0]:
                currency_holder[0] = currency
        elif k == "date":
            norm_item[k] = normalize_date(str(v))
        else:
            norm_item[k] = v.strip() if isinstance(v, str) else v
    return norm_item

def normalize_invoice(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    currency_holder = [None]
    data = trim_strings(data)
    for k, v in data.items():
        if k == "item_details" and isinstance(v, list):
            normalized[k] = [normalize_invoice_item(item, currency_holder) for item in v]
        elif k in INVOICE_NUM_FIELDS:
            num, currency = normalize_numeric(v)
            normalized[k] = num
            if currency and not currency_holder[0]:
                currency_holder[0] = currency
        elif k in INVOICE_DATE_FIELDS:
            normalized[k] = normalize_date(str(v)) if v else None
        elif isinstance(v, dict):
            normalized[k] = trim_strings(v)
        elif isinstance(v, str):
            normalized[k] = v.strip()
        else:
            normalized[k] = v

    optional_fields = [
        "due_date", "purchase_order_number", "payment_terms", "subtotal_amount",
        "total_discount", "vat_amount", "amount_in_words", "currency", "remarks"
    ]
    set_null(normalized, optional_fields)

    if "item_details" in normalized and isinstance(normalized["item_details"], list):
        subtotal = sum(item.get("amount", 0) or 0 for item in normalized["item_details"])
        normalized["subtotal_amount"] = subtotal
        tax = normalized.get("vat_amount")
        if tax is not None:
            try:
                normalized["total_amount"] = subtotal + float(tax)
            except Exception:
                pass

    if not normalized.get("currency") and currency_holder[0]:
        normalized["currency"] = currency_holder[0]

    if not normalized.get("currency"):
        vendor = None
        if "vendor_information" in normalized and isinstance(normalized["vendor_information"], dict):
            vendor = normalized["vendor_information"].get("name", "")
        elif "vendor_name" in normalized:
            vendor = normalized["vendor_name"]
        if vendor and ("ไทย" in vendor or "บริษัท" in vendor):
            normalized["currency"] = "THB"
    return normalized

def normalize_expense(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    currency_holder = [None]
    data = trim_strings(data)
    for k, v in data.items():
        if k == "expense_items" and isinstance(v, list):
            normalized[k] = [normalize_expense_item(item, currency_holder) for item in v]
        elif k in EXPENSE_NUM_FIELDS:
            num, currency = normalize_numeric(v)
            normalized[k] = num
            if currency and not currency_holder[0]:
                currency_holder[0] = currency
        elif k in EXPENSE_DATE_FIELDS:
            normalized[k] = normalize_date(str(v)) if v else None
        elif isinstance(v, dict):
            normalized[k] = trim_strings(v)
        elif isinstance(v, str):
            normalized[k] = v.strip()
        else:
            normalized[k] = v

    optional_fields = [
        "report_id", "employee_id", "department", "subtotal_amount", "vat_amount",
        "approval_name", "approval_status", "currency", "remarks"
    ]
    set_null(normalized, optional_fields)

    if "expense_items" in normalized and isinstance(normalized["expense_items"], list):
        subtotal = sum(item.get("amount", 0) or 0 for item in normalized["expense_items"])
        normalized["subtotal_amount"] = subtotal
        tax = normalized.get("vat_amount")
        if tax is not None:
            try:
                normalized["total_amount"] = subtotal + float(tax)
            except Exception:
                pass

    if not normalized.get("currency") and currency_holder[0]:
        normalized["currency"] = currency_holder[0]

    if not normalized.get("currency"):
        emp = normalized.get("employee_name", "")
        if emp and ("ไทย" in emp or "บริษัท" in emp):
            normalized["currency"] = "THB"

    return normalized

def normalize_by_document_type(data: Dict[str, Any]) -> Dict[str, Any]:
    doc_type = data.get("document_type", "").lower()
    if doc_type == "invoice":
        return normalize_invoice(data)
    elif doc_type == "expense_report":
        return normalize_expense(data)
    else:
        return data

def load_json(file_path: str) -> None:
    """Reads a JSON file, normalizes it, and prints results."""
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            raw_json = json.load(f)
        except json.JSONDecodeError:
            print(f"Invalid JSON: {os.path.basename(file_path)}")
            return

        normalized = normalize_by_document_type(raw_json)

        print(f"\nFile: {os.path.basename(file_path)}")
        print("Raw JSON:")
        print(json.dumps(raw_json, indent=2, ensure_ascii=False))

        print("\nNormalized JSON:")
        print(json.dumps(normalized, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    file_path = r"C:\Users\wasin.j\Desktop\data_normalize-validate\Test_normalize\expense_test.json"
    load_json(file_path)