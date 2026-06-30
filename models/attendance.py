from datetime import date, datetime, time, timedelta

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship

from extensions import db


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, default=date.today, index=True)
    check_in_at = Column(DateTime, nullable=False, default=datetime.now)
    check_out_at = Column(DateTime)
    total_seconds = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="checked_in", index=True)
    daily_summary = Column(String(2000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    employee = relationship("Employee", back_populates="attendance_records")

    __table_args__ = (
        Index("idx_attendance_employee_date", "employee_id", "attendance_date"),
        Index("idx_attendance_status_date", "status", "attendance_date"),
    )

    @property
    def is_open(self):
        return self.status == "checked_in" and self.check_out_at is None

    @property
    def duration_seconds(self):
        if self.total_seconds:
            return self.total_seconds

        if self.check_in_at and self.check_out_at:
            return max(0, int((self.check_out_at - self.check_in_at).total_seconds()))

        if self.check_in_at and self.is_open:
            return max(0, int((datetime.now() - self.check_in_at).total_seconds()))

        return 0

    @property
    def duration_label(self):
        return format_duration(self.duration_seconds)

    def close(self, check_out_at=None):
        self.check_out_at = check_out_at or datetime.now()
        self.total_seconds = max(0, int((self.check_out_at - self.check_in_at).total_seconds()))
        self.status = "checked_out"


def format_duration(total_seconds):
    total_seconds = int(total_seconds or 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m"


def date_bounds(target_date):
    start_at = datetime.combine(target_date, time.min)
    end_at = start_at + timedelta(days=1)
    return start_at, end_at


def seconds_on_date(record, target_date):
    start_at, end_at = date_bounds(target_date)
    check_out_at = record.check_out_at or datetime.now()
    overlap_start = max(record.check_in_at, start_at)
    overlap_end = min(check_out_at, end_at)

    if overlap_end <= overlap_start:
        return 0

    return int((overlap_end - overlap_start).total_seconds())


def ensure_attendance_tables():
    AttendanceRecord.__table__.create(bind=db.engine, checkfirst=True)

    column_sql = {
        "employee_id": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS employee_id INTEGER",
        "attendance_date": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS attendance_date DATE",
        "check_in_at": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS check_in_at TIMESTAMP",
        "check_out_at": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS check_out_at TIMESTAMP",
        "total_seconds": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS total_seconds INTEGER NOT NULL DEFAULT 0",
        "status": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'checked_in'",
        "daily_summary": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS daily_summary VARCHAR(2000)",
        "created_at": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    with db.engine.begin() as connection:
        for sql in column_sql.values():
            connection.execute(text(sql))
