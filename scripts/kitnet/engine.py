import numpy as np
from kitnet.KitNET.KitNET import KitNET

class KitNetWorker:
    def __init__(self):
        # FM_grace_period: packets used to cluster features (e.g., 5000)
        # AD_grace_period: packets used to train autoencoders (e.g., 50000)
        self.engine = KitNET(
            n=115, 
            max_autoencoder_size=10, 
            FM_grace_period=5000, 
            AD_grace_period=50000
        )

    def handle_request(self, feature_vector):
        """
        Intake: 115 feature list/array from Redis
        Output: Anomaly score (RMSE)
        """
        # Ensure vector is a numpy array for KitNET
        x = np.array(feature_vector, dtype=np.float32)
        
        # This one call handles everything:
        # 1. Increments internal packet count
        # 2. Decides if it should train or predict
        # 3. Returns RMSE
        score = self.engine.process(x)
        
        return score