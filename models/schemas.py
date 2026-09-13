# models/schemas.py
from pydantic import BaseModel,ConfigDict
from typing import Optional
# Модель для одного элемента payload
class PayloadItem(BaseModel):
    model_config = ConfigDict(extra='ignore')
    requestId: str
    qrPayload: Optional[str] = None
    errorMessage: Optional[str] = None 