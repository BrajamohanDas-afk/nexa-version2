from datetime import date, datetime

from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import or_

from extensions import db
from models import (
    AttendanceRecord,
    Employee,
    date_bounds,
    ensure_attendance_tables,
    format_duration,
    seconds_on_date,
)
from .forms import PunchForm


employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


class EmployeeSessionUser:
    def __init__(self, employee):
        self.employee = employee
        self.id = f"employee:{employee.id}"

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return get_employee_access_error(self.employee) is None

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id


def get_employee_access_error(employee):
    today = date.today()

    if not employee.is_active:
        return "Your account is inactive. Please contact the admin."

    if employee.account_start_date and employee.account_start_date > today:
        return "Your account is not active yet. Please contact the admin."

    if employee.account_expiry_date and employee.account_expiry_date < today:
        return "Your account has expired. Please contact the admin."

    return None


def employee_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        employee = getattr(current_user, "employee", None)
        if not current_user.is_authenticated or not employee:
            return redirect(url_for("employee.login"))

        access_error = get_employee_access_error(employee)
        if access_error:
            logout_user()
            flash(access_error, "error")
            return redirect(url_for("employee.login"))

        return view(*args, **kwargs)

    return wrapped


@employee_bp.route("")
@employee_bp.route("/")
def index():
    employee = getattr(current_user, "employee", None)
    if current_user.is_authenticated and employee:
        access_error = get_employee_access_error(employee)
        if access_error:
            logout_user()
            flash(access_error, "error")
            return redirect(url_for("employee.login"))
        return redirect(url_for("employee.dashboard"))

    return redirect(url_for("employee.login"))


@employee_bp.route("/login", methods=["GET", "POST"])
def login():
    if getattr(current_user, "employee", None):
        return redirect(url_for("employee.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        employee = Employee.query.filter(
            or_(
                Employee.username == identifier,
                Employee.email == identifier.lower(),
            )
        ).first()

        if not employee or not employee.check_password(password):
            flash("Invalid login credentials.", "error")
            return render_template("employee/login.html")

        access_error = get_employee_access_error(employee)
        if access_error:
            flash(access_error, "error")
            return render_template("employee/login.html")

        login_user(EmployeeSessionUser(employee))
        return redirect(url_for("employee.dashboard"))

    return render_template("employee/login.html")


@employee_bp.route("/logout")
@employee_login_required
def logout():
    logout_user()
    return redirect(url_for("employee.login"))


@employee_bp.route("/dashboard")
@employee_login_required
def dashboard():
    ensure_attendance_tables()
    employee = current_user.employee
    today = date.today()
    open_attendance = get_open_attendance(employee.id)
    today_start, tomorrow_start = date_bounds(today)
    today_records = (
        AttendanceRecord.query
        .filter(AttendanceRecord.employee_id == employee.id)
        .filter(AttendanceRecord.check_in_at < tomorrow_start)
        .filter(
            or_(
                AttendanceRecord.check_out_at.is_(None),
                AttendanceRecord.check_out_at >= today_start,
            )
        )
        .order_by(AttendanceRecord.check_in_at.desc())
        .all()
    )
    today_seconds = sum(seconds_on_date(record, today) for record in today_records)

    return render_template(
        "employee/dashboard.html",
        employee=employee,
        open_attendance=open_attendance,
        today_records=today_records,
        today_total_hours=format_duration(today_seconds),
        punch_form=PunchForm(),
    )


def get_open_attendance(employee_id):
    return (
        AttendanceRecord.query
        .filter_by(employee_id=employee_id, status="checked_in", check_out_at=None)
        .order_by(AttendanceRecord.check_in_at.desc())
        .first()
    )


@employee_bp.route("/attendance")
@employee_login_required
def attendance_history():
    ensure_attendance_tables()
    records = (
        AttendanceRecord.query
        .filter_by(employee_id=current_user.employee.id)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.check_in_at.desc())
        .limit(100)
        .all()
    )
    return render_template("employee/attendance.html", records=records)


@employee_bp.route("/attendance/punch-in", methods=["POST"])
@employee_login_required
def punch_in():
    ensure_attendance_tables()
    employee = current_user.employee
    form = PunchForm()

    if not form.validate_on_submit():
        flash("Attendance action could not be verified. Please try again.", "error")
        return redirect(url_for("employee.dashboard"))

    if get_open_attendance(employee.id):
        flash("You are already punched in.", "warning")
        return redirect(url_for("employee.dashboard"))

    now = datetime.now()
    record = AttendanceRecord(
        employee_id=employee.id,
        attendance_date=now.date(),
        check_in_at=now,
        status="checked_in",
    )
    db.session.add(record)
    db.session.commit()
    flash("Punch in recorded.", "success")
    return redirect(url_for("employee.dashboard"))


@employee_bp.route("/attendance/punch-out", methods=["POST"])
@employee_login_required
def punch_out():
    ensure_attendance_tables()
    form = PunchForm()

    if not form.validate_on_submit():
        flash("Attendance action could not be verified. Please try again.", "error")
        return redirect(url_for("employee.dashboard"))

    record = get_open_attendance(current_user.employee.id)

    if not record:
        flash("No active punch in found.", "warning")
        return redirect(url_for("employee.dashboard"))

    record.close()
    db.session.commit()
    flash("Punch out recorded.", "success")
    return redirect(url_for("employee.dashboard"))
