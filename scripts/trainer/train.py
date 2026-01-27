import os
import gc
import json
import hashlib
import sys

import pandas as pd
import numpy as np
import polars as pl

from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix

from skl2onnx import to_onnx
from skl2onnx.common.data_types import FloatTensorType

def clear_memory(*args):
    for var in args:
        if var in globals():
            del globals()[var]
    gc.collect()

DATA_DIR = "data"
MIRAI_DATA = os.path.join(DATA_DIR, "Mirai_dataset.csv.gz")
MIRAI_LABELS = os.path.join(DATA_DIR, "Mirai_labels.csv.gz")
OS_DATA = os.path.join(DATA_DIR, "OS%20Scan_dataset.csv.gz")
OS_LABELS = os.path.join(DATA_DIR, "OS%20Scan_labels.csv.gz")

RANDOM_SEED = 45
IS_ATTACK_THRESHOLD = 0.5

MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

def get_script_hash():
    with open(__file__, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

CURRENT_HASH = get_script_hash()
MODEL_PATH = os.path.join(MODEL_DIR, "svm_bot_filter.onnx")
CONFIG_PATH = os.path.join(MODEL_DIR, "preprocessor_config.json")

if os.path.exists(CONFIG_PATH) and os.path.exists(MODEL_PATH):
    with open(CONFIG_PATH, "r") as f:
        saved_config = json.load(f)
        if saved_config.get("hash") == CURRENT_HASH:
            print(">>> Training script and model are up to date. Skipping...")
            sys.exit(0)
    
# dataset loading & attach label & merge
def get_lazy_frame(file_path):
    return pl.scan_csv(file_path, has_header=False)

mirai_data_lf = get_lazy_frame(MIRAI_DATA)
mirai_labels_lf = get_lazy_frame(MIRAI_LABELS)
os_data_lf = get_lazy_frame(OS_DATA)
os_labels_lf = get_lazy_frame(OS_LABELS)

def get_cleaned_mirai(path):
    return (
        pl.scan_csv(path, has_header=False)
        .drop("column_1")
        .rename({f"column_{i}": f"column_{i-1}" for i in range(2, 117)})
    )

def get_cleaned_os_labels(path):
    return(
        pl.scan_csv(path, has_header=False)
        .slice(1)
        .select([
            pl.col("column_2")
            .cast(pl.Int64) 
            .alias("target") 
        ])
    )

mirai_data_lf = get_cleaned_mirai(MIRAI_DATA)
mirai_targets = pl.scan_csv(MIRAI_LABELS, has_header=False).rename({"column_1": "target"})
os_labels_lf = get_cleaned_os_labels(OS_LABELS)

def attach_label_to_df(lf, label_lf):
    return pl.concat([lf, label_lf], how="horizontal")

mirai_combined = attach_label_to_df(mirai_data_lf, mirai_targets)
os_combined = attach_label_to_df(os_data_lf, os_labels_lf)

final_lf = pl.concat([mirai_combined, os_combined], how="vertical")

# final_lf.sink_parquet(f"{DATA_DIR}/combined_kitsune.parquet")
# load the dataset and get burst ratio
# new_lf = (pl.scan_parquet(f"{DATA_DIR}/combined_kitsune.parquet"))
new_lf = final_lf

def get_std_df(lf):
    std_df = lf.select([
        pl.all().std()
    ]).collect()

    std_list = list(zip(std_df.columns, std_df.row(0)))
    std_list.sort(key=lambda x: x[1] if x[1] is not None else 0, reverse=True)

    return
std_list = get_std_df(new_lf)

def calculate_burst_ratios(lf: pl.LazyFrame) -> pl.LazyFrame:
    ratio_pairs = {
        "burst_src_ip":   ("column_1",  "column_93"),
        "burst_host":      ("column_6",  "column_98"),
        "burst_channel":  ("column_11", "column_103"),
        "burst_socket":   ("column_16", "column_108")
    }

    for name, (fast, slow) in ratio_pairs.items():
        # log(1+fast) - log(1+slow) is numerically stable and represents the ratio
        lf = lf.with_columns([
            (pl.col(fast).log1p() - pl.col(slow).log1p()).alias(f"{name}_log")
        ])
    return lf

def purge_leakage_features(lf: pl.LazyFrame) -> pl.LazyFrame:
    leak_regex = r"^(column_(68|71|74|77|80|67|70|73|76|79|1|5|24|28|47|51|93|97|98|103|108))$"

    slow_window_cols = [f"column_{i}" for i in range(93, 116)]

    return (
        lf.drop(slow_window_cols, strict=False)
          .drop(pl.col(leak_regex), strict=False)
    )

def apply_symmetric_log(lf: pl.LazyFrame) -> pl.LazyFrame:
    # Compresses large values while preserving sign: sign(x) * log(|x| + 1).
    target_cols = [c for c in lf.collect_schema().names() if "column_" in c]

    return lf.with_columns([
        (pl.col(c).sign() * pl.col(c).abs().log1p()).alias(c)
        for c in target_cols
    ])

def preprocess_layer(lf: pl.LazyFrame) -> pl.LazyFrame:
    lf = calculate_burst_ratios(lf)
    lf = purge_leakage_features(lf)
    lf = apply_symmetric_log(lf)

    return lf

new_lf = preprocess_layer(new_lf)

new_lf_std_list = get_std_df(new_lf)

benign_stats = (
    new_lf.filter(pl.col("target") == 0)
    .select([
        pl.all().median().name.suffix("_median"),
        (pl.col("*").quantile(0.75) - pl.col("*").quantile(0.25)).name.suffix("_iqr")
    ])
    .collect()
)

robust_exprs = []
for col in new_lf.collect_schema().names():
    if col == "target": continue

    m = benign_stats.get_column(f"{col}_median")[0]
    iqr = benign_stats.get_column(f"{col}_iqr")[0]

    # Avoid division by zero
    iqr = iqr if iqr != 0 else 1.0

    robust_exprs.append(
        ((pl.col(col) - m) / iqr).alias(col)
    )

new_lf = new_lf.with_columns(robust_exprs)

all_stats = (
    new_lf.filter(pl.col("target") == 0)
    .select([
        # 1. avg(abs(median))
        pl.concat_list(pl.col("^column_.*$").median().abs()).list.mean().alias("avg_median_error"),

        # 2. average IQR
        pl.concat_list(
            pl.col("^column_.*$").quantile(0.75) - pl.col("^column_.*$").quantile(0.25)
        ).list.mean().alias("avg_iqr_value")
    ])
    .collect()
)

avg_med = all_stats["avg_median_error"][0]
avg_iqr = all_stats["avg_iqr_value"][0]

print(f"Overall Median Error: {avg_med:.4e}")
print(f"Overall Average IQR: {avg_iqr:.4f}") 

new_lf = new_lf.with_columns([
    pl.col("^column_.*$").clip(-10, 10),
    pl.col("^burst_.*$").clip(-10, 10)
])

final_bounds = new_lf.select([
    pl.max_horizontal(pl.all().max()).alias("absolute_max"),
    pl.min_horizontal(pl.all().min()).alias("absolute_min")
]).collect()

def prepare_train_val_test(lf: pl.LazyFrame, feature_cols: list, target_col: str = "target"):
    """
    Slices a LazyFrame into Train (70%), Val (15%), and Test (15%) sets.
    Returns X, y tuples for each set.
    """
    total_rows = lf.select(pl.len()).collect().item()
    train_end = int(total_rows * 0.7)
    val_end = int(total_rows * 0.85)

    train_lf = lf.slice(0, train_end)
    val_lf   = lf.slice(train_end, val_end - train_end)
    test_lf  = lf.slice(val_end, total_rows - val_end)

    def to_xy(target_lf):
        df = target_lf.select(feature_cols + [target_col]).collect()
        X = df.drop(target_col).to_numpy()
        y = df[target_col].to_numpy()

        pos_rate = (y.sum() / len(y)) * 100
        return X, y, pos_rate

    X_train, y_train, train_p = to_xy(train_lf)
    X_val, y_val, val_p     = to_xy(val_lf)
    X_test, y_test, test_p   = to_xy(test_lf)

    print(f"{' SPLIT REPORT ':=^40}")
    print(f"Train: {X_train.shape[0]:>8} rows | Attack: {train_p:>5.1f}%")
    print(f"Val:   {X_val.shape[0]:>8} rows | Attack: {val_p:>5.1f}%")
    print(f"Test:  {X_test.shape[0]:>8} rows | Attack: {test_p:>5.1f}%")
    print(f"{'='*40}")

    return (X_train, y_train), (X_val, y_val), (X_test, y_test)

corr_df = new_lf.select(pl.col("^column_.*$")).collect().corr()
stds = new_lf.select(pl.col("^column_.*$")).collect().std()

cols = corr_df.columns
to_drop = set()
for i in range(len(cols)):
    if cols[i] in to_drop: continue

    for j in range(i + 1, len(cols)):
        if cols[j] in to_drop: continue

        if abs(corr_df[i, j]) > 0.99: 
            std_i = stds.get_column(cols[i])[0]
            std_j = stds.get_column(cols[j])[0]

            if std_i >= std_j:
                to_drop.add(cols[j])
            else:
                to_drop.add(cols[i])
                break

all_current_cols = new_lf.collect_schema().names()
surviving_features = [c for c in all_current_cols if c not in to_drop]

burst_check = [c for c in surviving_features if "burst" in c]

clean_features = [f for f in surviving_features if f != 'target']
nan_counts = (
    new_lf.select([
        pl.col(c).is_nan().sum().alias(f"{c}_nans") 
        for c in clean_features
    ]).collect()
)

new_lf = new_lf.with_columns([
    pl.col("burst_src_ip_log").fill_nan(0).fill_null(0),
    pl.col("burst_socket_log").fill_nan(0).fill_null(0)
])

train, val, test = prepare_train_val_test(new_lf, clean_features)
X_train, y_train = train
X_val, y_val = val
clear_memory('train_lf', 'val_lf', 'test_lf')
def calculate_metrics(name, probs, y):
    preds = (probs > IS_ATTACK_THRESHOLD).astype(int)
    cm = confusion_matrix(y, preds)
    fn = cm[1, 0] if cm.shape == (2, 2) else 0
    uncertain_rate = ((probs > 0.2) & (probs < 0.8)).mean() * 100
    return {
        "Model": name,
        "Accuracy": (y == preds).mean(),
        "Uncertainty Rate (%)": uncertain_rate,
        "Missed Attacks (FN)": fn
    }


base = LinearSVC(C=1.0, dual=False, max_iter=5000, random_state=RANDOM_SEED)
clf = CalibratedClassifierCV(base, cv=5, method='sigmoid') 
clf.fit(X_train, y_train)
probs = clf.predict_proba(X_val)[:, 1]
metrics = calculate_metrics(f"SVM (C={1.0})", probs, y_val)
print(metrics)

initial_type = [('float_input', FloatTensorType([None, X_train.shape[1]]))]
onx = to_onnx(clf, initial_types=initial_type, target_opset=14)
with open(os.path.join(MODEL_DIR, "svm_bot_filter.onnx"), "wb") as f:
    f.write(onx.SerializeToString())

feature_constants = {}

for col in clean_features:
    m = benign_stats.get_column(f"{col}_median")[0]
    iqr = benign_stats.get_column(f"{col}_iqr")[0]
    iqr = iqr if iqr != 0 else 1.0
    
    feature_constants[col] = {
        "median": float(m),
        "iqr": float(iqr)
    }

with open(CONFIG_PATH, "w") as f:
    json.dump({
        "hash": CURRENT_HASH,           # The key to the 'Smart Skip'
        "feature_names": clean_features,
        "constants": feature_constants
    }, f, indent=4)
    
print(f">>> [SUCCESS] Model and Config version {CURRENT_HASH[:8]} saved to {MODEL_DIR}")