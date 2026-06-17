from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship

from extensions import db


LEAVE_TYPE_CHOICES = (
    ("casual", "Casual Leave"),
    ("sick", "Sick Leave"),
    ("earned", "Earned Leave"),
    ("unpaid", "Unpaid Leave"),
    ("other", "Other"),
)

LEAVE_STATUS_CHOICES = (
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
)


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type = Column(String(30), nullable=False, default="casual")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending", index=True)
    admin_remarks = Column(Text)
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee", back_populates="leave_requests")

    __table_args__ = (
        Index("idx_leave_requests_status_dates", "status", "start_date", "end_date"),
    )

    @property
    def leave_type_label(self):
        return leave_type_label(self.leave_type)

    @property
    def status_label(self):
        return leave_status_label(self.status)

    @property
    def duration_days(self):
        if not self.start_date or not self.end_date:
            return 0

        return (self.end_date - self.start_date).days + 1


def leave_type_label(leave_type):
    return dict(LEAVE_TYPE_CHOICES).get(leave_type, "Other")


def leave_status_label(status):
    return dict(LEAVE_STATUS_CHOICES).get(status, "Unknown")


def ensure_leave_tables():
    LeaveRequest.__table__.create(bind=db.engine, checkfirst=True)

    column_sql = {
        "employee_id": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS employee_id INTEGER",
        "leave_type": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS leave_type VARCHAR(30) NOT NULL DEFAULT 'casual'",
        "start_date": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS start_date DATE",
        "end_date": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS end_date DATE",
        "reason": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS reason TEXT",
        "status": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'pending'",
        "admin_remarks": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS admin_remarks TEXT",
        "reviewed_at": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP",
        "created_at": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    with db.engine.begin() as connection:
        for sql in column_sql.values():
            connection.execute(text(sql))
