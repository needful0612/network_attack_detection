import polars as pl
import numpy as np

class stats_engine:
    def __init__(self):
        self.benign_stats = None
        self.clean_features = []
        self.feature_constants = {}

    def fit_robust_scaler(self, lf: pl.LazyFrame):
        self.benign_stats = (
            lf.filter(pl.col("target") == 0)
            .select([
                pl.all().median().name.suffix("_median"),
                (pl.col("*").quantile(0.75) - pl.col("*").quantile(0.25)).name.suffix("_iqr")
            ])
            .collect()
        )
        return self.benign_stats

    def get_scaling_expressions(
        self,
        lf: pl.LazyFrame
    ):
        schema_names = lf.collect_schema().names()
        if(self.benign_stats is None):
            self.fit_robust_scaler(lf)
            
        exprs = []
        for col in schema_names:
            if col == "target": continue
            m = self.benign_stats.get_column(f"{col}_median")[0]
            iqr = self.benign_stats.get_column(f"{col}_iqr")[0]
            iqr = iqr if iqr != 0 else 1.0
            
            self.feature_constants[col] = {"median": float(m), "iqr": float(iqr)}
            exprs.append(((pl.col(col) - m) / iqr).alias(col))
        return exprs
    
    def clips_lf(
        self, 
        lf: pl.LazyFrame, 
        lower_end = -10,
        higher_end = 10
    ):
        lf = lf.with_columns([
            pl.col("^column_.*$").clip(lower_end, higher_end),
            pl.col("^burst_.*$").clip(lower_end, higher_end)
        ])
        
        return lf
    
    def get_avg_median_and_iqr(self, lf: pl.LazyFrame):
        all_stats = (
        lf.filter(pl.col("target") == 0)
            .select([
                pl.concat_list(pl.col("^column_.*$").median().abs()).list.mean().alias("avg_median_error"),

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
        
        return {
            "avg_med": avg_med,
            "avg_iqr": avg_iqr
        }
        
    def get_feature_constants(
        self,
        lf:pl.LazyFrame
    ):
        if not self.feature_constants:
            self.get_scaling_expressions(lf)
        
        return self.feature_constants