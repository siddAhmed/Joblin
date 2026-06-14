import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class AtsType(str, enum.Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    workable = "workable"
    smartrecruiters = "smartrecruiters"
    workday = "workday"
    crawl4ai = "crawl4ai"
    custom = "custom"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    careers_url: Mapped[str] = mapped_column(String, nullable=False)
    ats_type: Mapped[AtsType] = mapped_column(Enum(AtsType), nullable=False)
    ats_identifier: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_api_url: Mapped[str | None] = mapped_column(String, nullable=True)
    css_selector: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quarantine_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quarantine_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
