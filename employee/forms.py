from flask_wtf import FlaskForm
from wtforms import DateField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError

from models import LEAVE_TYPE_CHOICES


class EmployeeLoginForm(FlaskForm):
    identifier = StringField("Username or Email", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=256)])
    submit = SubmitField("Login")


class PunchInForm(FlaskForm):
    pass


class PunchOutForm(FlaskForm):
    daily_summary = TextAreaField("Daily Summary", validators=[DataRequired(), Length(min=10, max=2000)])


class LeaveRequestForm(FlaskForm):
    leave_type = SelectField("Leave Type", choices=LEAVE_TYPE_CHOICES, validators=[DataRequired()])
    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date", validators=[DataRequired()])
    reason = TextAreaField("Reason", validators=[DataRequired(), Length(min=5, max=1000)])
    submit = SubmitField("Submit Request")

    def validate_end_date(self, field):
        if self.start_date.data and field.data < self.start_date.data:
            raise ValidationError("End date cannot be before the start date.")
