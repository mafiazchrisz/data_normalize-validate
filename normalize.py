import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

months = {
    "มกราคม": "01", "กุมภาพันธ์": "02", "มีนาคม": "03", "เมษายน": "04",
    "พฤษภาคม": "05", "มิถุนายน": "06", "กรกฎาคม": "07", "สิงหาคม": "08",
    "กันยายน": "09", "ตุลาคม": "10", "พฤศจิกายน": "11", "ธันวาคม": "12",
    "ม.ค.": "01", "ก.พ.": "02", "มี.ค.": "03", "เม.ย.": "04",
    "พ.ค.": "05", "มิ.ย.": "06", "ก.ค.": "07", "ส.ค.": "08",
    "ก.ย.": "09", "ต.ค.": "10", "พ.ย.": "11", "ธ.ค.": "12",
}

currency_symbol = {
    'THB': 'THB', '฿': 'THB', 'บาท': 'THB'
}

invoice_num_fields = [
    "quantity", "unit_price", "discount", "amount",
    "subtotal_amount", "total_discount", "vat_amount", "total_amount"
]

invoice_date_fields = [
    "invoice_date", "due_date"
]

expense_num_fields = [
    "quantity", "amount", "subtotal_amount", "vat_amount", "total_amount"
]

expense_date_fields = [
    "report_date", "period_start", "period_end"
]

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
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue

    m = re.match(r"(\d{1,2})\s+([ก-๙\.]+)\s+(\d{4})", value)
    if m:
        day, thai_month, year = m.groups()
        month = months.get(thai_month)
        year = int(year)
        if year > 2500:
            year -= 543
        return f"{year:04d}-{month}-{int(day):02d}"
    return value

def set_null(data: Dict[str, Any], optional_fields: List[str]) -> None:
    for field in optional_fields:
        if field in data and (data[field] == "" or data[field] is None):
            data[field] = None

def normalize_numeric(value: Any) -> Tuple[Optional[float], Optional[str]]:
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    value = str(value).strip()
    if value == "":
        return None, None
    m = re.match(r"([\d,\.]+)\s*([A-Za-zก-๙$€฿]*)", value)
    if m:
        num, currency = m.groups()
        num = num.replace(",", "")
        currency_code = currency_symbol.get(currency, currency) if currency else None
        try:
            num = float(num)
        except Exception:
            num = None
        return num, currency_code
    try:
        return float(value), None
    except Exception:
        return None, None

def normalize_invoice_item(item: Dict[str, Any], currency_holder: List[Optional[str]]) -> Dict[str, Any]:
    norm_item = {}
    for k, v in item.items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            norm_item[k] = None
            continue
        if k in invoice_num_fields:
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
        if k in expense_num_fields:
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
    # Normalize fields
    for k, v in data.items():
        if k == "item_details" and isinstance(v, list):
            normalized[k] = [normalize_invoice_item(item, currency_holder) for item in v]
        elif k in invoice_num_fields:
            num, currency = normalize_numeric(v)
            normalized[k] = num
            if currency and not currency_holder[0]:
                currency_holder[0] = currency
        elif k in invoice_date_fields:
            normalized[k] = normalize_date(str(v)) if v else None
        elif isinstance(v, dict):
            normalized[k] = trim_strings(v)
        elif isinstance(v, str):
            normalized[k] = v.strip()
        else:
            normalized[k] = v

    # Set missing optional fields to null
    optional_fields = [
        "due_date", "purchase_order_number", "payment_terms", "subtotal_amount",
        "total_discount", "vat_amount", "amount_in_words", "currency", "remarks"
    ]
    set_null(normalized, optional_fields)

    # Recalculate subtotal_amount from item_details if present
    if "item_details" in normalized and isinstance(normalized["item_details"], list):
        subtotal = sum(item.get("amount", 0) or 0 for item in normalized["item_details"])
        normalized["subtotal_amount"] = subtotal
        # If vat_amount exists, recalc total_amount
        tax = normalized.get("vat_amount")
        if tax is not None:
            try:
                normalized["total_amount"] = subtotal + float(tax)
            except Exception:
                pass

    # Set currency if found in any field
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
    # Normalize fields
    for k, v in data.items():
        if k == "expense_items" and isinstance(v, list):
            normalized[k] = [normalize_expense_item(item, currency_holder) for item in v]
        elif k in expense_num_fields:
            num, currency = normalize_numeric(v)
            normalized[k] = num
            if currency and not currency_holder[0]:
                currency_holder[0] = currency
        elif k in expense_date_fields:
            normalized[k] = normalize_date(str(v)) if v else None
        elif isinstance(v, dict):
            normalized[k] = trim_strings(v)
        elif isinstance(v, str):
            normalized[k] = v.strip()
        else:
            normalized[k] = v

    # Set missing optional fields to null
    optional_fields = [
        "report_id", "employee_id", "department", "subtotal_amount", "vat_amount",
        "approval_name", "approval_status", "currency", "remarks"
    ]
    set_null(normalized, optional_fields)

    # Recalculate subtotal_amount from expense_items if present
    if "expense_items" in normalized and isinstance(normalized["expense_items"], list):
        subtotal = sum(item.get("amount", 0) or 0 for item in normalized["expense_items"])
        normalized["subtotal_amount"] = subtotal
        # If vat_amount exists, recalc total_amount
        tax = normalized.get("vat_amount")
        if tax is not None:
            try:
                normalized["total_amount"] = subtotal + float(tax)
            except Exception:
                pass

    # Set currency if found in any field
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
        # Fallback to generic normalization if unknown type
        return data

def compare_after_normalization(raw_json: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    normalized = normalize_by_document_type(raw_json)
    diffs: Dict[str, Any] = {}
    for key in raw_json.keys():
        raw_val = raw_json[key]
        norm_val = normalized.get(key)
        # Use normalize_numeric for numeric fields to compare
        if key in invoice_num_fields + expense_num_fields:
            raw_num, _ = normalize_numeric(raw_val)
            if raw_num != norm_val:
                diffs[key] = {
                    "raw": raw_val,
                    "normalized": norm_val
                }
        elif key in invoice_date_fields + expense_date_fields:
            raw_date = normalize_date(str(raw_val)) if raw_val else None
            if raw_date != norm_val:
                diffs[key] = {
                    "raw": raw_val,
                    "normalized": norm_val
                }
        else:
            if isinstance(raw_val, str):
                raw_val = raw_val.strip()
            if raw_val != norm_val:
                diffs[key] = {
                    "raw": raw_val,
                    "normalized": norm_val
                }
    return normalized, diffs

def process_json_file(file_path: str) -> None:
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
    file_path = r"C:\Users\wasin.j\Desktop\data_normalize-validate\Test_normalize\expense_test.json"  # replace with your file path
    process_json_file(file_path)