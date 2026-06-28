from extensions import db
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url
import os

# Import models so SQLAlchemy registers them
from .blog import (
    BlogPost,
    Category
)
from .employee import Employee
from .attendance import (
    AttendanceRecord,
    date_bounds,
    ensure_attendance_tables,
    format_duration,
    seconds_on_date,
)
from .leave import (
    LEAVE_STATUS_CHOICES,
    LEAVE_TYPE_CHOICES,
    LeaveRequest,
    ensure_leave_tables,
    leave_status_label,
    leave_type_label,
)
from .project import (
    DOCUMENT_TYPE_CHOICES,
    PROJECT_STATUS_CHOICES,
    Project,
    ProjectDocument,
    ensure_project_tables,
    format_money,
    payment_status_label,
    project_status_label,
)
from .lead import ContactLead, ensure_contact_leads_table
from .career import (
    CareerJob,
    JobApplication,
    JOB_TYPE_CHOICES,
    REMOTE_TYPE_CHOICES,
    APPLICATION_STATUS_CHOICES,
    ensure_career_tables,
    job_type_label,
    remote_type_label,
    application_status_label,
)

__all__ = [
    "db",
    "BlogPost",
    "Category",
    "Employee",
    "AttendanceRecord",
    "LeaveRequest",
    "Project",
    "ProjectDocument",
    "ContactLead",
    "CareerJob",
    "JobApplication",
    "DOCUMENT_TYPE_CHOICES",
    "LEAVE_STATUS_CHOICES",
    "LEAVE_TYPE_CHOICES",
    "PROJECT_STATUS_CHOICES",
    "JOB_TYPE_CHOICES",
    "REMOTE_TYPE_CHOICES",
    "APPLICATION_STATUS_CHOICES",
    "date_bounds",
    "ensure_attendance_tables",
    "ensure_leave_tables",
    "ensure_project_tables",
    "ensure_all_tables",
    "ensure_career_tables",
    "format_money",
    "format_duration",
    "leave_status_label",
    "leave_type_label",
    "payment_status_label",
    "project_status_label",
    "application_status_label",
    "job_type_label",
    "remote_type_label",
    "seconds_on_date",
    "ensure_contact_leads_table",
    "upload_project_document",
    "signed_project_document_url",
    "upload_blog_image",
    "upload_resume",
]


def ensure_all_tables():
    """Ensure all application tables exist. Call once at startup."""
    db.create_all()

    # Best-effort migration of columns for older databases.
    # Some SQLite versions do not support ALTER TABLE ... IF NOT EXISTS,
    # so failures here are safe to ignore when tables already have the columns.
    migration_funcs = [
        ensure_contact_leads_table,
        ensure_attendance_tables,
        ensure_project_tables,
        ensure_leave_tables,
        ensure_career_tables,
    ]
    for migrate in migration_funcs:
        try:
            migrate()
        except Exception:
            db.session.rollback()

# ============================
# CLOUDINARY CONFIG
# ============================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# ============================
# IMAGE UPLOAD HELPER
# ============================
def upload_blog_image(file):
    """
    Uploads image to Cloudinary and returns secure URL
    """
    if not file:
        return None

    result = cloudinary.uploader.upload(
        file,
        folder="nexa-solutions/blogs",
        resource_type="image",
        overwrite=True
    )

    return result.get("secure_url")


def upload_project_document(file):
    if not file:
        return None

    result = cloudinary.uploader.upload(
        file,
        folder="nexa-solutions/projects",
        resource_type="raw",
        type="private",
        overwrite=False,
    )

    return result


def upload_resume(file):
    """Upload a resume/CV to Cloudinary and return the secure URL."""
    if not file:
        return None

    result = cloudinary.uploader.upload(
        file,
        folder="nexa-solutions/careers/resumes",
        resource_type="raw",
        overwrite=False,
    )

    return result.get("secure_url")


def signed_project_document_url(document, expires_at):
    if not document.cloudinary_public_id:
        return None

    url, _ = cloudinary_url(
        document.cloudinary_public_id,
        resource_type=document.cloudinary_resource_type or "raw",
        type=document.cloudinary_delivery_type or "private",
        sign_url=True,
        secure=True,
        expires_at=expires_at,
    )
    return url
