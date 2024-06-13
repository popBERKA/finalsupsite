from flask import flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, ValidationError, SelectField
from wtforms.validators import DataRequired, Email, EqualTo
from models import User
from flask_wtf.file import FileField, FileAllowed

class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    full_name = StringField('ФИО', validators=[DataRequired()])
    phone_number = StringField('Номер телефона', validators=[DataRequired()])
    email = StringField('Почта', validators=[DataRequired(), Email()])
    office_number = StringField('Номер кабинета', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    confirm_password = PasswordField('Подтверждение пароля', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Регистрация')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Этот логин уже используется.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Эта почта уже используется.')

    def validate_full_name(self, full_name):
        user = User.query.filter_by(full_name=full_name.data).first()
        if user:
            raise ValidationError('Это ФИО уже используется.')

class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class UpdateProfileForm(FlaskForm):
    full_name = StringField('ФИО', validators=[DataRequired()])
    phone_number = StringField('Номер телефона', validators=[DataRequired()])
    email = StringField('Почта', validators=[DataRequired(), Email()])
    office_number = StringField('Номер кабинета', validators=[DataRequired()])
    submit = SubmitField('Обновить профиль')

    def __init__(self, original_email, original_full_name, *args, **kwargs):
        super(UpdateProfileForm, self).__init__(*args, **kwargs)
        self.original_email = original_email
        self.original_full_name = original_full_name

    def validate_email(self, email):
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Эта почта уже используется.')

    def validate_full_name(self, full_name):
        if full_name.data != self.original_full_name:
            user = User.query.filter_by(full_name=full_name.data).first()
            if user:
                raise ValidationError('Это ФИО уже используется.')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Старый пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired()])
    confirm_new_password = PasswordField('Подтверждение нового пароля', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Изменить пароль')

class CreateRequestForm(FlaskForm):
    subject = StringField('Тема запроса', validators=[DataRequired()])
    message = TextAreaField('Текст запроса', validators=[DataRequired()])
    file = FileField('Прикрепить файл')
    submit = SubmitField('Создать запрос')

class CommentForm(FlaskForm):
    content = TextAreaField('', validators=[DataRequired()])
    submit = SubmitField('Добавить комментарий')
    
class RequestFilterForm(FlaskForm):
    status = SelectField('Статус', choices=[
        ('', 'Все'),
        ('Ожидает ответа', 'Ожидает ответа'),
        ('В работе', 'В работе'),
        ('Выполнен', 'Выполнен')
    ], default='')
    subject = StringField('Тема запроса')
    user = StringField('Пользователь')
    submit = SubmitField('Фильтр')