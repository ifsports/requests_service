from sqlalchemy import Column, String, Enum as SQLEnum, DateTime, UUID, ForeignKey
import uuid
from enum import Enum as PyEnum
from typing import Optional
from datetime import datetime, timezone
from shared.database import Base
from pydantic import BaseModel


class RequestTypeEnum(str, PyEnum):
    approve_team = "approve_team"
    delete_team = "delete_team"
    remove_team_member = "remove_team_member"
    add_team_member = "add_team_member"


class RequestStatusEnum(str, PyEnum):
    pendent = "pendent"
    approved = "approved"
    rejected = "rejected"


class Request(Base):
    __tablename__ = "requests"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_type: RequestTypeEnum = Column(SQLEnum(RequestTypeEnum), nullable=False)
    team_id: uuid.UUID = Column(UUID(as_uuid=True), nullable=False)
    competition_id: Optional[uuid.UUID] = Column(UUID(as_uuid=True), nullable=True)
    user_id: Optional[str] = Column(String, nullable=True)
    campus_code: str = Column(String(100), nullable=False)
    reason: Optional[str] = Column(String, nullable=True)
    reason_rejected: Optional[str] = Column(String, nullable=True)
    status: RequestStatusEnum = Column(
        SQLEnum(RequestStatusEnum),
        default=RequestStatusEnum.pendent,
        nullable=False
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class RequestsPutRequest(BaseModel):
    reason_rejected: Optional[str] = None
    status: RequestStatusEnum

class RequestsCreateRequest(BaseModel):
    request_type: RequestTypeEnum
    team_id: uuid.UUID
    user_id: Optional[str] = None
    reason: Optional[str] = None


class RequestsResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    user_id: Optional[str] = None
    campus_code: str
    request_type: RequestTypeEnum
    reason: Optional[str] = None
    reason_rejected: Optional[str] = None
    status: RequestStatusEnum
    created_at: datetime

    model_config = {
        "from_attributes": True
    }