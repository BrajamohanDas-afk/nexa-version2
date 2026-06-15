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

__all__ = [
    "db",
    "BlogPost",
    "Category",
    "Employee",
    "AttendanceRecord",
    "Project",
    "ProjectDocument",
    "ContactLead",
    "DOCUMENT_TYPE_CHOICES",
    "PROJECT_STATUS_CHOICES",
    "date_bounds",
    "ensure_attendance_tables",
    "ensure_project_tables",
    "format_money",
    "format_duration",
    "payment_status_label",
    "project_status_label",
    "seconds_on_date",
    "ensure_contact_leads_table",
    "upload_project_document",
    "signed_project_document_url",
]

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
