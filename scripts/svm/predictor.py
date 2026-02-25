import json
import numpy as np
import onnxruntime as rt
import os

class BotFilterPredictor:
    def __init__(self, model_path, config_path):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        self.feature_names = self.config["feature_names"]
        self.constants = self.config["constants"]
        self.feature_weights = np.array(self.config.get("svm_weights", []))
        # add memory mapping to prevent model idle in memory
        self.sess = rt.InferenceSession(model_path)
        self.input_name = self.sess.get_inputs()[0].name

    def preprocess(self, raw_data):
        """
        raw_data: A dict containing column_1 to column_115.
        Returns: A numpy array ready for ONNX.
        """
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
            
            # prevent overflow cause NaN
            processed[new_col] = np.log1p(max(0, f_val)) - np.log1p(max(0, s_val))

        final_vector = []
        for col in self.feature_names:
            val = processed.get(col, 0)
            
            if col.startswith("column_"):
                val = np.sign(val) * np.log1p(np.abs(val))
            
            # Safety: If IQR is tiny or zero, don't divide by it
            stats = self.constants[col]
            m = stats["median"]
            iqr = stats["iqr"]
            
            if iqr < 1e-9:
                val = val - m 
            else:
                val = (val - m) / iqr
            
            val = np.clip(val, -10, 10)
            
            final_vector.append(val)
        
        arr = np.array([final_vector], dtype=np.float32)
        return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    
    def explain_prediction(self, X_processed):
        impacts = self.feature_weights * X_processed[0]
        top_idx = np.argmax(np.abs(impacts))
        
        return {
            "feature": self.feature_names[top_idx],
            "contribution": float(impacts[top_idx])
        }

    def predict(self, raw_data):
        X = self.preprocess(raw_data)
        
        # ONNX inference
        # preds[0] = labels, preds[1] = probabilities
        preds = self.sess.run(None, {self.input_name: X})
        
        prob_attack = preds[1][0][1]
        label = preds[0][0]
        
        explanation = self.explain_prediction(X) if label else None
        return {
            "is_attack": bool(label),
            "probability": float(prob_attack),
            "uncertain": 0.2 < prob_attack < 0.8,
            "explanation": explanation
        }