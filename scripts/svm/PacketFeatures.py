from pydantic import BaseModel, model_validator
from typing import Dict

class PacketFeatures(BaseModel):
    features: Dict[str, float]

    @model_validator(mode='before')
    def check_exact_keys(cls, values):
        feat_dict = values.get("features", {})
        expected_keys = {f"column_{i}" for i in range(1, 116)}
        actual_keys = set(feat_dict.keys())

        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys

        if missing:
            raise ValueError(f"Missing features: {missing}")
        if extra:
            raise ValueError(f"Unexpected extra features: {extra}")
            
        return values