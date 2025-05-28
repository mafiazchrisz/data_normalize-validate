import json
import os
from typing import List, Dict, Any
from datetime import datetime

invoice_req_fields = {
    "document_type": {"type": str},
    "invoice_number": {"type": str},
    "invoice_date": {"type": str},
    "vendor_information": {"type": dict},
    "buyer_information": {"type": dict},
    "item_details": {"type": list},
    "total_amount": {"type": float}
}

invoice_opt_fields = {
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

expense_req_fields = {
    "document_type": {"type": str},
    "employee_name": {"type": str},
    "expense_items": {"type": list},
    "total_amount": {"type": float},
}

expense_opt_fields = {
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

placeholder = ["", "N/A", "null", None]

def parse_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None 

def date_format(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False

def empty_value(value):
    """Check if a value is considered empty for required fields."""
    return value in placeholder or (isinstance(value, str) and value.strip() == "")

def req_fields_invoice(invoice: Dict[str, Any]) -> Dict[str, str]:
    """Return a dict of required fields that are empty for invoice."""
    empty_fields = {}
    for field in invoice_req_fields:
        value = invoice.get(field, None)
        if empty_value(value):
            empty_fields[field] = "Required field cannot be empty"
    return empty_fields

def req_fields_expense(expense: Dict[str, Any]) -> Dict[str, str]:
    """Return a dict of required fields that are empty for expense report."""
    empty_fields = {}
    for field in expense_req_fields:
        value = expense.get(field, None)
        if empty_value(value):
            empty_fields[field] = "Required field cannot be empty"
    return empty_fields

def validate_invoice(invoice: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "status": "pass",
        "invalid_fields": {},
        "logical_checks": []
    }

    # Check required fields are present and not empty
    empty_fields = req_fields_invoice(invoice)
    if empty_fields:
        result["status"] = "fail"
        result["invalid_fields"].update(empty_fields)

    # Required & type checks
    for field, rules in invoice_req_fields.items():
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

    # Optional fields: check type if present
    for field, rules in invoice_opt_fields.items():
        if field in invoice and invoice[field] not in placeholder:
            value = invoice[field]
            if not isinstance(value, rules["type"]):
                result["status"] = "fail"
                result["invalid_fields"][field] = f"Invalid type for optional field. Expected {rules['type']}"
            # Add date format check for due_date
            if field == "due_date":
                if not isinstance(value, str) or not date_format(value):
                    result["status"] = "fail"
                    result["invalid_fields"][field] = "Invalid date format. Expected YYYY-MM-DD"

    # Logical check: subtotal + vat - discount == total
    subtotal = invoice.get("subtotal_amount")
    vat = invoice.get("vat_amount")
    discount = invoice.get("total_discount")
    total = invoice.get("total_amount")

    # Only check if all are present and not None
    if all(x is not None for x in [subtotal, vat, total]):
        # If discount is None, treat as 0
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
    result = {
        "status": "pass",
        "invalid_fields": {},
        "logical_checks": []
    }

    # Check required fields are present and not empty
    empty_fields = req_fields_expense(expense)
    if empty_fields:
        result["status"] = "fail"
        result["invalid_fields"].update(empty_fields)

    # Required & type checks
    for field, rules in expense_req_fields.items():
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

    # Optional fields: check type if present
    for field, rules in expense_opt_fields.items():
        if field in expense and expense[field] not in placeholder:
            value = expense[field]
            if not isinstance(value, rules["type"]):
                result["status"] = "fail"
                result["invalid_fields"][field] = f"Invalid type for optional field. Expected {rules['type']}"
            # Add date format check for specific optional fields
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

    # Check date logic
    start = expense.get("period_start")
    end = expense.get("period_end")
    try:
        if start and end and date_format(start) and date_format(end):
            d1 = datetime.strptime(start, "%Y-%m-%d")
            d2 = datetime.strptime(end, "%Y-%m-%d")
            if d1 > d2:
                result["status"] = "fail"
                result["logical_checks"].append("period_start is after period_end")
    except Exception as e:
        result["logical_checks"].append("Date format error")

    # Validate date format in each expense_items
    items = expense.get("expense_items", [])
    if isinstance(items, list):
        for idx, item in enumerate(items):
            date_val = item.get("date")
            if date_val not in placeholder and (not isinstance(date_val, str) or not date_format(date_val)):
                result["status"] = "fail"
                result["invalid_fields"][f"expense_items {idx+1}"] = "Invalid date format. Expected YYYY-MM-DD"

    return result

def validate_document(document: Dict[str, Any]) -> Dict[str, Any]:
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

def validation_result(data: List[Dict[str, Any]]) -> None:
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
        validation_result(data)

if __name__ == "__main__":
    file_path = r"C:\Users\wasin.j\Desktop\data_normalize-validate\test_invoice_validation\sample2.json" # replace with your file path
    try:
        load_json(file_path)
    except Exception as e:
        print(f"Error: {e}")