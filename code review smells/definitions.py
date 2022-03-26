import enum

from sqlalchemy import ForeignKey, Column, Integer, String, Boolean, Enum, DateTime, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ReviewStatusesEnum(enum.Enum):
    CHANGES_REQUESTED = 1
    COMMENTED = 2
    APPROVED = 3
    DISMISSED = 4


class AuthorAssociationEnum(enum.Enum):
    OWNER = 1
    MEMBER = 2
    COLLABORATOR = 3
    CONTRIBUTOR = 4
    NONE = 5


class Review(Base):
    __tablename__ = 'review'
    id = Column(Integer, primary_key=True)
    pull_id = Column(Integer, ForeignKey('pull.id'))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship('User')
    body = Column('body', String)
    state = Column('state', Enum(ReviewStatusesEnum))
    author_association = Column('author_association', Enum(AuthorAssociationEnum))
    submitted_at = Column('Submitted_at', DateTime)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    login = Column('login', String)


pulls_assignees_table = Table('pulls_assignees', Base.metadata,
                              Column('assignee_id', ForeignKey('user.id')),
                              Column('pull_id', ForeignKey('pull.id'))
                              )


class PullRequest(Base):
    __tablename__ = 'pull'
    id = Column(Integer, primary_key=True)
    number = Column('number', Integer)
    title = Column('title', String)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship('User', foreign_keys=user_id)
    body = Column('body', String)
    created_at = Column('created_at', DateTime)
    closed_at = Column('closed_at', DateTime)
    assignee_id = Column(Integer, ForeignKey('user.id'))
    assignee = relationship("User", foreign_keys=assignee_id)
    assignees = relationship("User", secondary=pulls_assignees_table)
    repository_id = Column(Integer, ForeignKey('repo.id'))
    author_association = Column('author_association', Enum(AuthorAssociationEnum))
    merged = Column('merged', Boolean)
    reviews = relationship('Review')
    additions = Column('additions', Integer)
    deletions = Column('deletions', Integer)
    changed_files = Column('changed_files', Integer)


class Repository(Base):
    __tablename__ = 'repo'
    id = Column(Integer, primary_key=True)
    name = Column('name', String)
    full_name = Column('full_name', String)
    owner_id = Column(Integer, ForeignKey('user.id'))
    owner = relationship('User')
    pulls = relationship('PullRequest')
