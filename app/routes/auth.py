from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from jose import jwt

from app.config import JWT_SECRET, PROVISIONING_SECRET

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_MAX_TTL_SECONDS = 86_400  # 24 hours


class TokenRequest(BaseModel):
    tenant_id: str
    ttl_seconds: int = Field(default=3600, ge=1, le=_MAX_TTL_SECONDS)


@router.post("/token")
def create_token(
    req: TokenRequest,
    x_provisioning_key: str | None = Header(default=None),
):
    if PROVISIONING_SECRET is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token provisioning is disabled on this server.",
        )

    if not x_provisioning_key or not secrets.compare_digest(x_provisioning_key, PROVISIONING_SECRET):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid provisioning key.")

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
