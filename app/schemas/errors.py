from typing import Any, Dict, Optional

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorBody
