import re
from urllib.parse import urlparse

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError

RESERVED = {
    "api", "dashboard", "healthz", "readyz", "links", "login", "logout",
    "privacy", "terms", "users", "settings", "static", "admin", "rest",
}


def valid_url(_form, field):
    value = field.data.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Enter a complete URL beginning with http:// or https://.")


def valid_tag(_form, field):
    value = field.data.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,64}", value):
        raise ValidationError("Use 2–64 letters, numbers, hyphens, or underscores.")
    if value.lower() in RESERVED:
        raise ValidationError("This tag is reserved. Choose another tag.")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")


class CreateLinkForm(FlaskForm):
    destination_url = TextAreaField("Destination URL", validators=[DataRequired(), valid_url])
    custom_tag = StringField("My tag", validators=[DataRequired(), valid_tag])
    submit = SubmitField("Create short link")


class EditLinkForm(FlaskForm):
    destination_url = TextAreaField("Destination URL", validators=[DataRequired(), valid_url])
    submit = SubmitField("Save destination")


class UserForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(min=2, max=120)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=255)])
    role = SelectField(
        "Role",
        choices=[("admin", "Administrator"), ("analyst", "Analyst"), ("viewer", "Viewer")],
    )
    password = PasswordField("Temporary password", validators=[Optional(), Length(min=12, max=256)])
    must_change_password = BooleanField("Require password change at next sign-in", default=True)
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save user")


class PasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), Length(min=12, max=256)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("new_password")]
    )
    submit = SubmitField("Change password")


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField("New temporary password", validators=[DataRequired(), Length(min=12, max=256)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("new_password")]
    )
    require_change = BooleanField("Require password change at next sign-in", default=True)
    submit = SubmitField("Reset password")
