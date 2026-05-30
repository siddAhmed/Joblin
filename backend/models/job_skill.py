from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (
        UniqueConstraint("job_id", "skill_name", name="uq_job_skill"),
        Index("ix_job_skills_skill_name", "skill_name"),
        Index("ix_job_skills_job_id", "job_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    skill_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
