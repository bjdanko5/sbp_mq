# routes/mockapi.py
from fastapi import APIRouter, HTTPException, status
import time
import uuid
from pydantic import BaseModel, RootModel, Field
from typing import Optional

from models.schemas import PayloadItem

router = APIRouter()


# Модель для элемента запроса
class QRCodeRequestItem(BaseModel):
    requestId: str
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


# ============================================================
#                      POST /qr-code
# ============================================================
@router.post("/qr-code", status_code=status.HTTP_202_ACCEPTED, response_model=list[PayloadItem])
async def mock_qr_code_post(request: QRCodeRequest):
    """Мок-эндпоинт POST для тестирования создания QR."""
    # processing_time = 0.5 + (hash(...) % 1000) / 1000
    # time.sleep(processing_time)
    
    responses = []
    for item in request.root:
        if item.amount is not None and item.amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )
        
        responses.append(
            PayloadItem(
                requestId=item.requestId,
                qrPayload=f"QR:{uuid.uuid4().hex}",
                errorMessage="accepted"
            )
        )
    
    return responses


# ============================================================
#                       GET /qr-code
# ============================================================
@router.get("/qr-code", response_model=list[PayloadItem])
async def mock_qr_code_get(request: QRCodeRequest):
    """Мок-эндпоинт GET для получения QR-кодов."""
    # processing_time = 0.5 + (hash(...) % 1000) / 1000
    # time.sleep(processing_time)
    
    responses = []
    for item in request.root:
        # Имитация ошибки: если requestId начинается с "err"
        if item.requestId.startswith("err"):
            responses.append(
                PayloadItem(
                    requestId=item.requestId,
                    qrPayload=None,
                    errorMessage=f"Error processing {item.requestId}"
                )
            )
        else:
            responses.append(
                PayloadItem(
                    requestId=item.requestId,
                    qrPayload=f"QR:{uuid.uuid4().hex}",
                    errorMessage=None
                )
            )
    
    return responses


# ============================================================
#                      PATCH /qr-code/block
# ============================================================
@router.patch("/qr-code/block", status_code=status.HTTP_202_ACCEPTED)
async def mock_qr_code_block(request: QRCodeRequest):
    """Мок-эндпоинт PATCH для блокировки QR-кодов."""
    # processing_time = 0.5 + (hash(...) % 1000) / 1000
    # time.sleep(processing_time)
    
    results = []
    for item in request.root:
        results.append({
            "requestId": item.requestId,
            "status": "blocked",
            "message": f"QR {item.requestId} успешно заблокирован"
        })
    
    return {"status": "success", "blocked": results}