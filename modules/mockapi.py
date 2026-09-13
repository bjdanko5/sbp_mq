from fastapi import APIRouter, HTTPException, status
import time
from pydantic import BaseModel, RootModel,Field 
import uuid
from typing import Optional

router = APIRouter()

# Модель для элемента запроса
# class QRCodeRequestItem(BaseModel):
#     requestId: str
#     retailer: str
#     amount: int
#     qrTtl: int = 129600  # 90 дней по умолчанию
#     persAcctIvc: str
#     persAcctGis: str
#     period: str  # ММГГГГ
#     paymentPurpose: str
#     payerAddress: str
#     serviceCode: str
#     redirectUrl: str

class QRCodeRequestItem(BaseModel):
    requestId: str  # Обязательное поле
    retailer: Optional[str] = None
    amount: Optional[int] = None
    qrTtl: Optional[int] = Field(default=129600, description="Время жизни QR в минутах")
    persAcctIvc: Optional[str] = None
    persAcctGis: Optional[str] = None
    period: Optional[str] = Field(None, pattern=r"^\d{2}\d{4}$", description="Формат ММГГГГ")
    paymentPurpose: Optional[str] = None
    payerAddress: Optional[str] = None
    serviceCode: Optional[str] = None
    redirectUrl: Optional[str] = None

# Корневая модель для запроса
class QRCodeRequest(RootModel):
    root: list[QRCodeRequestItem]

# Модель для ответа
class QRCodeResponse(BaseModel):
    requestId: str
    qrPayload: Optional[str]
    errorMessage: Optional[str] = "" 

#@router.post("/qr-code", response_model=list[QRCodeResponse])
@router.post("/qr-code", status_code=status.HTTP_202_ACCEPTED, response_model=list[QRCodeResponse])
async def mock_qr_code_endpoint(request: QRCodeRequest):
    """Мок-эндпоинт для тестирования отправки payload"""
    # Имитация обработки (задержка 0.5-1.5 сек)
    processing_time = 0.5 + (hash(request.model_dump_json()) % 1000) / 1000                             
    time.sleep(processing_time)
    
    responses = []
    for item in request.root:
        # Валидация данных (имитация ошибок)
        if len(item.requestId) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid requestId: {item.requestId}"
            )
        
        if item.amount is not None and item.amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )
        
        # Генерация мокового ответа
        response = QRCodeResponse(
            requestId=item.requestId,
            qrPayload=f"QR:{uuid.uuid4().hex}",
            errorMessage = "accepted"
        )
        responses.append(response)
    
    return responses