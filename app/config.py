import os


BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_DIR      = os.path.join(BASE_DIR, "data", "input")
PROCESSED_DIR  = os.path.join(BASE_DIR, "data", "processed")
FAILED_DIR     = os.path.join(BASE_DIR, "data", "failed")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(FAILED_DIR, exist_ok=True)