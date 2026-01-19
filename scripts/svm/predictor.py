import json
import numpy as np
import onnxruntime as rt
import os

class BotFilterPredictor:
    def __init__(self, model_path="models/svm_bot_filter.onnx", config_path="models/preprocessor_config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        self.feature_names = self.config["feature_names"]
        self.constants = self.config["constants"]
        
        self.sess = rt.InferenceSession(model_path)
        self.input_name = self.sess.get_inputs()[0].name

    def preprocess(self, raw_data):
        """
        raw_data: A dict containing column_1 to column_115.
        Returns: A numpy array ready for ONNX.
        """
        # Using dict.get(key, 0) to handle missing values safely
        processed = raw_data.copy()
        
        ratio_pairs = {
            "burst_src_ip_log": ("column_1", "column_93"),
            "burst_host_log": ("column_6", "column_98"),
            "burst_channel_log": ("column_11", "column_103"),
            "burst_socket_log": ("column_16", "column_108")
        }

        for new_col, (fast, slow) in ratio_pairs.items():
            f_val = processed.get(fast, 0)
            s_val = processed.get(slow, 0)
            # log1p is np.log(1 + x)
            processed[new_col] = np.log1p(f_val) - np.log1p(s_val)

        final_vector = []
        for col in self.feature_names:
            val = processed.get(col, 0)
            
            if col.startswith("column_"):
                val = np.sign(val) * np.log1p(np.abs(val))
            
            stats = self.constants[col]
            val = (val - stats["median"]) / stats["iqr"]
            
            val = np.clip(val, -10, 10)
            
            final_vector.append(val)

        return np.array([final_vector], dtype=np.float32)

    def predict(self, raw_data):
        X = self.preprocess(raw_data)
        
        # ONNX inference
        # preds[0] = labels, preds[1] = probabilities
        preds = self.sess.run(None, {self.input_name: X})
        
        prob_attack = preds[1][0][1]
        label = preds[0][0]
        
        return {
            "is_attack": bool(label),
            "attack_probability": float(prob_attack),
            "uncertain": 0.2 < prob_attack < 0.8
        }

# dry run test
if __name__ == "__main__":
    predictor = BotFilterPredictor()
    
    sample_packet = {f"column_{i}": 1.5 for i in range(1, 116)}
    
    result = predictor.predict(sample_packet)
    print(f"Result: {result}")