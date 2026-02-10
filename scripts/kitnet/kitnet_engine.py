import os
import pickle
import numpy as np
import traceback
from scripts.kitnet.KitNET.KitNET import KitNET
from scripts.config.setting import settings

MODEL_DIR = settings.MODEL_DIR

class KitNetWorker:
    def __init__(self, model_path=None):
        # FM_grace_period: packets used to cluster features (e.g., 5000)
        # AD_grace_period: packets used to train autoencoders (e.g., 50000)
        if model_path and os.path.exists(model_path):
            try:
                print(f"[*] Loading warmed KitNET state from {model_path}")
                with open(model_path, "rb") as f:
                    self.engine = pickle.load(f)
            except Exception as e:
                print(f"--- Error Caught ---")
                traceback.print_exc()
        else:
            print("[*] Initializing fresh KitNET instance")
            self.engine = KitNET(
                n=115, 
                max_autoencoder_size=10, 
                FM_grace_period=5000, 
                AD_grace_period=50000
            )

    def process_features(self, feature_vector):
        """
        Intake: 115 feature list/array from Redis
        Output: Anomaly score (RMSE)
        """
        x = np.array(feature_vector, dtype=np.float32)
        
        score = self.engine.process(x)
        
        return score