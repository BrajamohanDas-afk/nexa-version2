from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField,
    BooleanField, SubmitField, HiddenField, PasswordField, DateField
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from flask_wtf.file import FileField, FileAllowed


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
