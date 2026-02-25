import os
import gc
import json
import hashlib
import sys

import polars as pl

from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix

from skl2onnx import to_onnx
from skl2onnx.common.data_types import FloatTensorType

# svm
from scripts.trainer.svm.preprocess import get_final_lazyframe
from scripts.trainer.svm.feature_pipeline import feature_pipeline
from scripts.trainer.svm.stats_engine import stats_engine
from scripts.trainer.svm.feature_selector import feature_selector
from scripts.trainer.svm.data_sanitizor import data_sanitizor
from scripts.trainer.svm.data_splitter import prepare_train_val_test
from scripts.trainer.svm.model_evaluator import(
    get_avg_weight,
    evaluate_svm
)

# kitnet
from scripts.trainer.kitnet_trainer.kitnet_cold_start import(
    kitnet_cold_start
)

from scripts.utils.utils import(
    clear_memory,
    get_script_hash,
    get_project_hash
)
from scripts.config.setting import settings

RANDOM_SEED = settings.RANDOM_SEED
IS_ATTACK_THRESHOLD = settings.IS_ATTACK_THRESHOLD

MODEL_DIR = settings.MODEL_DIR
MODEL_PATH = settings.MODEL_PATH
CONFIG_PATH = settings.CONFIG_PATH

DEPENDENCIES = [
    __file__,
    "scripts/trainer/svm/preprocess.py",
    "scripts/trainer/svm/feature_pipeline.py",
    "scripts/trainer/svm/stats_engine.py",
    "scripts/trainer/svm/feature_selector.py",
    "scripts/trainer/svm/data_sanitizor.py",
    "scripts/trainer/svm/data_splitter.py",
    "scripts/trainer/svm/model_evaluator.py",
    "scripts/trainer/kitnet_trainer/kitnet_cold_start.py",
    "scripts/config/setting.py",
]

CURRENT_HASH = get_project_hash(DEPENDENCIES)

def check_project_status_skip_if_unchange():
    """
    CURRENT_HASH = get_script_hash(__file__)

    if os.path.exists(CONFIG_PATH) and os.path.exists(MODEL_PATH):
        with open(CONFIG_PATH, "r") as f:
            saved_config = json.load(f)
            if saved_config.get("hash") == CURRENT_HASH:
                print(">>> Training script and model are up to date. Skipping...")
                sys.exit(0)
    """
    if os.path.exists(CONFIG_PATH) and os.path.exists(MODEL_PATH):
        with open(CONFIG_PATH, "r") as f:
            saved_config = json.load(f)
            if saved_config.get("hash") == CURRENT_HASH:
                print(f">>> Project state {CURRENT_HASH[:8]} is up to date. Skipping...")
                sys.exit(0)
                
def start_training_kitnet(lf: pl.LazyFrame):
    kitnet_lf = (
        lf
        .filter(pl.col("target") == 0)
        .head(55000)
    )

    materialized_df = kitnet_lf.collect()

    print(f">>> KitNET: Training on {materialized_df.shape} samples...")
    kitnet_cold_start(kitnet_lf)
    print(f">>> [SUCCESS] KitNET state saved to {MODEL_DIR}")

def start_training_svm(
    new_lf: pl.LazyFrame
):
    #------------------------
    #new_lf = get_final_lazyframe()
    #-----------------------

    pipeline = feature_pipeline()
    new_lf = pipeline.run_full_feature_preprocessing(new_lf)

    engine = stats_engine()
    robust_exprs = engine.get_scaling_expressions(new_lf)
    new_lf = new_lf.with_columns(robust_exprs)
    engine.get_avg_median_and_iqr(new_lf)
    new_lf = engine.clips_lf(new_lf)

    selector = feature_selector()
    clean_features = selector.get_clean_features(new_lf)
    #------------
    sanitizor = data_sanitizor()
    new_lf = sanitizor.check_and_fill_nan(
        clean_features,
        new_lf
    )
    #------------
    train, val, test = prepare_train_val_test(new_lf, clean_features)
    X_train, y_train = train
    X_val, y_val = val
    clear_memory('train_lf', 'val_lf', 'test_lf')
    print(f">>> SVM: Training started...")
    base = LinearSVC(C=1.0, dual=False, max_iter=5000, random_state=RANDOM_SEED)
    clf = CalibratedClassifierCV(base, cv=5, method='sigmoid') 
    clf.fit(X_train, y_train)
    print(f">>> SVM: Training finished...")
    #-----------------------------
    metrics = evaluate_svm(
        clf,
        X_val,
        y_val,
        IS_ATTACK_THRESHOLD
    )
    print(f">>> SVM: Evaluation Report...")
    print(metrics)

    avg_weights = get_avg_weight(clf)
    #-----------------------------
    initial_type = [('float_input', FloatTensorType([None, X_train.shape[1]]))]
    onx = to_onnx(clf, initial_types=initial_type, target_opset=14)
    with open(MODEL_PATH, "wb") as f:
        f.write(onx.SerializeToString())

    feature_constants = engine.get_feature_constants(new_lf)
    #-----------------------------
    with open(CONFIG_PATH, "w") as f:
        json.dump({
            "hash": CURRENT_HASH,
            "feature_names": clean_features,
            "constants": feature_constants,
            "svm_weights": avg_weights
        }, f, indent=4)
        
    print(f">>> [SUCCESS] Model and Config version {CURRENT_HASH[:8]} saved to {MODEL_DIR}")
    
def start_training_progress():
    check_project_status_skip_if_unchange()
    lf = get_final_lazyframe()
    start_training_kitnet(lf)
    start_training_svm(lf)
    
start_training_progress()
