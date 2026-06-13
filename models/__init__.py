from extensions import db
import cloudinary
import cloudinary.uploader
import cloudinary.api
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
from .lead import ContactLead, ensure_contact_leads_table

__all__ = [
    "db",
    "BlogPost",
    "Category",
    "Employee",
    "AttendanceRecord",
    "ContactLead",
    "date_bounds",
    "ensure_attendance_tables",
    "format_duration",
    "seconds_on_date",
    "ensure_contact_leads_table"
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
