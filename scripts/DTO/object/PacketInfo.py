from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import uuid
import time
import json

class PacketInfo(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    
    src_ip: str
    dst_ip: str
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    
    features: List[float]

    @field_validator('features')
    @classmethod
    def validate_features(cls, v: List[float]) -> List[float]:
        if len(v) != 115:
            raise ValueError(f"Expected 115 features, got {len(v)}")
        return v

    def to_redis(self):
        return self.model_dump_json()

    @classmethod
    def from_redis(cls, data: str):
        return cls.model_validate_json(data)