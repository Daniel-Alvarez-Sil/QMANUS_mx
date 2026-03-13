from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from jose import jwt

from app.config import JWT_SECRET

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    tenant_id: str
    ttl_seconds: int | None = 3600


@router.post("/token")
def create_token(req: TokenRequest):
    if not req.tenant_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id required")

    now = datetime.utcnow()
    payload = {
        "tid": req.tenant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=req.ttl_seconds)).timestamp()),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}
