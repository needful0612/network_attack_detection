import os
import pickle
import polars as pl

from scripts.kitnet.kitnet_engine import KitNetWorker

def kitnet_cold_start(lf: pl.LazyFrame):
    
    df = lf.drop("target").collect()

    worker = KitNetWorker() 

    matrix = df.to_numpy()
    
    for i in range(len(matrix)):
        worker.engine.process(matrix[i])
        
    with open("models/kitnet_state.pkl", "wb") as f:
        pickle.dump(worker.engine, f)