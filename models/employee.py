from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Index, Integer, String
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class Employee(db.Model):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(50))
    role = Column(String(120))
    department = Column(String(120))
    account_start_date = Column(Date, nullable=False, default=date.today)
    account_expiry_date = Column(Date)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    assigned_project_name = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    attendance_records = relationship(
        "AttendanceRecord",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    projects = relationship(
        "Project",
        secondary="project_employees",
        back_populates="team_members",
    )

    __table_args__ = (
        Index("idx_employee_account_dates", "account_start_date", "account_expiry_date"),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def account_status_label(self):
        today = date.today()

        if not self.is_active:
            return "Inactive"

        if self.account_start_date and self.account_start_date > today:
            return "Scheduled"

        if self.account_expiry_date and self.account_expiry_date < today:
            return "Expired"

        return "Active"
