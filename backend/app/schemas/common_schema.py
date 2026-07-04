from pydantic import BaseModel
from typing import Optional


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "Operation completed successfully"


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
