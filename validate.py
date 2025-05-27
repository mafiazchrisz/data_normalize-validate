import json
import os
from typing import List, Dict, Any
from datetime import datetime

# Configuration
REQUIRED_FIELDS = {
    "document_type": {"type": str},
    "invoice_number": {"type": str},
    "invoice_date": {"type": str},
    "vendor_information": {"type": dict},
    "buyer_information": {"type": dict},
    "item_details": {"type": list},
    "total_amount": {"type": float},
}

# Optional fields from invoice.json
OPTIONAL_FIELDS = {
    "due_date": {"type": str},
    "purchase_order_number": {"type": str},
    "payment_terms": {"type": str},
    "subtotal_amount": {"type": float},
    "total_discount": {"type": float},
    "vat_amount": {"type": float},
    "amount_in_words": {"type": str},
    "currency": {"type": str},
    "remarks": {"type": str},
}

PLACEHOLDER_VALUES = ["", "N/A", "null", None]

def parse_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON file must contain a list of invoices.")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")    

def is_valid_date_format(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False

def validate_invoice_data(invoice: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "status": "pass",
        "invalid_fields": {},
        "logical_checks": []
    }

    # Required & type checks
    for field, rules in REQUIRED_FIELDS.items():
        value = invoice.get(field, None)

        if value in PLACEHOLDER_VALUES:
            result["status"] = "fail"
            result["invalid_fields"][field] = "Field is empty or contains placeholder"
        elif field not in invoice:
            result["status"] = "fail"
            result["invalid_fields"][field] = "Missing required field"
        elif not isinstance(value, rules["type"]):
            result["status"] = "fail"
            result["invalid_fields"][field] = f"Invalid type. Expected {rules['type']}, got {type(value)}"
        elif field == "invoice_date":
            if not isinstance(value, str) or not is_valid_date_format(value):
                result["status"] = "fail"
                result["invalid_fields"][field] = "Invalid date format. Expected YYYY-MM-DD"
        elif field == "item_details":
            if not isinstance(value, list) or len(value) == 0:
                result["status"] = "fail"
                result["invalid_fields"][field] = "item_details must be a non-empty list"

    # Optional fields: check type if present
    for field, rules in OPTIONAL_FIELDS.items():
        if field in invoice and invoice[field] not in PLACEHOLDER_VALUES:
            value = invoice[field]
            if not isinstance(value, rules["type"]):
                result["status"] = "fail"
                result["invalid_fields"][field] = f"Invalid type for optional field. Expected {rules['type']}, got {type(value)}"

    # Logical consistency checks (example: total_amount should be sum of item_details amounts)
    total = parse_float(invoice.get("total_amount"))
    if isinstance(invoice.get("item_details"), list):
        item_total = sum(parse_float(item.get("amount", 0)) or 0 for item in invoice["item_details"])
        if total is not None and abs(item_total - total) > 0.01:
            result["status"] = "fail"
            result["logical_checks"].append("Sum of item_details amounts does not match total_amount")
    return result

def print_validation_report(data: List[Dict[str, Any]]) -> None:
    for idx, invoice in enumerate(data):
        #print(f"\n--- Invoice #{idx + 1} Validation ---")
        result = validate_invoice_data(invoice)
        print(f"Validation Status: {result['status'].upper()}")

        if result["status"] == "fail":
            if result["invalid_fields"]:
                print("Reasons:")
                for field, error in result["invalid_fields"].items():
                    print(f"  - {field}: {error}")
            if result["logical_checks"]:
                for issue in result["logical_checks"]:
                    print(f"  - {issue}")

def process_json_folder(folder_path: str) -> None:
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, dict):
                        data = [data]
                    elif not isinstance(data, list):
                        print(f"File: {filename}")
                        print("Error: JSON file must contain an invoice object or a list of invoices.")
                        continue
                except json.JSONDecodeError as e:
                    print(f"File: {filename}")
                    print(f"Error: Invalid JSON format: {e}")
                    continue
                print(f"\nFile: {filename}")
                print_validation_report(data)

if __name__ == "__main__":
    folder_path = (r"C:\Users\wasin.j\Desktop\data_normalize-validate\samples-validate")  # replace with your folder path
    try:
        process_json_folder(folder_path)
    except Exception as e:
        print(f"Error: {e}")