from flask_wtf import FlaskForm
# ← add this import
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, \
    TextAreaField, IntegerField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, \
    Length, NumberRange, Optional
import sqlalchemy as sa
from app import db
from app.models import User


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Please use a different email address.')


class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Request Password Reset')


class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    about_me = TextAreaField('About me', validators=[Length(min=0, max=140)])
    # ← NEW field for profile picture
    picture = FileField(
        'Update Profile Picture',
        validators=[FileAllowed(['jpg', 'jpeg', 'png']), Optional()]
    )
    submit = SubmitField('Submit')

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = db.session.scalar(sa.select(User).where(
                User.username == username.data))
            if user is not None:
                raise ValidationError('Please use a different username.')


class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')


class PostForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(), Length(max=140)])

    body = TextAreaField('Body', validators=[
        DataRequired(), Length(min=1, max=140)])

    progress = IntegerField('Progress', validators=[
        DataRequired(), NumberRange(min=0, max=100)])

    image = FileField('Upload Image', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])

    submit = SubmitField('Submit')

class UploadImageForm(FlaskForm):
    image = FileField('Upload Image', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])
    submit = SubmitField('Upload Image')


# ← NEW form for quest creation, with image upload
class QuestForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(), Length(max=140)])

    body = TextAreaField('Body', validators=[
        DataRequired(), Length(min=1, max=140)])

    progress = IntegerField('Progress', validators=[
        DataRequired(), NumberRange(min=0, max=100)])

    image = FileField(
        'Quest Image',
        validators=[FileAllowed(['jpg', 'jpeg', 'png']), Optional()]
    )

    submit = SubmitField('Create Quest')
