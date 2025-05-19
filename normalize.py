"""
Invoice JSON Validator

This script validates JSON data extracted from invoice files.
It checks for required fields, performs logical validation, and calculates confidence scores.
"""
import json
import re
from datetime import datetime


# Define validation rules for invoice data
invoice_validation_rules = {
    # Required fields that must be present
    "required_fields": ["invoice_number", "invoice_date", "total_amount"],
    
    # Important fields (not required but impact confidence score)
    "important_fields": ["vendor_name", "due_date", "subtotal", "tax_amount", "line_items"],
    
    # Expected field count for confidence calculation
    "expected_field_count": 10,
    
    # Type validations for specific fields
    "field_types": {
        "invoice_number": "string",
        "invoice_date": "date",
        "due_date": "date",
        "total_amount": "number",
        "subtotal": "number",
        "tax_amount": "number",
        "line_items": "array",
        "vendor_name": "string",
        "client_name": "string",
        "payment_terms": "string"
    },
    
    # Format validations (optional)
    "formats": {
        "invoice_date": r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD format
        "due_date": r"^\d{4}-\d{2}-\d{2}$",      # YYYY-MM-DD format
        "invoice_number": r"^[\w\-\/\.]+$"       # Alphanumeric with some special chars
    },
    
    # Value constraints (optional)
    "constraints": {
        "total_amount": {
            "min": 0  # Total amount must be non-negative
        },
        "subtotal": {
            "min": 0
        },
        "tax_amount": {
            "min": 0
        }
    },
    
    # Logical relationships between fields
    "logical_checks": [
        {
            "name": "dates_chronology",
            "fields": ["invoice_date", "due_date"],
            "error_message": "Due date must be on or after invoice date"
        },
        {
            "name": "amount_calculation",
            "fields": ["subtotal", "tax_amount", "total_amount"],
            "error_message": "Total amount should equal subtotal plus tax amount"
        },
        {
            "name": "line_items_sum",
            "fields": ["line_items", "subtotal"],
            "error_message": "Line items should sum to subtotal"
        }
    ],
    
    # Rules for confidence calculation
    "confidence_rules": {
        # Value patterns that suggest default/placeholder values
        "placeholder_patterns": {
            "invoice_number": r"^(N\/A|Unknown|TBD|0+)$",
            "vendor_name": r"^(N\/A|Unknown|TBD|None)$",
            "client_name": r"^(N\/A|Unknown|TBD|None)$"
        },
        
        # Weight factors for confidence calculation
        "weights": {
            "required_fields": 0.5,   # 50% of confidence is based on required fields
            "important_fields": 0.2,  # 20% on important fields
            "logical_checks": 0.2,    # 20% on logical validations
            "field_count": 0.1        # 10% on overall field completeness
        }
    }
}


def validate_logical_check(invoice, check):
    """Execute logical validation checks based on check type"""
    fields = check["fields"]
    
    # Skip if any required field is missing
    if not all(field in invoice and invoice[field] is not None for field in fields):
        return True
    
    if check["name"] == "dates_chronology":
        # Check if due date is not earlier than invoice date
        invoice_date = datetime.fromisoformat(invoice["invoice_date"])
        due_date = datetime.fromisoformat(invoice["due_date"])
        return invoice_date <= due_date
    
    elif check["name"] == "amount_calculation":
        # Check if total equals subtotal + tax
        subtotal = invoice["subtotal"]
        tax_amount = invoice["tax_amount"]
        total_amount = invoice["total_amount"]
        # Allow for small floating point differences (within 0.01)
        return abs((subtotal + tax_amount) - total_amount) < 0.01
    
    elif check["name"] == "line_items_sum":
        # Check if line items sum to subtotal
        line_items = invoice["line_items"]
        subtotal = invoice["subtotal"]
        
        if not isinstance(line_items, list) or len(line_items) == 0:
            return True
        
        line_items_sum = 0
        for item in line_items:
            # Check if item has a total or calculate from quantity * unit_price
            if isinstance(item.get("total"), (int, float)):
                line_items_sum += item["total"]
            elif isinstance(item.get("quantity"), (int, float)) and isinstance(item.get("unit_price"), (int, float)):
                line_items_sum += item["quantity"] * item["unit_price"]
        
        # Allow for small floating point differences (within 0.01)
        return abs(line_items_sum - subtotal) < 0.01
    
    return True


def validate_invoice_data(invoice_data):
    """
    Validates the extracted invoice JSON data against defined rules
    
    Args:
        invoice_data: The JSON data to validate
        
    Returns:
        Dictionary with validation results including validity, errors, warnings, and confidence score
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "confidence": 1.0
    }
    
    # Check if input is a valid dictionary
    if not isinstance(invoice_data, dict):
        result["valid"] = False
        result["errors"].append("Invalid invoice data: must be a JSON object")
        result["confidence"] = 0
        return result
    
    # Track validation metrics for confidence calculation
    metrics = {
        "required_fields_present": 0,
        "required_fields_total": len(invoice_validation_rules["required_fields"]),
        "important_fields_present": 0,
        "important_fields_total": len(invoice_validation_rules["important_fields"]),
        "logical_checks_valid": 0,
        "logical_checks_total": 0,
        "fields_with_values": 0,
        "suspicious_values": 0
    }
    
    # Validate required fields
    for field in invoice_validation_rules["required_fields"]:
        if field not in invoice_data or invoice_data[field] is None:
            result["valid"] = False
            result["errors"].append(f"Missing required field: {field}")
        else:
            metrics["required_fields_present"] += 1
            metrics["fields_with_values"] += 1
    
    # Check important fields (not required but impact confidence)
    for field in invoice_validation_rules["important_fields"]:
        if field in invoice_data and invoice_data[field] is not None:
            metrics["important_fields_present"] += 1
            metrics["fields_with_values"] += 1
        else:
            result["warnings"].append(f"Missing important field: {field}")
    
    # Count total fields with values for completeness assessment
    for field in invoice_data:
        if (field not in invoice_validation_rules["required_fields"] and
            field not in invoice_validation_rules["important_fields"] and
            invoice_data[field] is not None):
            metrics["fields_with_values"] += 1
    
    # Validate field types
    for field, expected_type in invoice_validation_rules["field_types"].items():
        if field in invoice_data and invoice_data[field] is not None:
            value = invoice_data[field]
            
            if expected_type == "string" and not isinstance(value, str):
                result["valid"] = False
                result["errors"].append(f'Field "{field}" must be a string')
            
            elif expected_type == "number" and not isinstance(value, (int, float)):
                result["valid"] = False
                result["errors"].append(f'Field "{field}" must be a number')
            
            elif expected_type == "array" and not isinstance(value, list):
                result["valid"] = False
                result["errors"].append(f'Field "{field}" must be an array')
            
            elif expected_type == "date":
                # For date fields, check if it's a valid date string
                if not isinstance(value, str):
                    result["valid"] = False
                    result["errors"].append(f'Field "{field}" must be a date string')
                elif field in invoice_validation_rules["formats"]:
                    pattern = invoice_validation_rules["formats"][field]
                    if not re.match(pattern, value):
                        result["valid"] = False
                        result["errors"].append(f'Field "{field}" has invalid date format. Expected: YYYY-MM-DD')
                else:
                    try:
                        datetime.fromisoformat(value)
                    except ValueError:
                        result["valid"] = False
                        result["errors"].append(f'Field "{field}" contains an invalid date')
            
            # Check for suspicious placeholder values
            if field in invoice_validation_rules["confidence_rules"]["placeholder_patterns"]:
                pattern = invoice_validation_rules["confidence_rules"]["placeholder_patterns"][field]
                if isinstance(value, str) and re.match(pattern, value, re.IGNORECASE):
                    metrics["suspicious_values"] += 1
                    result["warnings"].append(f'Field "{field}" appears to contain a placeholder value: "{value}"')
    
    # Validate constraints
    for field, constraint in invoice_validation_rules["constraints"].items():
        if field in invoice_data and invoice_data[field] is not None:
            value = invoice_data[field]
            
            if "min" in constraint and value < constraint["min"]:
                result["valid"] = False
                result["errors"].append(f'Field "{field}" must be at least {constraint["min"]}')
            
            if "max" in constraint and value > constraint["max"]:
                result["valid"] = False
                result["errors"].append(f'Field "{field}" must be at most {constraint["max"]}')
    
    # Perform logical checks
    for check in invoice_validation_rules["logical_checks"]:
        # Only validate if all required fields for this check are present
        fields_present = all(field in invoice_data and invoice_data[field] is not None 
                           for field in check["fields"])
        
        if fields_present:
            metrics["logical_checks_total"] += 1
            
            if not validate_logical_check(invoice_data, check):
                result["valid"] = False
                result["errors"].append(check["error_message"])
            else:
                metrics["logical_checks_valid"] += 1
    
    # Calculate confidence score (0.0 to 1.0)
    confidence_weights = invoice_validation_rules["confidence_rules"]["weights"]
    
    # Calculate components of confidence
    required_fields_score = (metrics["required_fields_present"] / metrics["required_fields_total"] 
                            if metrics["required_fields_total"] > 0 else 1)
    
    important_fields_score = (metrics["important_fields_present"] / metrics["important_fields_total"] 
                             if metrics["important_fields_total"] > 0 else 1)
    
    logical_checks_score = (metrics["logical_checks_valid"] / metrics["logical_checks_total"] 
                           if metrics["logical_checks_total"] > 0 else 1)
    
    completeness_score = min(1, metrics["fields_with_values"] / 
                           invoice_validation_rules["expected_field_count"])
    
    # Apply penalties for suspicious values
    suspicious_value_penalty = 0.1 * min(metrics["suspicious_values"], 5)  # Cap at 50% penalty
    
    # Combine all confidence components using weights
    result["confidence"] = (
        (confidence_weights["required_fields"] * required_fields_score) +
        (confidence_weights["important_fields"] * important_fields_score) +
        (confidence_weights["logical_checks"] * logical_checks_score) +
        (confidence_weights["field_count"] * completeness_score) -
        suspicious_value_penalty
    )
    
    # Ensure confidence is between 0 and 1
    result["confidence"] = max(0, min(1, result["confidence"]))
    
    # Add confidence interpretation
    if result["confidence"] >= 0.9:
        result["confidence_level"] = "High"
    elif result["confidence"] >= 0.7:
        result["confidence_level"] = "Medium"
    elif result["confidence"] >= 0.5:
        result["confidence_level"] = "Low"
    else:
        result["confidence_level"] = "Very Low"
    
    return result


def format_value(value):
    """Helper to format values for console output"""
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return "[Object]"
    if isinstance(value, str):
        return f'"{value}"'
    return value


def validate_invoice_file(json_data):
    """
    Validates an invoice from either a JSON string or a Python dictionary
    
    Args:
        json_data: Either a JSON string or a Python dictionary representing invoice data
        
    Returns:
        Dictionary with validation results
    """
    try:
        # Parse JSON if string is provided
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        
        # Validate the invoice data
        validation_result = validate_invoice_data(data)
        
        print("\n========== INVOICE VALIDATION REPORT ==========")
        
        if validation_result["valid"]:
            print("✅ VALIDATION STATUS: PASSED")
        else:
            print("❌ VALIDATION STATUS: FAILED")
        
        print(f"\nCONFIDENCE SCORE: {(validation_result['confidence'] * 100):.1f}% ({validation_result['confidence_level']})")
        
        if validation_result["errors"]:
            print("\nERRORS:")
            for error in validation_result["errors"]:
                print(f"  - {error}")
        
        if validation_result["warnings"]:
            print("\nWARNINGS:")
            for warning in validation_result["warnings"]:
                print(f"  - {warning}")
        
        print("\nDETAILED DATA ASSESSMENT:")
        fields = sorted(data.keys())
        has_line_items = "line_items" in data and isinstance(data["line_items"], list)
        
        for field in fields:
            if field != "line_items":
                is_required = field in invoice_validation_rules["required_fields"]
                is_important = field in invoice_validation_rules["important_fields"]
                status = "[REQUIRED]" if is_required else "[IMPORTANT]" if is_important else "[OPTIONAL]"
                print(f"  {field}: {format_value(data[field])} {status}")
        
        if has_line_items:
            print("\nLINE ITEMS:")
            for index, item in enumerate(data["line_items"]):
                print(f"  Item #{index + 1}:")
                for key, value in item.items():
                    print(f"    {key}: {format_value(value)}")
        
        print("==============================================")
        
        return validation_result
    
    except json.JSONDecodeError as e:
        print(f"Error validating invoice: {e}")
        return {
            "valid": False,
            "errors": [f"JSON parsing error: {e}"],
            "warnings": [],
            "confidence": 0,
            "confidence_level": "Very Low"
        }
    except Exception as e:
        print(f"Error validating invoice: {e}")
        return {
            "valid": False,
            "errors": [f"Validation error: {e}"],
            "warnings": [],
            "confidence": 0,
            "confidence_level": "Very Low"
        }


# Example invoices for testing
valid_invoice = {
    "invoice_number": "INV-2023-001",
    "invoice_date": "2023-05-15",
    "due_date": "2023-06-15",
    "vendor_name": "Acme Corp",
    "client_name": "Globex Inc.",
    "subtotal": 1000.00,
    "tax_amount": 250.50,
    "total_amount": 1250.50,
    "payment_terms": "Net 30",
    "currency": "USD",
    "line_items": [
        {"description": "Product A", "quantity": 2, "unit_price": 250.00, "total": 500.00},
        {"description": "Service B", "quantity": 5, "unit_price": 100.00, "total": 500.00}
    ]
}

invalid_invoice = {
    "invoice_date": "05/15/2023",  # Wrong format
    "due_date": "2023-04-15",      # Due date before invoice date
    "vendor_name": "N/A",          # Placeholder value
    "total_amount": "1250.50",     # Should be a number, not a string
    "subtotal": 1000.00,
    "tax_amount": 200.00           # Total doesn't match subtotal + tax
}

partial_invoice = {
    "invoice_number": "INV-2023-002",
    "invoice_date": "2023-05-20",
    "total_amount": 500.00,
    # Missing many fields that would impact confidence
}

if __name__ == "__main__":
    # Test all examples
    print("========== TESTING VALID INVOICE ==========")
    validate_invoice_file(valid_invoice)

    print("\n\n========== TESTING INVALID INVOICE ==========")
    validate_invoice_file(invalid_invoice)

    print("\n\n========== TESTING PARTIAL INVOICE ==========")
    validate_invoice_file(partial_invoice)