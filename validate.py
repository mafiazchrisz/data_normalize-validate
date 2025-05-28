import json
import os
from typing import List, Dict, Any
from datetime import datetime

INVOICE_REQUIRED_FIELDS = {
    "document_type": {"type": str},
    "invoice_number": {"type": str},
    "invoice_date": {"type": str},
    "vendor_information": {"type": dict},
    "buyer_information": {"type": dict},
    "item_details": {"type": list},
    "total_amount": {"type": float}
}

INVOICE_OPTIONAL_FIELDS = {
    "due_date": {"type": str},
    "purchase_order_number": {"type": str},
    "payment_terms": {"type": str},
    "subtotal_amount": {"type": float},
    "total_discount": {"type": float},
    "vat_amount": {"type": float},
    "amount_in_words": {"type": str},
    "currency": {"type": str},
    "remarks": {"type": str}
}

EXPENSE_REQUIRED_FIELDS = {
    "document_type": {"type": str},
    "employee_name": {"type": str},
    "expense_items": {"type": list},
    "total_amount": {"type": float},
}

EXPENSE_OPTIONAL_FIELDS = {
    "report_id": {"type": str},
    "employee_id": {"type": str},
    "department": {"type": str},
    "report_date": {"type": str},
    "period_start": {"type": str},
    "period_end": {"type": str},
    "subtotal_amount": {"type": float},
    "vat_amount": {"type": float},
    "approval_name": {"type": str},
    "approval_status": {"type": str},
    "currency": {"type": str},
    "remarks": {"type": str}
}

PLACEHOLDER_VALUES = ["", "N/A", "null", None]

# --- Utility Functions ---

def parse_float(val):
    """Safely parse a float value, return None if not possible."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def date_format(date_str: str) -> bool:
    """Check if a string matches YYYY-MM-DD date format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False

def is_empty(value):
    """Check if a value is considered empty for required fields."""
    return value in PLACEHOLDER_VALUES or (isinstance(value, str) and value.strip() == "")

# --- Validation Functions ---

def find_empty_fields(data: Dict[str, Any], required_fields: Dict[str, Any]) -> Dict[str, str]:
    """Return a dict of required fields that are empty."""
    empty_fields = {}
    for field in required_fields:
        value = data.get(field, None)
        if is_empty(value):
            empty_fields[field] = "Required field cannot be empty"
    return empty_fields

def validate_invoice(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an invoice document."""
    result = {
        "status": "pass",
        "invalid_fields": {},
        "logical_checks": []
    }

    # Required fields: presence and not empty
    empty_fields = find_empty_fields(invoice, INVOICE_REQUIRED_FIELDS)
    if empty_fields:
        result["status"] = "fail"
        result["invalid_fields"].update(empty_fields)

    # Required fields: type and specific checks
    for field, rules in INVOICE_REQUIRED_FIELDS.items():
        value = invoice.get(field, None)
        if field not in invoice:
            result["status"] = "fail"
            result["invalid_fields"][field] = "Missing required field"
        elif not isinstance(value, rules["type"]):
            result["status"] = "fail"
            result["invalid_fields"][field] = f"Invalid type for required field. Expected {rules['type']}"
        elif field == "invoice_date":
            if not isinstance(value, str) or not date_format(value):
                result["status"] = "fail"
                result["invalid_fields"][field] = "Invalid date format. Expected YYYY-MM-DD"
        elif field == "item_details":
            if not isinstance(value, list) or len(value) == 0:
                result["status"] = "fail"
                result["invalid_fields"][field] = "item_details must be a non-empty list"

    # Optional fields: type and specific checks
    for field, rules in INVOICE_OPTIONAL_FIELDS.items():
        if field in invoice and invoice[field] not in PLACEHOLDER_VALUES:
            value = invoice[field]
            if not isinstance(value, rules["type"]):
                result["status"] = "fail"
                result["invalid_fields"][field] = f"Invalid type for optional field. Expected {rules['type']}"
            if field == "due_date":
                if not isinstance(value, str) or not date_format(value):
                    result["status"] = "fail"
                    result["invalid_fields"][field] = "Invalid date format. Expected YYYY-MM-DD"

    # Logical check: subtotal + vat - discount == total
    subtotal = invoice.get("subtotal_amount")
    vat = invoice.get("vat_amount")
    discount = invoice.get("total_discount")
    total = invoice.get("total_amount")
    if all(x is not None for x in [subtotal, vat, total]):
        discount = discount if discount is not None else 0.0
        try:
            expected_total = float(subtotal) + float(vat) - float(discount)
            if abs(float(total) - expected_total) > 0.01:
                result["status"] = "fail"
                result["logical_checks"].append(
                    f"Incorrect total summary: ({subtotal} + {vat} - {discount} != {total})"
                )
        except Exception as e:
            result["status"] = "fail"
            result["logical_checks"].append(f"Error in logical total calculation: {e}")

    return result

def validate_expense(expense: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an expense report document."""
    result = {
        "status": "pass",
        "invalid_fields": {},
        "logical_checks": []
    }

    # Required fields: presence and not empty
    empty_fields = find_empty_fields(expense, EXPENSE_REQUIRED_FIELDS)
    if empty_fields:
        result["status"] = "fail"
        result["invalid_fields"].update(empty_fields)

    # Required fields: type and specific checks
    for field, rules in EXPENSE_REQUIRED_FIELDS.items():
        value = expense.get(field, None)
        if field not in expense:
            result["status"] = "fail"
            result["invalid_fields"][field] = "Missing required field"
        elif not isinstance(value, rules["type"]):
            result["status"] = "fail"
            result["invalid_fields"][field] = f"Invalid type. Expected {rules['type']}"
        elif field == "expense_items":
            if not isinstance(value, list) or len(value) == 0:
                result["status"] = "fail"
                result["invalid_fields"][field] = "expense_items must be a non-empty list"

    # Optional fields: type and specific checks
    for field, rules in EXPENSE_OPTIONAL_FIELDS.items():
        if field in expense and expense[field] not in PLACEHOLDER_VALUES:
            value = expense[field]
            if not isinstance(value, rules["type"]):
                result["status"] = "fail"
                result["invalid_fields"][field] = f"Invalid type for optional field. Expected {rules['type']}"
            if field in ["report_date", "period_start", "period_end"]:
                if not isinstance(value, str) or not date_format(value):
                    result["status"] = "fail"
                    result["invalid_fields"][field] = "Invalid date format. Expected YYYY-MM-DD"

    # Logical check: subtotal + vat == total
    subtotal = expense.get("subtotal_amount")
    vat = expense.get("vat_amount")
    total = expense.get("total_amount")
    if all(x is not None for x in [subtotal, vat, total]):
        try:
            expected_total = float(subtotal) + float(vat)
            if abs(float(total) - expected_total) > 0.01:
                result["status"] = "fail"
                result["logical_checks"].append(
                    f"Incorrect total summary: ({subtotal} + {vat} != {total})"
                )
        except Exception as e:
            result["status"] = "fail"
            result["logical_checks"].append(f"Error in logical total calculation: {e}")

    # Date logic: period_start <= period_end
    start = expense.get("period_start")
    end = expense.get("period_end")
    try:
        if start and end and date_format(start) and date_format(end):
            d1 = datetime.strptime(start, "%Y-%m-%d")
            d2 = datetime.strptime(end, "%Y-%m-%d")
            if d1 > d2:
                result["status"] = "fail"
                result["logical_checks"].append("period_start is after period_end")
    except Exception:
        result["logical_checks"].append("Date format error")

    # Validate date format in each expense_items
    items = expense.get("expense_items", [])
    if isinstance(items, list):
        for idx, item in enumerate(items):
            date_val = item.get("date")
            if date_val not in PLACEHOLDER_VALUES and (not isinstance(date_val, str) or not date_format(date_val)):
                result["status"] = "fail"
                result["invalid_fields"][f"expense_items {idx+1}"] = "Invalid date format. Expected YYYY-MM-DD"

    return result

def validate_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a document by its type."""
    doc_type = document.get("document_type", "").lower()
    if doc_type == "invoice":
        return validate_invoice(document)
    elif doc_type == "expense_report":
        return validate_expense(document)
    else:
        return {
            "status": "fail",
            "invalid_fields": {"document_type": "Unknown or missing document_type"},
            "logical_checks": []
        }

def print_validation_result(data: List[Dict[str, Any]]) -> None:
    """Print validation results for a list of documents."""
    for document in data:
        result = validate_document(document)
        print(f"Validation Status: {result['status'].upper()}")
        if result["status"] == "fail":
            if result["invalid_fields"]:
                print("Outputs:")
                for field, error in result["invalid_fields"].items():
                    print(f"  - {field}: {error}")
            if result["logical_checks"]:
                print("Logical Checks:")
                for issue in result["logical_checks"]:
                    print(f"  - {issue}")

def load_json(file_path: str) -> None:
    """Load a JSON file and validate its contents."""
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                print(f"Error: JSON file must contain an invoice or expense object or a list of documents.")
                return
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON format: {e}")
            return
        print(f"\nFile: {os.path.basename(file_path)}")
        print_validation_result(data)

if __name__ == "__main__":
    file_path = r"C:\Users\wasin.j\Desktop\data_normalize-validate\test_invoice_validation\sample2.json"  # replace with your file path
    try:
        load_json(file_path)
    except Exception as e:
        print(f"Error: {e}")