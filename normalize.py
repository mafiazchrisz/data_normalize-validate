import re
from datetime import datetime
import json

# === Value Normalization Function ===
def normalize_value(key, value):
    if not isinstance(value, str):
        value = str(value)

    value = value.strip()

    if key.lower() == "date":
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

    if key.lower() == "total":
        match = re.findall(r"[\d.,]+", value)
        if match:
            return match[0].replace(",", "")

    return value

# === Normalize only values ===
def normalize_values_only(data):
    normalized = {}
    for key, value in data.items():
        normalized[key] = normalize_value(key, value)
    return normalized

# === Compare normalized values by same keys ===
def compare_by_keys(ocr_json, reference_json):
    ocr_norm = normalize_values_only(ocr_json)
    ref_norm = normalize_values_only(reference_json)

    diffs = {}
    all_keys = set(ref_norm.keys()) | set(ocr_norm.keys())
    for key in all_keys:
        ocr_val = ocr_norm.get(key)
        ref_val = ref_norm.get(key)
        if ocr_val != ref_val:
            diffs[key] = {
                "ocr": ocr_val,
                "reference": ref_val
            }

    return diffs, ocr_norm, ref_norm

# === Example Input ===
ocr_json = {
    "Company Name": " Acme Corp. ",
    "Total": "1,234.56",
    "Date": "09/05/2025",
    "Tax ID": "123-456-789"
}

reference_json = {
    "Company Name": "Acme Corp.",
    "Total": "1234.56",
    "Date": "2025-05-09",
    "Tax ID": "123-456-789"
}

# === Run Comparison ===
diffs, ocr_norm, ref_norm = compare_by_keys(ocr_json, reference_json)

# === Output ===
print("🔍 OCR JSON (raw input):")
print(json.dumps(ocr_json, indent=2))

print("\n📄 Reference JSON (raw input):")
print(json.dumps(reference_json, indent=2))

print("\n✅ Normalized OCR JSON:")
print(json.dumps(ocr_norm, indent=2))

print("\n✅ Normalized Reference JSON:")
print(json.dumps(ref_norm, indent=2))

print("\n🧾 Differences After Normalization:")
if not diffs:
    print("✔ No differences found.")
else:
    for key, val in diffs.items():
        print(f" - {key}: OCR='{val['ocr']}' | Reference='{val['reference']}'")
