from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
import os
from config import Config
from models import db, User, SupportRequest, Comment, Notification, UploadedFile
from forms import RegisterForm, LoginForm, UpdateProfileForm, CreateRequestForm, CommentForm, ChangePasswordForm
from io import BytesIO
import openpyxl

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    with app.app_context():
        return db.session.get(User, int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            phone_number=form.phone_number.data,
            email=form.email.data,
            office_number=form.office_number.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна! Можете войти.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Логин выполнен успешно!', 'success')
            return redirect(url_for('index'))
        flash('Неверное имя пользователя или пароль!', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Выход выполнен!', 'success')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_form = UpdateProfileForm(original_email=current_user.email, original_full_name=current_user.full_name, obj=current_user)
    if profile_form.validate_on_submit():
        current_user.full_name = profile_form.full_name.data
        current_user.phone_number = profile_form.phone_number.data
        current_user.email = profile_form.email.data
        current_user.office_number = profile_form.office_number.data
        db.session.commit()
        flash('Обновление профиля прошло успешно!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', profile_form=profile_form)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('Старый пароль неверен.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Пароль успешно изменен!', 'success')
            return redirect(url_for('profile'))
    return render_template('change_password.html', form=form)

@app.route('/create_request', methods=['GET', 'POST'])
@login_required
def create_request():
    form = CreateRequestForm()
    if form.validate_on_submit():
        support_request = SupportRequest(
            user_id=current_user.id,
            full_name=current_user.full_name,
            phone_number=current_user.phone_number,
            email=current_user.email,
            office_number=current_user.office_number,
            subject=form.subject.data,
            message=form.message.data,
            status='Ожидает ответа'
        )
        db.session.add(support_request)
        db.session.commit()

        # Save uploaded file
        if form.file.data:
            filename = secure_filename(form.file.data.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            form.file.data.save(filepath)
            uploaded_file = UploadedFile(filename=filename, request_id=support_request.id)
            db.session.add(uploaded_file)
            db.session.commit()

        # Notify admins of new request
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            notification = Notification(
                message=f'Новый запрос "{support_request.subject}" от {current_user.full_name}',
                user_id=admin.id,
                support_request_id=support_request.id
            )
            db.session.add(notification)
        db.session.commit()

        flash('Запрос успешно создан!', 'success')
        return redirect(url_for('index'))
    return render_template('create_request.html', form=form)

@app.route('/download_requests', methods=['GET'])
@login_required
def download_requests():
    if current_user.role != 'admin':
        flash('У вас нет доступа к данной странице', 'danger')
        return redirect(url_for('index'))

    # Query all support requests
    support_requests = SupportRequest.query.all()

    # Create an in-memory output file for the new workbook.
    output = BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Support Requests'

    # Add headers to the worksheet
    headers = ['Номер', 'ФИО', 'Номер телефона', 'Почта', 'Номер кабинета', 'Тема', 'Сообщение', 'Статус']
    sheet.append(headers)

    # Add data to the worksheet
    for request in support_requests:
        row = [
            request.id,
            request.full_name,
            request.phone_number,
            request.email,
            request.office_number,
            request.subject,
            request.message,
            request.status
        ]
        sheet.append(row)

    workbook.save(output)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name='support_requests.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/view_request/<int:request_id>', methods=['GET', 'POST'])
@login_required
def view_request(request_id):
    support_request = SupportRequest.query.get_or_404(request_id)
    form = CommentForm()
    if form.validate_on_submit() and support_request.status != 'Выполнен':
        comment = Comment(
            support_request_id=request_id,
            user_id=current_user.id,
            content=form.content.data
        )
        db.session.add(comment)

        # Notify user of new comment if admin commented
        if current_user.role == 'admin':
            notification = Notification(
                message=f'Новый комментарий в вашем запросе "{support_request.subject}" от {current_user.full_name}',
                user_id=support_request.user_id,
                support_request_id=request_id
            )
            db.session.add(notification)

        # Notify admins of new comment if user commented
        elif current_user.role == 'user':
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                notification = Notification(
                    message=f'Новый комментарий в запросе "{support_request.subject}" от {current_user.full_name}',
                    user_id=admin.id,
                    support_request_id=request_id
                )
                db.session.add(notification)

        if support_request.status == 'Ожидает ответа' and current_user.role == 'admin':
            support_request.status = 'В работе'
        db.session.commit()
        flash('Ваш комментарий добавлен!', 'success')
        return redirect(url_for('view_request', request_id=request_id))
    comments = Comment.query.filter_by(support_request_id=request_id).order_by(Comment.timestamp.asc()).all()
    uploaded_files = UploadedFile.query.filter_by(request_id=request_id).all()
    return render_template('view_request.html', support_request=support_request, form=form, comments=comments, uploaded_files=uploaded_files)

@app.route('/close_request/<int:request_id>', methods=['POST'])
@login_required
def close_request(request_id):
    support_request = SupportRequest.query.get_or_404(request_id)
    if support_request.user_id == current_user.id or current_user.role == 'admin':
        support_request.status = 'Выполнен'
        db.session.commit()
        flash('Запрос успешно закрыт!', 'success')
    else:
        flash('Вы не можете закрыть запрос!', 'danger')
    return redirect(url_for('view_request', request_id=request_id))

@app.route('/user_requests')
@login_required
def user_requests():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    subject_filter = request.args.get('subject', '', type=str)
    
    query = SupportRequest.query.filter_by(user_id=current_user.id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if subject_filter:
        query = query.filter(SupportRequest.subject.like(f'%{subject_filter}%'))
    
    user_requests = query.paginate(page=page, per_page=15)
    return render_template('user_requests.html', requests=user_requests, status_filter=status_filter, subject_filter=subject_filter)

@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        flash('У вас нет доступа к данной странице', 'danger')
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    subject_filter = request.args.get('subject', '', type=str)
    user_filter = request.args.get('user', '', type=str)
    
    query = SupportRequest.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if subject_filter:
        query = query.filter(SupportRequest.subject.like(f'%{subject_filter}%'))
    if user_filter:
        query = query.join(User).filter(User.full_name.like(f'%{user_filter}%'))
    
    support_requests = query.paginate(page=page, per_page=15)
    return render_template('admin_panel.html', support_requests=support_requests, status_filter=status_filter, subject_filter=subject_filter, user_filter=user_filter)

@app.route('/active_chats')
@login_required
def active_chats():
    if current_user.role != 'admin':
        flash('У вас нет доступа к данной странице', 'danger')
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    subject_filter = request.args.get('subject', '', type=str)
    user_filter = request.args.get('user', '', type=str)
    
    query = SupportRequest.query.filter(SupportRequest.status.in_(['Ожидает ответа', 'В работе', 'Выполнен']))
    if status_filter:
        query = query.filter_by(status=status_filter)
    if subject_filter:
        query = query.filter(SupportRequest.subject.like(f'%{subject_filter}%'))
    if user_filter:
        query = query.join(User).filter(User.full_name.like(f'%{user_filter}%'))
    
    active_requests = query.paginate(page=page, per_page=15)
    return render_template('active_chats.html', active_requests=active_requests, status_filter=status_filter, subject_filter=subject_filter, user_filter=user_filter)

@app.route('/user_management')
@login_required
def user_management():
    if current_user.role != 'admin':
        flash('У вас нет доступа к данной странице', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('user_management.html', users=users)

@app.route('/update_user_role/<int:user_id>', methods=['POST'])
@login_required
def update_user_role(user_id):
    if current_user.role != 'admin':
        flash('У вас нет доступа к данной странице', 'danger')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    new_role = request.form['role']
    if new_role in ['admin', 'user']:
        user.role = new_role
        db.session.commit()
        flash(f'Роль пользователя {user.username} изменена на {new_role}.', 'success')
    else:
        flash('Выбрана неверная роль!', 'danger')
    return redirect(url_for('user_management'))

@app.route('/notifications/<int:user_id>', methods=['GET'])
@login_required
def get_notifications(user_id):
    if current_user.id != user_id and current_user.role != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    notifications = Notification.query.filter_by(user_id=user_id, is_read=False).all()
    notification_data = []
    for n in notifications:
        url = url_for('view_request', request_id=n.support_request_id) if n.support_request_id else '#'
        notification_data.append({
            'id': n.id,
            'message': n.message,
            'timestamp': n.timestamp,
            'url': url
        })
    return jsonify(notification_data)

@app.route('/notifications/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get(notification_id)
    if notification.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    notification.is_read = True
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/notifications/clear_all', methods=['POST'])
@login_required
def clear_all_notifications():
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'status': 'success'})

if __name__ == "__main__":
    app.run(debug=True)