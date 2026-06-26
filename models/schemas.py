from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReviewBase(BaseModel):
    repo_name: str
    pr_number: int


class ReviewCreate(ReviewBase):
    pass


class ReviewRead(ReviewBase):
    id: UUID
    status: str
    findings_count: int
    created_at: datetime

    class Config:
        from_attributes = True
