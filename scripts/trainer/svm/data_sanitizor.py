import polars as pl

class data_sanitizor:
    def __init__(self):
        pass
    
    def check_and_fill_nan(
        self, 
        clean_features,
        lf:pl.LazyFrame
    ):
        nan_counts = (
            lf.select([
                pl.col(c).is_nan().sum().alias(f"{c}_nans") 
                for c in clean_features
            ]).collect()
        )
        total_nans = sum(nan_counts.row(0))
        print(f"Found {total_nans} total NaN entries.")

        lf = lf.with_columns([
            pl.col("burst_src_ip_log").fill_nan(0).fill_null(0),
            pl.col("burst_socket_log").fill_nan(0).fill_null(0)
        ])
        
        return lf