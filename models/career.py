from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, Boolean, text
from sqlalchemy.orm import relationship

from extensions import db


JOB_TYPE_CHOICES = (
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contract", "Contract"),
    ("internship", "Internship"),
)

REMOTE_TYPE_CHOICES = (
    ("remote", "Remote"),
    ("onsite", "On-site"),
    ("hybrid", "Hybrid"),
)

APPLICATION_STATUS_CHOICES = (
    ("new", "New"),
    ("reviewed", "Reviewed"),
    ("shortlisted", "Shortlisted"),
    ("rejected", "Rejected"),
    ("hired", "Hired"),
)


class CareerJob(db.Model):
    __tablename__ = "career_jobs"

    id = Column(Integer, primary_key=True)
    title = Column(String(180), nullable=False, index=True)
    slug = Column(String(220), unique=True, nullable=False, index=True)
    location = Column(String(120), nullable=False)
    remote_type = Column(String(30), nullable=False, default="remote")
    job_type = Column(String(30), nullable=False, default="full_time")
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    applications = relationship(
        "JobApplication",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobApplication.applied_at.desc()",
    )

    __table_args__ = (
        Index("idx_career_jobs_active", "is_active", "created_at"),
    )

    @property
    def job_type_label(self):
        return dict(JOB_TYPE_CHOICES).get(self.job_type, self.job_type)

    @property
    def remote_type_label(self):
        return dict(REMOTE_TYPE_CHOICES).get(self.remote_type, self.remote_type)

    def __repr__(self):
        return f"<CareerJob {self.title}>"


class JobApplication(db.Model):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("career_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50))
    resume_url = Column(String(500))
    cover_letter = Column(Text)

    # Screening questions
    why_nexa = Column(Text)
    relevant_project = Column(Text)
    salary_expectation = Column(String(120))
    notice_period = Column(String(120))

    status = Column(String(30), nullable=False, default="new", index=True)
    applied_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    admin_notes = Column(Text)

    job = relationship("CareerJob", back_populates="applications")

    __table_args__ = (
        Index("idx_job_applications_status", "status", "applied_at"),
    )

    @property
    def status_label(self):
        return dict(APPLICATION_STATUS_CHOICES).get(self.status, self.status)

    def __repr__(self):
        return f"<JobApplication {self.email} for {self.job_id}>"


def job_type_label(job_type):
    return dict(JOB_TYPE_CHOICES).get(job_type, job_type)


def remote_type_label(remote_type):
    return dict(REMOTE_TYPE_CHOICES).get(remote_type, remote_type)


def application_status_label(status):
    return dict(APPLICATION_STATUS_CHOICES).get(status, status)


def ensure_career_tables():
    CareerJob.__table__.create(bind=db.engine, checkfirst=True)
    JobApplication.__table__.create(bind=db.engine, checkfirst=True)

    job_column_sql = {
        "title": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS title VARCHAR(180)",
        "slug": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS slug VARCHAR(220)",
        "location": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS location VARCHAR(120)",
        "remote_type": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS remote_type VARCHAR(30) NOT NULL DEFAULT 'remote'",
        "job_type": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS job_type VARCHAR(30) NOT NULL DEFAULT 'full_time'",
        "description": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS description TEXT",
        "requirements": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS requirements TEXT",
        "is_active": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "created_at": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }
    application_column_sql = {
        "job_id": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS job_id INTEGER",
        "full_name": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS full_name VARCHAR(120)",
        "email": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
        "phone": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS phone VARCHAR(50)",
        "resume_url": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS resume_url VARCHAR(500)",
        "cover_letter": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS cover_letter TEXT",
        "why_nexa": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS why_nexa TEXT",
        "relevant_project": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS relevant_project TEXT",
        "salary_expectation": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS salary_expectation VARCHAR(120)",
        "notice_period": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS notice_period VARCHAR(120)",
        "status": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'new'",
        "applied_at": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "reviewed_at": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP",
        "admin_notes": "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS admin_notes TEXT",
    }

    with db.engine.begin() as connection:
        for sql in job_column_sql.values():
            connection.execute(text(sql))
        for sql in application_column_sql.values():
            connection.execute(text(sql))
