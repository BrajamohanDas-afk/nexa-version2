from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField,
    BooleanField, SubmitField, HiddenField, PasswordField, DateField,
    DecimalField, SelectMultipleField
)
from wtforms.validators import DataRequired, Email, EqualTo, InputRequired, Length, Optional, ValidationError
from flask_wtf.file import FileField, FileAllowed

from models import (
    DOCUMENT_TYPE_CHOICES,
    LEAVE_STATUS_CHOICES,
    PROJECT_STATUS_CHOICES,
    JOB_TYPE_CHOICES,
    REMOTE_TYPE_CHOICES,
    APPLICATION_STATUS_CHOICES,
)


class BlogForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=255)])
    slug = StringField("Slug", validators=[DataRequired(), Length(max=300)])

    summary = TextAreaField("Summary", validators=[DataRequired()])
    content = HiddenField("Content")
    author_name = StringField("Author Name", validators=[DataRequired()])

    category_id = SelectField('Category', coerce=str, validators=[DataRequired()])

    featured_image = FileField(
        "Featured Image",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only")]
    )
    featured_image_alt = StringField(
        "Featured Image Alt Text",
        validators=[Optional(), Length(max=255)]
    )

    # ── SEO ──
    seo_title = StringField(
        "SEO Title",
        validators=[Optional(), Length(max=255)]
    )
    seo_description = TextAreaField(
        "Meta Description",
        validators=[Optional(), Length(max=300)]
    )
    seo_keywords = TextAreaField(
        "Focus Keywords",
        validators=[Optional()]
    )

    is_published = BooleanField("Publish now")

    submit = SubmitField("Save Blog")


class EmployeeForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    role = StringField("Role", validators=[Optional(), Length(max=120)])
    department = StringField("Department", validators=[Optional(), Length(max=120)])
    assigned_project_name = StringField(
        "Assigned Project",
        validators=[Optional(), Length(max=255)]
    )
    project_ids = SelectMultipleField("Assigned Projects", coerce=int, validators=[Optional()])
    account_start_date = DateField("Account Start Date", validators=[DataRequired()])
    account_expiry_date = DateField("Account Expiry Date", validators=[Optional()])
    is_active = BooleanField("Account active")
    password = PasswordField("Password", validators=[Optional(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[Optional(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Save Employee")

    def validate_account_expiry_date(self, field):
        if field.data and self.account_start_date.data and field.data < self.account_start_date.data:
            raise ValidationError("Expiry date cannot be before the account start date.")


class AdminLoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=256)])
    submit = SubmitField("Login")


class DeleteForm(FlaskForm):
    pass


class LeaveReviewForm(FlaskForm):
    status = SelectField("Status", choices=LEAVE_STATUS_CHOICES, validators=[DataRequired()])
    admin_remarks = TextAreaField("Admin Remarks", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Save Review")


class ProjectForm(FlaskForm):
    name = StringField("Project Name", validators=[DataRequired(), Length(max=180)])
    client_name = StringField("Client Name", validators=[DataRequired(), Length(max=180)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])
    start_date = DateField("Start Date", validators=[DataRequired()])
    expected_end_date = DateField("Expected End Date", validators=[Optional()])
    status = SelectField("Project Status", choices=PROJECT_STATUS_CHOICES, validators=[DataRequired()])
    total_value = DecimalField("Total Project Value", places=2, validators=[InputRequired()])
    advance_received = DecimalField("Advance Received", places=2, validators=[InputRequired()])
    employee_ids = SelectMultipleField("Team Assignment", coerce=int, validators=[Optional()])
    document_type = SelectField("Document Type", choices=DOCUMENT_TYPE_CHOICES, validators=[Optional()])
    document_file = FileField(
        "Upload Document",
        validators=[FileAllowed(["pdf", "doc", "docx", "jpg", "jpeg", "png", "webp"], "Supported documents only")]
    )
    submit = SubmitField("Save Project")

    def validate_expected_end_date(self, field):
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError("Expected end date cannot be before the start date.")

    def validate_total_value(self, field):
        if field.data is not None and field.data < 0:
            raise ValidationError("Total project value cannot be negative.")

    def validate_advance_received(self, field):
        if field.data is not None and field.data < 0:
            raise ValidationError("Advance received cannot be negative.")

        if field.data is not None and self.total_value.data is not None and field.data > self.total_value.data:
            raise ValidationError("Advance received cannot exceed total project value.")


class CareerForm(FlaskForm):
    title = StringField("Job Title", validators=[DataRequired(), Length(max=180)])
    location = StringField("Location", validators=[DataRequired(), Length(max=120)])
    remote_type = SelectField("Work Mode", choices=REMOTE_TYPE_CHOICES, validators=[DataRequired()])
    job_type = SelectField("Job Type", choices=JOB_TYPE_CHOICES, validators=[DataRequired()])
    description = TextAreaField("Job Description", validators=[DataRequired()])
    requirements = TextAreaField("Requirements", validators=[DataRequired()])
    is_active = BooleanField("Listing active")
    submit = SubmitField("Save Job")


class JobApplicationReviewForm(FlaskForm):
    status = SelectField("Status", choices=APPLICATION_STATUS_CHOICES, validators=[DataRequired()])
    admin_notes = TextAreaField("Admin Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save Review")


class JobApplicationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    resume = FileField(
        "Resume / CV",
        validators=[FileAllowed(["pdf", "doc", "docx"], "PDF or Word documents only")]
    )
    cover_letter = TextAreaField("Cover Letter", validators=[Optional()])

    # Screening questions
    why_nexa = TextAreaField("Why do you want to work at Nexa Solutions?", validators=[DataRequired()])
    relevant_project = TextAreaField("Describe a project you're proud of and your role in it.", validators=[DataRequired()])
    salary_expectation = StringField("Salary Expectation", validators=[Optional(), Length(max=120)])
    notice_period = StringField("Notice Period / Availability (in days)", validators=[Optional(), Length(max=120)])

    submit = SubmitField("Submit Application")
