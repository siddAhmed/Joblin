import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class MatchTier(str, enum.Enum):
    strong = "strong"
    borderline = "borderline"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, unique=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[MatchTier] = mapped_column(Enum(MatchTier), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    filter_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    not_interested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
