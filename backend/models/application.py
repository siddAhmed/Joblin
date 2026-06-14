import enum
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from backend.database import Base


class ApplicationStatus(str, enum.Enum):
    interested = "interested"
    applied = "applied"
    rejected = "rejected"
    offer = "offer"


class ApplicationSource(str, enum.Enum):
    joblin = "joblin"
    external = "external"


class ApplicationTracking(Base):
    __tablename__ = "application_tracking"
    __table_args__ = (UniqueConstraint("job_id", name="uq_application_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), nullable=False)
    source: Mapped[ApplicationSource] = mapped_column(Enum(ApplicationSource), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
