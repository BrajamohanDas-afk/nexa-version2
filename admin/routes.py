from flask import Blueprint, abort, current_app, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import current_user, login_user, logout_user, login_required
from models import (
    AttendanceRecord,
    BlogPost,
    Category,
    ContactLead,
    Employee,
    LEAVE_STATUS_CHOICES,
    LeaveRequest,
    Project,
    ProjectDocument,
    date_bounds,
    ensure_attendance_tables,
    ensure_contact_leads_table,
    ensure_leave_tables,
    ensure_project_tables,
    format_money,
    format_duration,
    seconds_on_date,
    signed_project_document_url,
    upload_project_document,
    upload_blog_image,
)
from .forms import AdminLoginForm, BlogForm, DeleteForm, EmployeeForm, LeaveReviewForm, ProjectForm
from .utils import generate_unique_slug
from security_utils import admin_ip_login_limiter, admin_login_limiter, login_ip_key, login_rate_key
from sqlalchemy import case
from sqlalchemy.orm import joinedload
import re
import os
from datetime import date, datetime, timedelta
from extensions import db
from werkzeug.utils import secure_filename

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_PROJECT_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png", "webp"}
PROJECTS_PER_PAGE = 20
LEAVES_PER_PAGE = 20


@admin_bp.before_request
def require_admin_user():
    if request.endpoint == "admin.login":
        return None

    if not current_user.is_authenticated:
        return redirect(url_for("admin.login"))

    if not getattr(current_user, "is_admin", False):
        abort(403)

    return None

# ============================
# LOGIN
# ============================
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    form = AdminLoginForm()

    if form.validate_on_submit():
        rate_key = login_rate_key("admin", form.username.data, request.remote_addr)
        ip_rate_key = login_ip_key("admin", request.remote_addr)
        if admin_login_limiter.is_limited(rate_key) or admin_ip_login_limiter.is_limited(ip_rate_key):
            flash("Too many login attempts. Please try again later.", "error")
            return render_template("admin/login.html", form=form), 429

        if verify_admin_credentials(form.username.data, form.password.data):
            from app import AdminUser
            session.clear()
            login_user(AdminUser())
            admin_login_limiter.reset(rate_key)
            admin_ip_login_limiter.reset(ip_rate_key)
            return redirect(url_for("admin.dashboard"))

        admin_login_limiter.record_failure(rate_key)
        admin_ip_login_limiter.record_failure(ip_rate_key)
        flash("Invalid credentials", "error")

    return render_template("admin/login.html", form=form)


def verify_admin_credentials(username, password):
    expected_username = os.getenv("ADMIN_USERNAME")
    plaintext_password = os.getenv("ADMIN_PASSWORD")

    if username != expected_username:
        return False

    return bool(plaintext_password) and password == plaintext_password


def flash_database_error(error, message="Sorry, there was a database problem. Please try again."):
    current_app.logger.exception("Admin database error: %s", error)
    flash(message, "error")

# ============================
# LOGOUT
# ============================
@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/#")

# ============================
# DASHBOARD
# ============================
@admin_bp.route("/")
@login_required
def dashboard():
    ensure_contact_leads_table()
    ensure_employee_tables()
    ensure_project_tables()
    ensure_leave_tables()
    today = date.today()
    today_start, tomorrow_start = date_bounds(today)
    today_records = (
        AttendanceRecord.query
        .filter(AttendanceRecord.check_in_at < tomorrow_start)
        .filter(
            db.or_(
                AttendanceRecord.check_out_at.is_(None),
                AttendanceRecord.check_out_at >= today_start,
            )
        )
        .all()
    )
    online_employee_count = (
        AttendanceRecord.query
        .filter_by(status="checked_in", check_out_at=None)
        .count()
    )
    checked_out_today_count = len({
        record.employee_id
        for record in today_records
        if record.status == "checked_out"
    })
    today_total_seconds = sum(seconds_on_date(record, today) for record in today_records)
    return render_template(
        "admin/dashboard.html",
        blog_count=BlogPost.query.count(),
        category_count=Category.query.count(),
        employee_count=Employee.query.count(),
        active_employee_count=Employee.query.filter_by(is_active=True).count(),
        online_employee_count=online_employee_count,
        checked_out_today_count=checked_out_today_count,
        today_total_hours=format_duration(today_total_seconds),
        project_count=Project.query.count(),
        active_project_count=Project.query.filter_by(status="active").count(),
        completed_project_count=Project.query.filter_by(status="completed").count(),
        outstanding_amount=format_money(sum_project_outstanding_amount()),
        pending_leave_count=LeaveRequest.query.filter_by(status="pending").count(),
        approved_leave_count=LeaveRequest.query.filter_by(status="approved").count(),
        rejected_leave_count=LeaveRequest.query.filter_by(status="rejected").count(),
        lead_count=ContactLead.query.count(),
        recent_leads=ContactLead.query.order_by(ContactLead.created_at.desc()).limit(5).all()
    )


def ensure_employee_tables():
    Employee.__table__.create(bind=db.engine, checkfirst=True)
    ensure_attendance_tables()
    ensure_project_tables()
    ensure_leave_tables()


def populate_employee_project_choices(form):
    ensure_project_tables()
    form.project_ids.choices = [
        (project.id, f"{project.name} - {project.client_name}")
        for project in Project.query.order_by(Project.name.asc()).all()
    ]


def validate_employee_uniqueness(form, employee_id=None):
    email_query = Employee.query.filter(Employee.email == form.email.data.strip().lower())
    username_query = Employee.query.filter(Employee.username == form.username.data.strip())

    if employee_id:
        email_query = email_query.filter(Employee.id != employee_id)
        username_query = username_query.filter(Employee.id != employee_id)

    is_valid = True

    if email_query.first():
        form.email.errors.append("An employee with this email already exists.")
        is_valid = False

    if username_query.first():
        form.username.errors.append("An employee with this username already exists.")
        is_valid = False

    return is_valid


@admin_bp.route("/leads")
@login_required
def lead_list():
    ensure_contact_leads_table()
    leads = ContactLead.query.order_by(ContactLead.created_at.desc()).all()
    return render_template("admin/lead_list.html", leads=leads)


@admin_bp.route("/employees")
@login_required
def employee_list():
    ensure_employee_tables()
    employees = Employee.query.order_by(Employee.created_at.desc()).all()
    return render_template("admin/employee_list.html", employees=employees, delete_form=DeleteForm())


@admin_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
def create_employee():
    ensure_employee_tables()
    form = EmployeeForm()
    populate_employee_project_choices(form)

    if request.method == "GET":
        form.account_start_date.data = date.today()
        form.is_active.data = True

    if form.validate_on_submit() and validate_employee_uniqueness(form):
        if not form.password.data:
            form.password.errors.append("Password is required for new employees.")
            return render_template("admin/employee_form.html", form=form, is_edit=False)

        employee = Employee(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            username=form.username.data.strip(),
            phone=(form.phone.data or "").strip() or None,
            role=(form.role.data or "").strip() or None,
            department=(form.department.data or "").strip() or None,
            assigned_project_name=(form.assigned_project_name.data or "").strip() or None,
            account_start_date=form.account_start_date.data,
            account_expiry_date=form.account_expiry_date.data,
            is_active=form.is_active.data,
        )
        employee.set_password(form.password.data)
        employee.projects = Project.query.filter(Project.id.in_(form.project_ids.data or [])).all()

        try:
            db.session.add(employee)
            db.session.commit()
            flash("Employee account created successfully.", "success")
            return redirect(url_for("admin.employee_list"))
        except Exception as e:
            db.session.rollback()
            flash_database_error(e)

    return render_template("admin/employee_form.html", form=form, is_edit=False)


@admin_bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
def edit_employee(employee_id):
    ensure_employee_tables()
    employee = Employee.query.get_or_404(employee_id)
    form = EmployeeForm(obj=employee)
    populate_employee_project_choices(form)

    if request.method == "GET":
        form.project_ids.data = [project.id for project in employee.projects]

    if form.validate_on_submit() and validate_employee_uniqueness(form, employee_id=employee.id):
        employee.full_name = form.full_name.data.strip()
        employee.email = form.email.data.strip().lower()
        employee.username = form.username.data.strip()
        employee.phone = (form.phone.data or "").strip() or None
        employee.role = (form.role.data or "").strip() or None
        employee.department = (form.department.data or "").strip() or None
        employee.assigned_project_name = (form.assigned_project_name.data or "").strip() or None
        employee.account_start_date = form.account_start_date.data
        employee.account_expiry_date = form.account_expiry_date.data
        employee.is_active = form.is_active.data
        employee.projects = Project.query.filter(Project.id.in_(form.project_ids.data or [])).all()

        if form.password.data:
            employee.set_password(form.password.data)

        try:
            db.session.commit()
            flash("Employee account updated.", "success")
            return redirect(url_for("admin.employee_list"))
        except Exception as e:
            db.session.rollback()
            flash_database_error(e)

    return render_template("admin/employee_form.html", form=form, is_edit=True)


@admin_bp.route("/employees/<int:employee_id>/delete", methods=["POST"])
@login_required
def delete_employee(employee_id):
    ensure_employee_tables()
    form = DeleteForm()
    if not form.validate_on_submit():
        flash("Employee delete action could not be verified. Please try again.", "error")
        return redirect(url_for("admin.employee_list"))

    employee = Employee.query.get_or_404(employee_id)
    db.session.delete(employee)
    db.session.commit()
    flash("Employee account deleted.", "success")
    return redirect(url_for("admin.employee_list"))


@admin_bp.route("/attendance")
@login_required
def attendance_overview():
    ensure_employee_tables()
    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    today = date.today()
    today_start, tomorrow_start = date_bounds(today)
    latest_records = (
        AttendanceRecord.query
        .order_by(AttendanceRecord.check_in_at.desc())
        .all()
    )
    latest_by_employee = {}
    for record in latest_records:
        latest_by_employee.setdefault(record.employee_id, record)

    today_records = (
        AttendanceRecord.query
        .filter(AttendanceRecord.check_in_at < tomorrow_start)
        .filter(
            db.or_(
                AttendanceRecord.check_out_at.is_(None),
                AttendanceRecord.check_out_at >= today_start,
            )
        )
        .all()
    )
    today_seconds_by_employee = {}
    for record in today_records:
        today_seconds_by_employee[record.employee_id] = (
            today_seconds_by_employee.get(record.employee_id, 0) + seconds_on_date(record, today)
        )

    attendance_rows = [
        {
            "employee": employee,
            "latest_record": latest_by_employee.get(employee.id),
            "today_total": format_duration(today_seconds_by_employee.get(employee.id, 0)),
        }
        for employee in employees
    ]
    return render_template("admin/attendance_overview.html", attendance_rows=attendance_rows)


@admin_bp.route("/attendance/reports")
@login_required
def attendance_reports():
    ensure_employee_tables()
    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    employee_id = request.args.get("employee_id", type=int)
    date_from_raw = request.args.get("date_from", "").strip()
    date_to_raw = request.args.get("date_to", "").strip()

    query = AttendanceRecord.query.join(Employee)

    if employee_id:
        query = query.filter(AttendanceRecord.employee_id == employee_id)

    date_from = parse_filter_date(date_from_raw, "from")
    if date_from:
        query = query.filter(AttendanceRecord.attendance_date >= date_from)

    date_to = parse_filter_date(date_to_raw, "to")
    if date_to:
        query = query.filter(AttendanceRecord.attendance_date <= date_to)

    if date_from and date_to and date_from > date_to:
        flash("The from date cannot be after the to date.", "error")
        records = []
    else:
        records = (
            query
            .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.check_in_at.desc())
            .all()
        )
    total_seconds = sum(record.duration_seconds for record in records)

    return render_template(
        "admin/attendance_reports.html",
        employees=employees,
        records=records,
        selected_employee_id=employee_id,
        date_from=date_from_raw,
        date_to=date_to_raw,
        total_hours=format_duration(total_seconds),
    )


def parse_filter_date(value, label):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        flash(f"The {label} date is invalid. Please use a valid date.", "error")
        return None


@admin_bp.route("/leaves")
@login_required
def leave_request_list():
    ensure_employee_tables()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)
    valid_statuses = {status for status, _ in LEAVE_STATUS_CHOICES}
    query = LeaveRequest.query.options(joinedload(LeaveRequest.employee)).join(Employee)

    if status_filter in valid_statuses:
        query = query.filter(LeaveRequest.status == status_filter)
    elif status_filter:
        flash("Unknown leave status filter.", "error")
        status_filter = ""

    pagination = query.order_by(LeaveRequest.created_at.desc()).paginate(
        page=page,
        per_page=LEAVES_PER_PAGE,
        error_out=False,
    )

    return render_template(
        "admin/leave_list.html",
        leave_requests=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
    )


@admin_bp.route("/leaves/<int:leave_id>", methods=["GET", "POST"])
@login_required
def review_leave_request(leave_id):
    ensure_employee_tables()
    leave_request = LeaveRequest.query.get_or_404(leave_id)
    form = LeaveReviewForm(obj=leave_request)

    if form.validate_on_submit():
        leave_request.status = form.status.data
        leave_request.admin_remarks = (form.admin_remarks.data or "").strip() or None
        leave_request.reviewed_at = datetime.utcnow()

        try:
            db.session.commit()
            flash("Leave request updated.", "success")
            return redirect(url_for("admin.leave_request_list"))
        except Exception as e:
            db.session.rollback()
            flash_database_error(e)

    return render_template("admin/leave_review.html", leave_request=leave_request, form=form)


def apply_project_payment_filter(query, payment_filter):
    if payment_filter == "paid":
        return query.filter(Project.total_value > 0, Project.advance_received >= Project.total_value)

    if payment_filter == "partial":
        return query.filter(Project.advance_received > 0, Project.advance_received < Project.total_value)

    if payment_filter == "unpaid":
        return query.filter(db.or_(Project.total_value <= 0, Project.advance_received <= 0))

    return query


def project_outstanding_filter(query):
    return query.filter(db.or_(Project.total_value <= 0, Project.advance_received < Project.total_value))


def sum_project_column(column):
    return db.session.query(db.func.coalesce(db.func.sum(column), 0)).scalar() or 0


def sum_project_outstanding_amount():
    remaining_amount = case(
        (Project.total_value > Project.advance_received, Project.total_value - Project.advance_received),
        else_=0,
    )
    return db.session.query(db.func.coalesce(db.func.sum(remaining_amount), 0)).scalar() or 0


@admin_bp.route("/projects")
@login_required
def project_list():
    ensure_employee_tables()
    status_filter = request.args.get("status", "").strip()
    payment_filter = request.args.get("payment", "").strip()
    page = request.args.get("page", 1, type=int)
    query = Project.query

    if status_filter:
        query = query.filter(Project.status == status_filter)

    if payment_filter:
        query = apply_project_payment_filter(query, payment_filter)

    pagination = query.order_by(Project.created_at.desc()).paginate(
        page=page,
        per_page=PROJECTS_PER_PAGE,
        error_out=False,
    )

    return render_template(
        "admin/project_list.html",
        projects=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
        payment_filter=payment_filter,
        delete_form=DeleteForm(),
    )


@admin_bp.route("/projects/dashboard")
@login_required
def project_dashboard():
    ensure_employee_tables()
    today = date.today()
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)

    return render_template(
        "admin/project_dashboard.html",
        total_projects=Project.query.count(),
        active_projects=Project.query.filter_by(status="active").count(),
        completed_projects=Project.query.filter_by(status="completed").count(),
        on_hold_projects=Project.query.filter_by(status="on_hold").count(),
        cancelled_projects=Project.query.filter_by(status="cancelled").count(),
        awaiting_payment_count=project_outstanding_filter(Project.query).count(),
        completed_pending_count=project_outstanding_filter(Project.query.filter_by(status="completed")).count(),
        monthly_projects=Project.query
            .filter(Project.start_date >= month_start)
            .filter(Project.start_date < next_month_start)
            .count(),
        total_value=format_money(sum_project_column(Project.total_value)),
        collected_amount=format_money(sum_project_column(Project.advance_received)),
        outstanding_amount=format_money(sum_project_outstanding_amount()),
        recent_projects=Project.query.order_by(Project.created_at.desc()).limit(6).all(),
    )


@admin_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def create_project():
    ensure_employee_tables()
    form = ProjectForm()
    populate_project_form_choices(form)

    if request.method == "GET":
        form.start_date.data = date.today()
        form.status.data = "active"
        form.total_value.data = 0
        form.advance_received.data = 0

    if form.validate_on_submit():
        project = Project(
            name=form.name.data.strip(),
            client_name=form.client_name.data.strip(),
            description=(form.description.data or "").strip() or None,
            start_date=form.start_date.data,
            expected_end_date=form.expected_end_date.data,
            status=form.status.data,
            total_value=form.total_value.data,
            advance_received=form.advance_received.data,
        )
        project.team_members = Employee.query.filter(Employee.id.in_(form.employee_ids.data or [])).all()

        try:
            db.session.add(project)
            db.session.flush()
            save_project_document(project, form)
            db.session.commit()
            flash("Project created successfully.", "success")
            return redirect(url_for("admin.project_list"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
        except Exception as e:
            db.session.rollback()
            flash_database_error(e)

    return render_template("admin/project_form.html", form=form, is_edit=False, project=None)


@admin_bp.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    ensure_employee_tables()
    project = Project.query.get_or_404(project_id)
    return render_template("admin/project_detail.html", project=project, delete_form=DeleteForm())


@admin_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    ensure_employee_tables()
    project = Project.query.get_or_404(project_id)
    form = ProjectForm(obj=project)
    populate_project_form_choices(form)

    if request.method == "GET":
        form.employee_ids.data = [employee.id for employee in project.team_members]

    if form.validate_on_submit():
        project.name = form.name.data.strip()
        project.client_name = form.client_name.data.strip()
        project.description = (form.description.data or "").strip() or None
        project.start_date = form.start_date.data
        project.expected_end_date = form.expected_end_date.data
        project.status = form.status.data
        project.total_value = form.total_value.data
        project.advance_received = form.advance_received.data
        project.team_members = Employee.query.filter(Employee.id.in_(form.employee_ids.data or [])).all()

        try:
            save_project_document(project, form)
            db.session.commit()
            flash("Project updated.", "success")
            return redirect(url_for("admin.project_detail", project_id=project.id))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
        except Exception as e:
            db.session.rollback()
            flash_database_error(e)

    return render_template("admin/project_form.html", form=form, is_edit=True, project=project)


@admin_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    ensure_employee_tables()
    form = DeleteForm()
    if not form.validate_on_submit():
        flash("Project delete action could not be verified. Please try again.", "error")
        return redirect(url_for("admin.project_list"))

    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "success")
    return redirect(url_for("admin.project_list"))


@admin_bp.route("/projects/<int:project_id>/documents/<int:document_id>/delete", methods=["POST"])
@login_required
def delete_project_document(project_id, document_id):
    ensure_employee_tables()
    form = DeleteForm()
    if not form.validate_on_submit():
        flash("Document delete action could not be verified. Please try again.", "error")
        return redirect(url_for("admin.project_detail", project_id=project_id))

    document = ProjectDocument.query.filter_by(id=document_id, project_id=project_id).first_or_404()
    db.session.delete(document)
    db.session.commit()
    flash("Project document removed.", "success")
    return redirect(url_for("admin.project_detail", project_id=project_id))


@admin_bp.route("/projects/<int:project_id>/documents/<int:document_id>/download")
@login_required
def download_project_document(project_id, document_id):
    ensure_employee_tables()
    document = ProjectDocument.query.filter_by(id=document_id, project_id=project_id).first_or_404()
    expires_at = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())
    signed_url = signed_project_document_url(document, expires_at)

    if not signed_url:
        flash("This document is unavailable. Please upload it again.", "error")
        return redirect(url_for("admin.project_detail", project_id=project_id))

    return redirect(signed_url)


def populate_project_form_choices(form):
    form.employee_ids.choices = [
        (employee.id, employee.full_name)
        for employee in Employee.query.order_by(Employee.full_name.asc()).all()
    ]


def save_project_document(project, form):
    if not form.document_file.data:
        return

    file = form.document_file.data
    file_name = secure_filename(file.filename or "project-document")
    validate_project_document_file(file, file_name)
    upload_result = upload_project_document(file)

    if not upload_result:
        return

    document = ProjectDocument(
        project=project,
        document_type=form.document_type.data or "supporting",
        file_name=file_name,
        file_url=upload_result.get("secure_url") or "",
        cloudinary_public_id=upload_result.get("public_id"),
        cloudinary_resource_type=upload_result.get("resource_type") or "raw",
        cloudinary_delivery_type=upload_result.get("type") or "private",
    )
    db.session.add(document)


def validate_project_document_file(file, file_name):
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in ALLOWED_PROJECT_DOCUMENT_EXTENSIONS:
        raise ValueError("Unsupported project document type.")

    header = file.stream.read(16)
    file.stream.seek(0)

    valid_signatures = {
        "pdf": header.startswith(b"%PDF-"),
        "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": header.startswith(b"\xff\xd8\xff"),
        "jpeg": header.startswith(b"\xff\xd8\xff"),
        "webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        "doc": header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        "docx": header.startswith(b"PK\x03\x04"),
    }

    if not valid_signatures.get(extension, False):
        raise ValueError("Uploaded document content does not match the selected file type.")

# ============================
# BLOG LIST
# ============================
@admin_bp.route("/blogs")
@login_required
def blog_list():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template("admin/blog_list.html", blogs=posts)

# ============================
# CREATE BLOG 
# ============================
@admin_bp.route("/blogs/new", methods=["GET", "POST"])
@login_required
def create_blog():
    form = BlogForm()
    # Populate category choices
    form.category_id.choices = [
        (str(c.id), c.name) for c in Category.query.order_by(Category.name).all()
    ]

    if form.validate_on_submit():
        content = request.form.get('content', '').strip()
        # Strip all HTML tags and check there is actual visible text
        if not re.sub(r'<[^>]+>', '', content).strip():
            flash("Blog content cannot be empty.", "error")
            return render_template("admin/blog_form.html", form=form, is_edit=False)

        # Handle Image Upload
        image_url = None
        if form.featured_image.data:
            image_url = upload_blog_image(form.featured_image.data)

        # Create the new record
        post = BlogPost(
            title=form.title.data,
            slug=generate_unique_slug(form.title.data),
            summary=form.summary.data,
            content=content,
            author_name=form.author_name.data,
            category_id=form.category_id.data,
            featured_image=image_url,
            featured_image_alt=form.featured_image_alt.data or None,
            seo_title=form.seo_title.data or None,
            seo_description=form.seo_description.data or None,
            seo_keywords=form.seo_keywords.data or None,
            is_published=form.is_published.data,
            published_at=db.func.now() if form.is_published.data else None,
        )

        try:
            db.session.add(post)
            db.session.commit()
            flash("Blog created successfully!", "success")
            return redirect(url_for("admin.blog_list"))
        except Exception as e:
            db.session.rollback()
            flash_database_error(e)

    else:
        print("VALIDATION FAILED!")
        print(form.errors)

    
    return render_template("admin/blog_form.html", form=form, is_edit=False)

# ============================
# EDIT BLOG
# ============================
@admin_bp.route("/blogs/<int:blog_id>/edit", methods=["GET", "POST"])
@login_required
def edit_blog(blog_id):
    post = BlogPost.query.get_or_404(blog_id)
    form = BlogForm(obj=post)

    form.category_id.choices = [
        (c.id, c.name) for c in Category.query.order_by(Category.name).all()
    ]

    if form.validate_on_submit():
        content = request.form.get('content', '').strip()
        if not re.sub(r'<[^>]+>', '', content).strip():
            flash("Blog content cannot be empty.", "error")
            return render_template("admin/blog_form.html", form=form, is_edit=True)

        post.title = form.title.data
        post.slug = generate_unique_slug(form.slug.data, post_id=post.id)
        post.summary = form.summary.data
        post.content = content
        post.author_name = form.author_name.data
        post.category_id = form.category_id.data
        post.featured_image_alt = form.featured_image_alt.data or None
        post.seo_title = form.seo_title.data or None
        post.seo_description = form.seo_description.data or None
        post.seo_keywords = form.seo_keywords.data or None
        post.is_published = form.is_published.data

        if form.is_published.data and not post.published_at:
            post.published_at = db.func.now()

        if form.featured_image.data:
            post.featured_image = upload_blog_image(form.featured_image.data)

        db.session.commit()
        flash("Blog updated", "success")
        return redirect(url_for("admin.blog_list"))

    return render_template("admin/blog_form.html", form=form, is_edit=True)

# ============================
# DELETE BLOG
# ============================
@admin_bp.route("/blogs/<int:blog_id>/delete", methods=["POST"])
@login_required
def delete_blog(blog_id):
    blog = BlogPost.query.get_or_404(blog_id)
    db.session.delete(blog)
    db.session.commit()
    flash("Blog deleted", "success")
    return redirect(url_for("admin.blog_list"))

@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
def manage_categories():
    if request.method == "POST":
        name = request.form.get("name")

        if not name:
            flash("Category name required", "error")
            return redirect(url_for("admin.manage_categories"))

        category = Category(name=name)
        db.session.add(category)
        db.session.commit()

        flash("Category added", "success")
        return redirect(url_for("admin.manage_categories"))

    categories = Category.query.all()
    return render_template("admin/categories.html", categories=categories)

@admin_bp.route("/categories/<uuid:id>/delete", methods=["POST"])
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)

    if category.posts:
        flash("Cannot delete category with blogs", "error")
        return redirect(url_for("admin.manage_categories"))

    db.session.delete(category)
    db.session.commit()

    flash("Category deleted", "success")
    return redirect(url_for("admin.manage_categories"))

# ============================
# QUILL IMAGE UPLOAD (AJAX)
# ============================
@admin_bp.route("/upload-image", methods=["POST"])
@login_required
def upload_image():
    """Upload an image from the Quill editor to Cloudinary."""
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "No image provided"}), 400

    try:
        url = upload_blog_image(file)
        return jsonify({"url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

