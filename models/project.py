from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from extensions import db


project_employees = Table(
    "project_employees",
    db.metadata,
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("employee_id", Integer, ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
)


class Project(db.Model):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(180), nullable=False, index=True)
    client_name = Column(String(180), nullable=False, index=True)
    description = Column(Text)
    start_date = Column(Date, nullable=False, default=date.today)
    expected_end_date = Column(Date)
    status = Column(String(30), nullable=False, default="active", index=True)
    total_value = Column(Numeric(12, 2), nullable=False, default=0)
    advance_received = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    team_members = relationship(
        "Employee",
        secondary=project_employees,
        back_populates="projects",
    )
    documents = relationship(
        "ProjectDocument",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectDocument.created_at.desc()",
    )

    __table_args__ = (
        Index("idx_projects_status_dates", "status", "start_date", "expected_end_date"),
        Index("idx_projects_payment", "total_value", "advance_received"),
    )

    @property
    def remaining_amount(self):
        remaining = decimal_or_zero(self.total_value) - decimal_or_zero(self.advance_received)
        return max(Decimal("0.00"), remaining)

    @property
    def total_value_label(self):
        return format_money(self.total_value)

    @property
    def advance_received_label(self):
        return format_money(self.advance_received)

    @property
    def remaining_amount_label(self):
        return format_money(self.remaining_amount)

    @property
    def payment_status(self):
        total_value = decimal_or_zero(self.total_value)
        advance_received = decimal_or_zero(self.advance_received)

        if total_value <= 0:
            return "unpaid"

        if self.remaining_amount <= 0:
            return "paid"

        if advance_received > 0:
            return "partial"

        return "unpaid"

    @property
    def status_label(self):
        return project_status_label(self.status)

    @property
    def payment_status_label(self):
        return payment_status_label(self.payment_status)


class ProjectDocument(db.Model):
    __tablename__ = "project_documents"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(50), nullable=False, default="supporting")
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    cloudinary_public_id = Column(String(255))
    cloudinary_resource_type = Column(String(30), nullable=False, default="raw")
    cloudinary_delivery_type = Column(String(30), nullable=False, default="private")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")


PROJECT_STATUS_CHOICES = (
    ("active", "Active"),
    ("completed", "Completed"),
    ("on_hold", "On Hold"),
    ("cancelled", "Cancelled"),
)

DOCUMENT_TYPE_CHOICES = (
    ("contract", "Contract"),
    ("proposal", "Proposal"),
    ("supporting", "Supporting Document"),
)


def decimal_or_zero(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(Decimal("0.01"))


def format_money(value):
    return f"{decimal_or_zero(value):,.2f}"


def project_status_label(status):
    return dict(PROJECT_STATUS_CHOICES).get(status, "Unknown")


def payment_status_label(status):
    return {
        "paid": "Paid",
        "partial": "Partial",
        "unpaid": "Unpaid",
    }.get(status, "Unknown")


def ensure_project_tables():
    Project.__table__.create(bind=db.engine, checkfirst=True)
    project_employees.create(bind=db.engine, checkfirst=True)
    ProjectDocument.__table__.create(bind=db.engine, checkfirst=True)

    project_column_sql = {
        "name": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS name VARCHAR(180)",
        "client_name": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_name VARCHAR(180)",
        "description": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS description TEXT",
        "start_date": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS start_date DATE",
        "expected_end_date": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS expected_end_date DATE",
        "status": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active'",
        "total_value": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS total_value NUMERIC(12, 2) NOT NULL DEFAULT 0",
        "advance_received": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS advance_received NUMERIC(12, 2) NOT NULL DEFAULT 0",
        "created_at": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "ALTER TABLE projects ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }
    document_column_sql = {
        "project_id": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS project_id INTEGER",
        "document_type": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS document_type VARCHAR(50) NOT NULL DEFAULT 'supporting'",
        "file_name": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS file_name VARCHAR(255)",
        "file_url": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS file_url VARCHAR(500)",
        "cloudinary_public_id": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS cloudinary_public_id VARCHAR(255)",
        "cloudinary_resource_type": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS cloudinary_resource_type VARCHAR(30) NOT NULL DEFAULT 'raw'",
        "cloudinary_delivery_type": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS cloudinary_delivery_type VARCHAR(30) NOT NULL DEFAULT 'private'",
        "created_at": "ALTER TABLE project_documents ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    with db.engine.begin() as connection:
        for sql in project_column_sql.values():
            connection.execute(text(sql))
        for sql in document_column_sql.values():
            connection.execute(text(sql))
