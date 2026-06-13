from flask import Blueprint, abort, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from models import (
    AttendanceRecord,
    BlogPost,
    Category,
    ContactLead,
    Employee,
    date_bounds,
    ensure_attendance_tables,
    ensure_contact_leads_table,
    format_duration,
    seconds_on_date,
    upload_blog_image,
)
from .forms import BlogForm, EmployeeForm
from .utils import generate_unique_slug
import re
import os
from datetime import date
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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
    if request.method == "POST":
        if (
            request.form["username"] == os.getenv("ADMIN_USERNAME")
            and request.form["password"] == os.getenv("ADMIN_PASSWORD")
        ):
            from app import AdminUser
            login_user(AdminUser())
            return redirect(url_for("admin.dashboard"))

        flash("Invalid credentials", "error")

    return render_template("admin/login.html")

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
        lead_count=ContactLead.query.count(),
        recent_leads=ContactLead.query.order_by(ContactLead.created_at.desc()).limit(5).all()
    )


def ensure_employee_tables():
    Employee.__table__.create(bind=db.engine, checkfirst=True)
    ensure_attendance_tables()


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
    return render_template("admin/employee_list.html", employees=employees)


@admin_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
def create_employee():
    ensure_employee_tables()
    form = EmployeeForm()

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

        try:
            db.session.add(employee)
            db.session.commit()
            flash("Employee account created successfully.", "success")
            return redirect(url_for("admin.employee_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Database Error: {str(e)}", "error")

    return render_template("admin/employee_form.html", form=form, is_edit=False)


@admin_bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
def edit_employee(employee_id):
    ensure_employee_tables()
    employee = Employee.query.get_or_404(employee_id)
    form = EmployeeForm(obj=employee)

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

        if form.password.data:
            employee.set_password(form.password.data)

        try:
            db.session.commit()
            flash("Employee account updated.", "success")
            return redirect(url_for("admin.employee_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Database Error: {str(e)}", "error")

    return render_template("admin/employee_form.html", form=form, is_edit=True)


@admin_bp.route("/employees/<int:employee_id>/delete", methods=["POST"])
@login_required
def delete_employee(employee_id):
    ensure_employee_tables()
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
            flash(f"Database Error: {str(e)}", "error")

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

