import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Enum, ForeignKey,
    DateTime, ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    company = Column(Text, nullable=False)
    url = Column(Text, unique=True, nullable=False)
    source = Column(
        Enum("naukri", "linkedin", "greenhouse", "lever", "career_page",
             name="job_source", create_type=False),
        nullable=False,
    )
    jd_text = Column(Text)
    location = Column(Text)
    geo_region = Column(
        Enum("india", "singapore", "uk", "saudi_arabia", "new_zealand",
             "australia", "netherlands", "remote", "other",
             name="geo_region", create_type=False),
    )
    requires_sponsorship = Column(Boolean)
    ats_type = Column(
        Enum("naukri", "greenhouse", "lever", "workday", "unknown",
             name="ats_type", create_type=False),
        nullable=False,
        server_default="unknown",
    )
    status = Column(
        Enum("scraped", "keyword_passed", "keyword_failed",
             "scored", "scored_low",
             "resume_assigned", "ready_to_apply", "ready_for_manual_apply",
             "submitted", "failed", "skipped",
             name="job_status", create_type=False),
        nullable=False,
        server_default="scraped",
    )
    keyword_score = Column(Integer)
    claude_score = Column(Integer)
    claude_reason = Column(Text)
    resume_variant = Column(
        Enum("backend", "qa", name="resume_variant", create_type=False),
    )
    discovered_sources = Column(ARRAY(String), server_default="{}")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    applications = relationship("Application", back_populates="job")

    def __repr__(self):
        return f"<Job {self.title} @ {self.company} [{self.status}]>"


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status = Column(
        Enum("submitted", "failed", "interview", "rejected", "offer",
             name="application_status", create_type=False),
        nullable=False,
    )
    resume_path = Column(Text)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    error_log = Column(Text)
    screenshot_path = Column(Text)

    job = relationship("Job", back_populates="applications")

    def __repr__(self):
        return f"<Application {self.job_id} [{self.status}]>"
