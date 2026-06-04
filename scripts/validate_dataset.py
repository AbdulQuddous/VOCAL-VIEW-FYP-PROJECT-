# scripts/validate_dataset.py

import json
from pathlib import Path

# Required fields for each question
REQUIRED_FIELDS = ['question_text', 'keywords', 'difficulty']


def validate_dataset():
    """
    Validate all JSON question datasets in data/questions/
    Ensures all required fields exist and JSON is readable.
    """

    data_dir = Path('data/questions')
    errors = []
    total_files = 0
    total_questions = 0

    if not data_dir.exists():
        print(f"❌ Dataset directory not found: {data_dir}")
        return

    # Loop through all JSON files
    for json_file in data_dir.glob('*.json'):
        total_files += 1

        try:
            # ✅ FIX: UTF-8 encoding for Windows + special characters
            with open(json_file, 'r', encoding='utf-8') as f:
                questions = json.load(f)

        except json.JSONDecodeError as e:
            errors.append(f"{json_file.name}: Invalid JSON format → {str(e)}")
            continue

        except Exception as e:
            errors.append(f"{json_file.name}: File read error → {str(e)}")
            continue

        # Validate each question
        for idx, q in enumerate(questions):
            total_questions += 1

            # Check if question is dict
            if not isinstance(q, dict):
                errors.append(
                    f"{json_file.name} Q{idx+1}: Not a valid object"
                )
                continue

            # Check required fields
            for field in REQUIRED_FIELDS:
                if field not in q:
                    errors.append(
                        f"{json_file.name} Q{idx+1}: Missing field '{field}'"
                    )

            # Extra validation (important for your AI system)
            if 'keywords' in q and not isinstance(q['keywords'], list):
                errors.append(
                    f"{json_file.name} Q{idx+1}: 'keywords' must be a list"
                )

            if 'difficulty' in q:
                if q['difficulty'] not in ['easy', 'medium', 'hard']:
                    errors.append(
                        f"{json_file.name} Q{idx+1}: Invalid difficulty '{q['difficulty']}'"
                    )

    # ===================== RESULT =====================

    print("\n================ VALIDATION REPORT ================\n")
    print(f"📁 Files checked: {total_files}")
    print(f"❓ Questions checked: {total_questions}\n")

    if errors:
        print("❌ VALIDATION FAILED:\n")
        for err in errors:
            print(f"  - {err}")
        print("\n==================================================")
    else:
        print("✅ ALL DATASETS VALID")
        print("🚀 Your interview system is safe to run")
        print("==================================================")



# Allow direct execution
if __name__ == "__main__":
    validate_dataset()