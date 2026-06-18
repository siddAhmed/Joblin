from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.company import AtsType


class CompanyCatalog(Base):
    __tablename__ = "company_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    careers_url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    ats_type: Mapped[AtsType | None] = mapped_column(Enum(AtsType), nullable=True)
    ats_identifier: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_api_url: Mapped[str | None] = mapped_column(String, nullable=True)
    css_selector: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quarantine_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quarantine_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    discovery_status: Mapped[str] = mapped_column(
        String, nullable=False, default="none", server_default="none"
    )
    discovery_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String, nullable=False, default="default", server_default="default"
    )
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
