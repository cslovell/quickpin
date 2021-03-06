from datetime import datetime
import dateutil.parser

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, \
                       func, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import relationship

import app.config
from model import Base
from model.avatar import Avatar
from model.label import Label


SOCIAL_SITES = {
    'twitter': 'Twitter',
    'instagram': 'Instagram',
}


avatar_join_profile = Table(
    'avatar_join_profile',
    Base.metadata,
    Column('avatar_id', Integer, ForeignKey('avatar.id'), primary_key=True),
    Column('profile_id', Integer, ForeignKey('profile.id'), primary_key=True),
)


profile_join_self = Table(
    'profile_join_self',
    Base.metadata,
    Column('follower_id', Integer, ForeignKey('profile.id'), primary_key=True),
    Column('friend_id', Integer, ForeignKey('profile.id'), primary_key=True),
)

label_join_profile = Table(
    'label_join_profile',
    Base.metadata,
    Column('label_id', Integer, ForeignKey('label.id'), primary_key=True),
    Column('profile_id', Integer, ForeignKey('profile.id'), primary_key=True),
)


class Profile(Base):
    ''' Data model for a profile. '''

    __tablename__ = 'profile'
    __table_args__ = (
        UniqueConstraint('site', 'upstream_id', name='uk_site_upstream_id'),
    )

    id = Column(Integer, primary_key=True)
    site = Column(Enum(*SOCIAL_SITES.keys(), name='social_site'), nullable=False)
    upstream_id = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)

    # A stub profile is one that exists only because some other profile is
    # connected to this profile; we haven't collected any additional information
    # about it.
    is_stub = Column(Boolean, nullable=False, default=False)
    name = Column(String(255))
    description = Column(Text)
    homepage = Column(Text)
    join_date = Column(DateTime)

    last_update = Column(
        DateTime,
        default=func.current_timestamp(),
    )

    follower_count = Column(Integer)
    friend_count = Column(Integer)
    post_count = Column(Integer)
    lang = Column(String(255))
    location = Column(Text)
    private = Column(Boolean)
    time_zone = Column(Text)

    # One profile has 1-n usernames.
    usernames = relationship(
        'ProfileUsername',
        backref='profile',
        cascade='all,delete-orphan'
    )

    # One profile has 0-n posts.
    posts = relationship(
        'Post',
        backref='author',
        cascade='all,delete-orphan'
    )

    # A profile has 0-n avatar images.
    avatars = relationship(
        'Avatar',
        secondary=avatar_join_profile
    )

    # One profile has 0-n notes.
    notes = relationship(
        'ProfileNote',
        cascade='all,delete-orphan'
    )

    # A profile can follow other profiles. We use the Twitter nomenclature and
    # call this relationship "friend".
    friends = relationship(
        'Profile',
        secondary=profile_join_self,
        primaryjoin=(id == profile_join_self.c.follower_id),
        secondaryjoin=(id == profile_join_self.c.friend_id)
    )

    # A profile can be followed other profiles.
    followers = relationship(
        'Profile',
        secondary=profile_join_self,
        primaryjoin=(id == profile_join_self.c.friend_id),
        secondaryjoin=(id == profile_join_self.c.follower_id)
    )

    # A user can mark a profile as interesting
    is_interesting = Column(Boolean, nullable=True)

    # One profile has 0-n tags.
    labels = relationship(
        'Label',
        secondary=label_join_profile
    )

    # A user can give a profile a score
    score = Column(Float, nullable=True)

    # A profile has 0 or 1 current avatars. (It may also have multiple older
    # avatars; see `avatars` relationship above.)
    current_avatar_id = Column(
        Integer,
        ForeignKey('avatar.id', name='fk_profile_current_avatar', use_alter=True)
    )

    current_avatar = relationship(
        'Avatar',
        primaryjoin='Profile.current_avatar_id == Avatar.id'
    )

    def __init__(self, site, upstream_id, username, is_stub=False):
        ''' Constructor. '''

        self.site = site
        self.upstream_id = upstream_id
        self.is_stub = is_stub

        if isinstance(username, ProfileUsername):
            self.username = username.username
            self.usernames.append(username)
        else:
            now = datetime.now()
            self.username = username
            self.usernames.append(
                ProfileUsername(username, start_date=now, end_date=now)
            )

    def as_dict(self):
        ''' Return dictionary representation of this profile. '''
        # Sort labels by name
        labels = [label.as_dict() for label in self.labels]
        notes = [note.as_dict() for note in self.notes]
        sorted_labels = sorted(labels, key=lambda x: x['name'])
        sorted_notes = sorted(notes, key=lambda x: x['created_at'], reverse=True)
        return {
            'description': self.description,
            'follower_count': self.follower_count,
            'friend_count': self.friend_count,
            'is_interesting': self.is_interesting,
            'id': self.id,
            'is_stub': self.is_stub,
            'join_date': self.join_date and self.join_date.isoformat(),
            'labels': sorted_labels,
            'last_update': self.last_update.replace(microsecond=0).isoformat(),
            'location': self.location,
            'name': self.name,
            'notes': sorted_notes,
            'post_count': self.post_count,
            'private': self.private,
            'score': self.score,
            'site': self.site,
            'site_name': self.site_name(),
            'upstream_id': self.upstream_id,
            'username': self.username,
            'time_zone': self.time_zone,
        }

    def site_name(self):
        ''' Human readable name for site. '''

        return SOCIAL_SITES[self.site]


class ProfileUsername(Base):
    ''' A profile can have many usernames. '''

    __tablename__ = 'profile_username'
    __table_args__ = (
        UniqueConstraint('username', 'profile_id', name='uk_username_profile_id'),
    )

    id = Column(Integer, primary_key=True)
    username = Column(String(255))
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    profile_id = Column(
        Integer,
        ForeignKey('profile.id', name='fk_profile_username_id'),
        nullable=False
    )

    def __init__(self, username, start_date=None, end_date=None):
        ''' Constructor. '''

        self.username = username

        if start_date is not None:
            if isinstance(start_date, datetime):
                self.start_date = start_date
            else:
                self.start_date = dateutil.parser.parse(start_date)

        if end_date is not None:
            if isinstance(end_date, datetime):
                self.end_date = end_date
            else:
                self.end_date = dateutil.parser.parse(end_date)


class ProfileNote(Base):
    ''' A profile can have many notes. '''

    __tablename__ = 'profile_note'
    __table_args__ = (
        UniqueConstraint('id', 'profile_id', name='uk_note_id_profile_id'),
    )

    id = Column(Integer, primary_key=True)
    category = Column(String(255))
    body = Column(Text)
    created_at = Column(DateTime,
                        default=func.current_timestamp())

    profile_id = Column(
        Integer,
        ForeignKey('profile.id', name='fk_profile_note_id'),
        nullable=False
    )

    def __init__(self, category, body, profile_id, created_at=None):
        ''' Constructor. '''
        self.category = category
        self.body = body
        self.profile_id = profile_id

        if created_at is not None:
            if isinstance(created_at, datetime):
                self.created_at = created_at
            else:
                self.created_at = dateutil.parser.parse(created_at)

    def as_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'body': self.body,
            'profile_id': self.profile_id,
            'created_at': self.created_at.isoformat(),
        }
