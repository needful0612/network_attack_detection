import polars as pl

from scripts.config.setting import settings
    
MIRAI_DATA = settings.MIRAI_DATA
MIRAI_LABELS = settings.MIRAI_LABELS
OS_DATA = settings.OS_DATA
OS_LABELS = settings.OS_LABELS

DATA_DIR = settings.DATA_DIR
    
# dataset loading & attach label & merge
def get_final_lazyframe():
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
    
    return final_lf

def save_lf(lf: pl.LazyFrame):
    lf.sink_parquet(f"{DATA_DIR}/combined_kitsune.parquet")

def load_lf(filename):
    # ex. new_lf = (pl.scan_parquet(f"{DATA_DIR}/combined_kitsune.parquet"))
    # combined_kitsune.parquet = filename
    lf = (pl.scan_parquet(f"{DATA_DIR}/{filename}"))
    return lf