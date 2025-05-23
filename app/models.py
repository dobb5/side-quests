from datetime import datetime, timezone
from hashlib import md5
from time import time
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from app import app, db, login

# Association table for followers
followers = sa.Table(
    'followers',
    db.metadata,
    sa.Column('follower_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True),
    sa.Column('followed_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True)
)

# Association table for quest participants
quest_participants = db.Table(
    'quest_participants',
    db.metadata,
    sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True),
    sa.Column('quest_id', sa.Integer, sa.ForeignKey('quest.id'), primary_key=True)
)

# Association table for post participants (e.g., tagged users)
post_users = db.Table(
    'post_users',
    db.metadata,
    sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True),
    sa.Column('post_id', sa.Integer, sa.ForeignKey('post.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    profile_pic: so.Mapped[str] = so.mapped_column(
        sa.String(128), nullable=False, default='default.jpg'
    )

    posts: so.WriteOnlyMapped['Post'] = so.relationship(back_populates='author')
    created_quests: so.WriteOnlyMapped['Quest'] = so.relationship(back_populates='creator')
    joined_quests = db.relationship('Quest', secondary=quest_participants, back_populates='participants')

    following: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        back_populates='followers'
    )
    followers: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers,
        primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates='following'
    )

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'

    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        query = self.following.select().where(User.id == user.id)
        return db.session.scalar(query) is not None

    def followers_count(self):
        query = sa.select(sa.func.count()).select_from(self.followers.select().subquery())
        return db.session.scalar(query)

    def following_count(self):
        query = sa.select(sa.func.count()).select_from(self.following.select().subquery())
        return db.session.scalar(query)

    def following_posts(self):
        Author = so.aliased(User)
        Follower = so.aliased(User)
        return (
            sa.select(Post)
            .join(Post.author.of_type(Author))
            .join(Author.followers.of_type(Follower), isouter=True)
            .where(sa.or_(Follower.id == self.id, Author.id == self.id))
            .group_by(Post)
            .order_by(Post.timestamp.desc())
        )

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256'
        )

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])['reset_password']
        except Exception:
            return
        return db.session.get(User, id)


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


class Post(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(140))
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc)
    )
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)

    author: so.Mapped[User] = so.relationship(back_populates='posts')
    users = db.relationship('User', secondary=post_users, backref='tagged_posts')

    image_file: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Post {self.body}>'


class Quest(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(140), nullable=False)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.String(500))
    created_at: so.Mapped[datetime] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc), index=True
    )
    deadline: so.Mapped[Optional[datetime]] = so.mapped_column(nullable=True)
    progress: so.Mapped[int] = so.mapped_column(default=0)
    creator_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), nullable=False)

    creator: so.Mapped[User] = so.relationship(back_populates='created_quests')
    participants = db.relationship('User', secondary=quest_participants, back_populates='joined_quests')

    image_file: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128), nullable=True)

    def __repr__(self):
        return f'<Quest {self.title}>'
