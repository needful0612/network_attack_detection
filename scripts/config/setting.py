import os

class Setting:
    DATA_DIR = os.getenv("DATA_DIR", "./data")
    MODEL_DIR = os.getenv("MODEL_DIR", "./models")

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(MODEL_DIR, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create directory: {e}")

    MIRAI_DATA = os.path.join(DATA_DIR, "Mirai_dataset.csv.gz")
    MIRAI_LABELS = os.path.join(DATA_DIR, "Mirai_labels.csv.gz")
    OS_DATA = os.path.join(DATA_DIR, "OS%20Scan_dataset.csv.gz")
    OS_LABELS = os.path.join(DATA_DIR, "OS%20Scan_labels.csv.gz")
    
    MODEL_PATH = os.path.join(MODEL_DIR, "svm_bot_filter.onnx")
    CONFIG_PATH = os.path.join(MODEL_DIR, "preprocessor_config.json")

    RANDOM_SEED = 45
    IS_ATTACK_THRESHOLD = 0.5

settings = Setting()