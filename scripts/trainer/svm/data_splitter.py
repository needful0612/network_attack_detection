import polars as pl

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