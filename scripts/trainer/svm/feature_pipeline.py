import polars as pl
import re

class feature_pipeline:
    def __init__(self, leakage_regex = None):
        self.leakage_regex = leakage_regex or r"^(column_(68|71|74|77|80|67|70|73|76|79|1|5|24|28|47|51|93|97|98|103|108))$"
        
    def run_full_feature_preprocessing(self, lf:pl.LazyFrame) -> pl.LazyFrame:
        """The main entry point for the training pipeline."""
        lf = self._calculate_burst_ratios(lf)
        lf = self._purge_leakage_features(lf)
        lf = self._apply_symmetric_log(lf)
        return lf
    
    def _calculate_burst_ratios(self, lf):
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

    def _purge_leakage_features(self,lf):

        slow_window_cols = [f"column_{i}" for i in range(93, 116)]

        return (
            lf.drop(slow_window_cols, strict=False)
            .drop(pl.col(self.leakage_regex), strict=False)
        )

    def _apply_symmetric_log(self, lf):
        # Compresses large values while preserving sign: sign(x) * log(|x| + 1).
        target_cols = [c for c in lf.collect_schema().names() if c.startswith("column_")]

        return lf.with_columns([
            (pl.col(c).sign() * pl.col(c).abs().log1p()).alias(c)
            for c in target_cols
        ])