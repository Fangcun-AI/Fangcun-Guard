"""Request and response schemas for content scanning."""

from typing import List, Optional

from pydantic import BaseModel, Field


class EmailScanRequest(BaseModel):
    content: str = Field(..., description="Email content (EML format or plain text)")


class WebpageScanRequest(BaseModel):
    content: str = Field(..., description="Webpage content (HTML or plain text)")
    url: Optional[str] = Field(None, description="URL of the webpage being scanned")


class ScanResponse(BaseModel):
    id: str
    scan_type: str
    risk_level: str
    risk_types: List[str] = Field(default_factory=list)
    risk_content: List[str] = Field(default_factory=list)
    score: Optional[float] = None
