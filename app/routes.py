from datetime import datetime, timezone
from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user, login_required
import sqlalchemy as sa
from app import app, db
from app.forms import (
    LoginForm, RegistrationForm, EditProfileForm,
    EmptyForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm, UploadImageForm
)
from app.models import User, Post, Quest, post_users
from app.email import send_password_reset_email

from app.utils import save_image, allowed_file, delete_old_image


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()


@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(
        current_user.following_posts(),
        page=page,
        per_page=app.config['POSTS_PER_PAGE'],
        error_out=False
    )
    next_url = url_for('index', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) if posts.has_prev else None

    return render_template(
        'index.html', title='Home',
        posts=posts.items, now=datetime.utcnow(), next_url=next_url, prev_url=prev_url
    )


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(
            title=form.title.data,
            body=form.body.data,
            due_date=form.due_date.data,
            author=current_user
        )
        # handle uploaded image
        if form.image.data:
            post.image_file = save_image(
                form.image.data,
                folder='post_pics',
                size=(400, 400)
            )
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))

    return render_template('create_template.html', title='Home', form=form)


@app.route('/', methods=['GET', 'POST'])
@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template(
        'index.html', title='Explore',
        posts=posts.items, now=datetime.utcnow(),  next_url=next_url, prev_url=prev_url
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data)
        )
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data)
        )
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template(
        'reset_password_request.html',
        title='Reset Password', form=form
    )


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    query = user.posts.select().order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'],
                        error_out=False)

    joined_query = (
        sa.select(Post)
        .join(post_users)
        .where(post_users.c.user_id == user.id)
        .order_by(Post.timestamp.desc())
    )
    joined_posts = db.session.execute(joined_query).scalars().all()

    next_url = url_for('user', username=user.username, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('user', username=user.username, page=posts.prev_num) \
        if posts.has_prev else None
    form = EmptyForm()
    return render_template(
        'user.html', user=user, posts=posts.items, now=datetime.utcnow(),
        next_url=next_url, prev_url=prev_url,
        form=form, joined_posts=joined_posts
    )


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        # handle new profile picture upload
        if form.picture.data:
            pic_path = save_image(
                form.picture.data,
                folder='profile_pics',
                size=(256, 256)
            )
            current_user.profile_pic = pic_path
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template(
        'edit_profile.html', title='Edit Profile', form=form
    )


@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username)
        )
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username)
        )
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/join_post/<int:post_id>', methods=['POST'])
@login_required
def join_post(post_id):
    post = Post.query.get_or_404(post_id)
    if current_user != post.author and current_user not in post.users:
        post.users.append(current_user)
        db.session.commit()
        flash('You joined the post!')
    return redirect(request.referrer or url_for('index'))


# Route to upload an image for a quest
@app.route('/upload_quest_image/<int:quest_id>', methods=['GET', 'POST'])
@login_required
def upload_quest_image(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    if quest.creator != current_user:
        flash('You are not authorized to upload an image for this quest.')
        return redirect(url_for('index'))

    form = UploadImageForm()
    if form.validate_on_submit():
        # Handle uploaded image for the quest
        image_path = save_image(form.image.data, folder='quest_pics', size=(400, 400))
        quest.image_file = image_path
        db.session.commit()
        flash('Quest image uploaded successfully!')
        return redirect(url_for('quest_detail', quest_id=quest.id))  # Assuming there's a quest detail route

    return render_template('upload_image.html', title='Upload Quest Image', form=form)


# Route to upload or update profile picture
@app.route('/upload_profile_image', methods=['GET', 'POST'])
@login_required
def upload_profile_image():
    form = UploadImageForm()
    if form.validate_on_submit():
        if not allowed_file(form.image.data.filename):
            flash('Unsupported file type. Please upload PNG, JPG, or GIF.')
            return redirect(request.url)

        # Delete old profile picture
        delete_old_image(current_user.profile_pic)

        # Save new image
        image_path = save_image(form.image.data, folder='profile_pics', size=(256, 256))
        current_user.profile_pic = image_path
        db.session.commit()
        flash('Your profile picture has been updated!')
        return redirect(url_for('edit_profile'))

    return render_template('upload_image.html', title='Upload Profile Image', form=form)

# Route to upload an image for any generic post (not directly related to profile or quests)
@app.route('/upload_post_image/<int:post_id>', methods=['GET', 'POST'])
@login_required
def upload_post_image(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash('You are not authorized to upload an image for this post.')
        return redirect(url_for('index'))

    form = UploadImageForm()
    if form.validate_on_submit():
        if not allowed_file(form.image.data.filename):
            flash('Unsupported file type. Please upload PNG, JPG, or GIF.')
            return redirect(request.url)

        # Delete old post image
        delete_old_image(post.image_file)

        # Save new image
        image_path = save_image(form.image.data, folder='post_pics', size=(400, 400))
        post.image_file = image_path
        db.session.commit()
        flash('Post image uploaded successfully!')
        return redirect(url_for('post_detail', post_id=post.id))

    return render_template('upload_image.html', title='Upload Post Image', form=form)
