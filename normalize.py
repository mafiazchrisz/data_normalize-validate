import os
import json
import re
from datetime import datetime

# === Normalize value based on key ===
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

# === Compare raw input with normalized ===
def compare_after_normalization(raw_json):
    normalized = normalize_values_only(raw_json)
    diffs = {}
    for key in raw_json.keys():
        raw_val = raw_json[key]
        norm_val = normalized.get(key)
        if normalize_value(key, raw_val) != norm_val:
            diffs[key] = {
                "raw": raw_val,
                "normalized": norm_val
            }
    return normalized, diffs

# === Process all JSON files in a folder ===
def process_json_folder(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    raw_json = json.load(f)
                except json.JSONDecodeError:
                    print(f"❌ Skipping invalid JSON: {filename}")
                    continue

                normalized, diffs = compare_after_normalization(raw_json)

                print(f"\n📄 File: {filename}")
                print("🔍 Raw OCR JSON:")
                print(json.dumps(raw_json, indent=2))

                print("\n✅ Normalized JSON:")
                print(json.dumps(normalized, indent=2))

# === Example Usage ===
if __name__ == "__main__":
    folder_path = (r"C:\Users\mafia\Desktop\OCR\sample-normalize")  # replace with your folder path
    process_json_folder(folder_path)
