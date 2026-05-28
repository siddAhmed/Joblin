import enum
from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CompanyResultStatus(str, enum.Enum):
    scraping = "scraping"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.running)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    company_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    total_passed_heuristic: Mapped[int] = mapped_column(Integer, default=0)
    total_confirmed: Mapped[int] = mapped_column(Integer, default=0)
    total_notified: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class RunCompanyResult(Base):
    __tablename__ = "run_company_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    status: Mapped[CompanyResultStatus] = mapped_column(
        Enum(CompanyResultStatus), default=CompanyResultStatus.scraping
    )
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    passed_heuristic: Mapped[int] = mapped_column(Integer, default=0)
    confirmed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
