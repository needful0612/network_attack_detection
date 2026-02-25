import polars as pl

class feature_selector:
    def __init__(self, threshold=0.99):
        self.threshold = threshold
        self.to_drop = set()
    
    def find_redundant_features(self, lf: pl.LazyFrame):
        corr_df = lf.select(pl.col("^column_.*$")).collect().corr()
        stds = lf.select(pl.col("^column_.*$")).collect().std()

        cols = corr_df.columns
        for i in range(len(cols)):
            if cols[i] in self.to_drop: continue
            for j in range(i + 1, len(cols)):
                if cols[j] in self.to_drop: continue

                if abs(corr_df[i, j]) > self.threshold: 
                    std_i = stds.get_column(cols[i])[0]
                    std_j = stds.get_column(cols[j])[0]
                    if std_i >= std_j:
                        self.to_drop.add(cols[j])
                    else:
                        self.to_drop.add(cols[i])
                        break
        return self.to_drop

    def get_clean_features(
        self, 
        lf:pl.LazyFrame
    ):
        if not self.to_drop:
            self.find_redundant_features(lf)
        all_cols = lf.collect_schema().names()
        return [c for c in all_cols if c not in self.to_drop and c != 'target']