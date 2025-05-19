from typing import List, Dict, Any
from datetime import datetime

# Configuration
REQUIRED_FIELDS = {
    "invoice_number": {"type": str},
    "invoice_date": {"type": str},
    "total_amount": {"type": (int, float, str)},
    "subtotal": {"type": (int, float, str)},
    "tax": {"type": (int, float, str)},
    "line_items": {"type": list},  # Expecting non-empty list of items
}

PLACEHOLDER_VALUES = ["", "N/A", "null", None]

def parse_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def is_valid_date_format(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False

def validate_invoice_data(invoice: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "status": "pass",
        "valid_fields": [],
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
            else:
                result["valid_fields"].append(field)

        elif field == "line_items":
            if not isinstance(value, list) or len(value) == 0:
                result["status"] = "fail"
                result["invalid_fields"][field] = "line_items must be a non-empty list"
            else:
                result["valid_fields"].append(field)
        else:
            result["valid_fields"].append(field)

    # Logical consistency checks
    subtotal = parse_float(invoice.get("subtotal"))
    tax = parse_float(invoice.get("tax"))
    total = parse_float(invoice.get("total_amount"))

    if subtotal is not None and tax is not None and total is not None:
        expected_total = subtotal + tax
        if abs(total - expected_total) > 0.01:
            result["status"] = "fail"
            result["logical_checks"].append("total_amount does not equal subtotal + tax")

    # Check line_items sum
    if isinstance(invoice.get("line_items"), list) and invoice["line_items"]:
        line_total = sum(parse_float(item.get("amount", 0)) or 0 for item in invoice["line_items"])
        if subtotal is not None and abs(line_total - subtotal) > 0.01:
            result["status"] = "fail"
            result["logical_checks"].append("Line item sum does not match subtotal")

    return result

def print_validation_report(data: List[Dict[str, Any]]) -> None:
    for idx, invoice in enumerate(data):
        print(f"\n--- Invoice #{idx + 1} Validation ---")
        result = validate_invoice_data(invoice)
        print(f"Validation Status: {result['status'].upper()}")

        if result["valid_fields"]:
            print("Valid Fields:")
            for field in result["valid_fields"]:
                print(f"  - {field}: {invoice.get(field)}")

        if result["invalid_fields"]:
            print("Invalid Fields:")
            for field, error in result["invalid_fields"].items():
                print(f"  - {field}: {error}")

        if result["logical_checks"]:
            print("Logical Check Issues:")
            for issue in result["logical_checks"]:
                print(f"  - {issue}")

# Example usage
if __name__ == "__main__":
    sample_data = [
        {
            "invoice_number": "INV-001",
            "invoice_date": "2025-05-16",
            "total_amount": 110.0,
            "subtotal": 100.0,
            "tax": 10.0,
            "line_items": [{"amount": 60.0}, {"amount": 40.0}]
        },
        {
            "invoice_number": "INV-002",
            "invoice_date": "2025-05-15",
            "total_amount": 200.0,
            "subtotal": 150.0,
            "tax": 20.0,
            "line_items": [{"amount": 100.0}, {"amount": 40.0}]
        },
        {
            "invoice_number": "",
            "invoice_date": "N/A",
            "total_amount": "N/A",
            "subtotal": "N/A",
            "tax": "",
            "line_items": []
        }
    ]

    print_validation_report(sample_data)