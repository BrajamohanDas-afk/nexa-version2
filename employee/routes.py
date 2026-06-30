from datetime import date, datetime

from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, session
from flask_login import current_user, login_user, logout_user
from sqlalchemy import or_

from extensions import db
from models import (
    AttendanceRecord,
    Employee,
    LeaveRequest,
    date_bounds,
    format_duration,
    seconds_on_date,
)
from .forms import EmployeeLoginForm, LeaveRequestForm, PunchInForm, PunchOutForm
from security_utils import employee_ip_login_limiter, employee_login_limiter, login_ip_key, login_rate_key


employee_bp = Blueprint("employee", __name__, url_prefix="/employee")
LEAVES_PER_PAGE = 20
ATTENDANCE_PER_PAGE = 25


def flash_employee_database_error(error, message="Sorry, there was a database problem. Please try again."):
    current_app.logger.exception("Employee database error: %s", error)
    flash(message, "error")


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

    form = EmployeeLoginForm()

    if form.validate_on_submit():
        identifier = form.identifier.data.strip()
        password = form.password.data
        rate_key = login_rate_key("employee", identifier, request.remote_addr)
        ip_rate_key = login_ip_key("employee", request.remote_addr)

        if employee_login_limiter.is_limited(rate_key) or employee_ip_login_limiter.is_limited(ip_rate_key):
            flash("Too many login attempts. Please try again later.", "error")
            return render_template("employee/login.html", form=form), 429

        employee = Employee.query.filter(
            or_(
                Employee.username == identifier,
                Employee.email == identifier.lower(),
            )
        ).first()

        if not employee or not employee.check_password(password):
            employee_login_limiter.record_failure(rate_key)
            employee_ip_login_limiter.record_failure(ip_rate_key)
            flash("Invalid login credentials.", "error")
            return render_template("employee/login.html", form=form)

        access_error = get_employee_access_error(employee)
        if access_error:
            employee_login_limiter.record_failure(rate_key)
            employee_ip_login_limiter.record_failure(ip_rate_key)
            flash(access_error, "error")
            return render_template("employee/login.html", form=form)

        session.clear()
        login_user(EmployeeSessionUser(employee))
        employee_login_limiter.reset(rate_key)
        employee_ip_login_limiter.reset(ip_rate_key)
        return redirect(url_for("employee.dashboard"))

    return render_template("employee/login.html", form=form)


@employee_bp.route("/logout")
@employee_login_required
def logout():
    logout_user()
    return redirect(url_for("employee.login"))


@employee_bp.route("/dashboard")
@employee_login_required
def dashboard():
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
        pending_leave_count=LeaveRequest.query.filter_by(employee_id=employee.id, status="pending").count(),
        recent_leave_requests=(
            LeaveRequest.query
            .filter_by(employee_id=employee.id)
            .order_by(LeaveRequest.created_at.desc())
            .limit(3)
            .all()
        ),
        punch_in_form=PunchInForm(),
        punch_out_form=PunchOutForm(),
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
    page = request.args.get("page", 1, type=int)
    pagination = (
        AttendanceRecord.query
        .filter_by(employee_id=current_user.employee.id)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.check_in_at.desc())
        .paginate(page=page, per_page=ATTENDANCE_PER_PAGE, error_out=False)
    )
    return render_template("employee/attendance.html", records=pagination.items, pagination=pagination)


@employee_bp.route("/leaves")
@employee_login_required
def leave_history():
    page = request.args.get("page", 1, type=int)
    pagination = (
        LeaveRequest.query
        .filter_by(employee_id=current_user.employee.id)
        .order_by(LeaveRequest.created_at.desc())
        .paginate(page=page, per_page=LEAVES_PER_PAGE, error_out=False)
    )
    return render_template(
        "employee/leave_history.html",
        leave_requests=pagination.items,
        pagination=pagination,
    )


@employee_bp.route("/leaves/new", methods=["GET", "POST"])
@employee_login_required
def create_leave_request():
    form = LeaveRequestForm()

    if form.validate_on_submit():
        leave_request = LeaveRequest(
            employee_id=current_user.employee.id,
            leave_type=form.leave_type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            reason=form.reason.data.strip(),
        )
        try:
            db.session.add(leave_request)
            db.session.commit()
            flash("Leave request submitted.", "success")
            return redirect(url_for("employee.leave_history"))
        except Exception as e:
            db.session.rollback()
            flash_employee_database_error(e)

    return render_template("employee/leave_form.html", form=form)


@employee_bp.route("/attendance/punch-in", methods=["POST"])
@employee_login_required
def punch_in():
    employee = current_user.employee
    form = PunchInForm()

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
    form = PunchOutForm()

    if not form.validate_on_submit():
        flash("Please provide your daily summary before punching out.", "error")
        return redirect(url_for("employee.dashboard"))

    record = get_open_attendance(current_user.employee.id)

    if not record:
        flash("No active punch in found.", "warning")
        return redirect(url_for("employee.dashboard"))

    record.daily_summary = form.daily_summary.data.strip()
    record.close()
    db.session.commit()
    flash("Punch out recorded.", "success")
    return redirect(url_for("employee.dashboard"))
