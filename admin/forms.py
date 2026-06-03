from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField,
    BooleanField, SubmitField, HiddenField
)
from wtforms.validators import DataRequired, Length, Optional
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
