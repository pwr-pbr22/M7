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
    body = Column(String)
    state = Column(Enum(ReviewStatusesEnum))
    author_association = Column(Enum(AuthorAssociationEnum))
    submitted_at = Column(DateTime)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    login = Column(String)


pulls_assignees_table = Table('pulls_assignees', Base.metadata,
                              Column('assignee_id', ForeignKey('user.id')),
                              Column('pull_id', ForeignKey('pull.id'))
                              )


class PullRequest(Base):
    __tablename__ = 'pull'
    id = Column(Integer, primary_key=True)
    number = Column(Integer)
    title = Column(String)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship('User', foreign_keys=user_id)
    body = Column(String)
    created_at = Column(DateTime)
    closed_at = Column(DateTime)
    assignee_id = Column(Integer, ForeignKey('user.id'))
    assignee = relationship("User", foreign_keys=assignee_id)
    assignees = relationship("User", secondary=pulls_assignees_table)
    repository_id = Column(Integer, ForeignKey('repo.id'))
    author_association = Column(Enum(AuthorAssociationEnum))
    merged = Column(Boolean)
    reviews = relationship('Review')
    additions = Column(Integer)
    deletions = Column(Integer)
    changed_files = relationship('FileChange', back_populates='pull')


class Repository(Base):
    __tablename__ = 'repo'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    full_name = Column(String)
    owner_id = Column(Integer, ForeignKey('user.id'))
    owner = relationship('User')
    pulls = relationship('PullRequest')


class File(Base):
    __tablename__ = 'file'
    filename = Column('filename', String, primary_key=True)
    firstMerged = Column(DateTime)
    lastDeleted = Column(DateTime)
    pulls = relationship('FileChange', back_populates="file")


class FileChange(Base):
    __tablename__ = 'file_change'
    filename = Column(String, ForeignKey('file.filename'), primary_key=True)
    pull_id = Column(Integer, ForeignKey('pull.id'), primary_key=True)
    file = relationship("File", back_populates="pulls")
    pull = relationship("PullRequest", back_populates="changed_files")
    additions = Column(Integer)
    deletions = Column(Integer)
    changes = Column(Integer)


class IssueForBug(Base):
    __tablename__ = "issue_for_bug"
    id = Column(Integer, primary_key=True)
    number = Column(Integer)
    repo_id = Column(Integer, ForeignKey('repo.id'))
    repo = relationship('Repository', foreign_keys=repo_id)
