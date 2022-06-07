import enum

from sqlalchemy import ForeignKey, Column, Integer, String, Boolean, Enum, DateTime, Table, ForeignKeyConstraint, \
    select, func, distinct
from sqlalchemy.orm import declarative_base, relationship, object_session

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


class Commit(Base):
    __tablename__ = 'commit'
    id = Column(String, primary_key=True)
    buggy = Column(Boolean)
    project = Column(String)

    def __str__(self) -> str:
        return str(vars(self))


pulls_commits_table = Table('pulls_commits', Base.metadata,
                            Column('commit_id', ForeignKey('commit.id')),
                            Column('pull_id', ForeignKey('pull.id'))
                            )


# noinspection SpellCheckingInspection
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

    @property
    def review_chars(self) -> int:
        return object_session(self).scalar(select(func.char_length(self.body)))

    @property
    def review_chars_code_lines_ratio(self) -> float:
        code_lines = object_session(self). \
            scalar(
            select(PullRequest.additions + PullRequest.deletions).
                where(PullRequest.id == self.pull_id))
        return self.review_chars / code_lines if code_lines > 0 else float("nan")

    @property
    def reviewed_lines_per_hour(self) -> float:
        return object_session(self).execute("""
            SELECT (pr.additions + pr.deletions) * 1.0 / (EXTRACT (Epoch FROM(r.submitted_at - pr.created_at))/3600)
            FROM review as "r" JOIN pull as "pr" ON r.pull_id=pr.id
            WHERE r.id = :review_id;""", {"review_id": self.id}).scalar()

    def __str__(self) -> str:
        return str(vars(self))


# noinspection SpellCheckingInspection
class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    login = Column(String)

    def __str__(self) -> str:
        return str(vars(self))


pulls_assignees_table = Table('pulls_assignees', Base.metadata,
                              Column('assignee_id', ForeignKey('user.id')),
                              Column('pull_id', ForeignKey('pull.id'))
                              )


# noinspection SpellCheckingInspection
class PullRequest(Base):
    __tablename__ = 'pull'
    id = Column(Integer, primary_key=True)
    number = Column(Integer)
    title = Column(String)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship('User', foreign_keys=user_id)
    body = Column(String)
    commits = relationship('Commit', secondary=pulls_commits_table)
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

    @property
    def reviewers_count(self) -> int:
        return self.count_reviewers(include_author=True)

    def count_reviewers(self,
                        include_author: bool = False,
                        required_experience: int = 0,
                        association: AuthorAssociationEnum = None) -> int:
        query = select(func.count(distinct(Review.user_id))).where(Review.pull_id == self.id)
        if not include_author:
            query = query.where(Review.user_id != self.user_id)
        if required_experience > 0:
            raise NotImplementedError()
        if association is not None:
            query = query.where(Review.author_association == association)
        return object_session(self).scalar(query)

    @property
    def reviews_count(self):
        return self.count_reviews(include_author=True)

    def count_reviews(self,
                      include_author: bool = False,
                      required_experience: int = 0,
                      association: AuthorAssociationEnum = None,
                      status: ReviewStatusesEnum = None,
                      min_length: int = 0) -> int:
        query = select(func.count(Review.id)).where(Review.pull_id == self.id)
        if not include_author:
            query = query.where(Review.user_id != self.user_id)
        if required_experience > 0:
            raise NotImplementedError()
        if association is not None:
            query = query.where(Review.author_association == association)
        if status is not None:
            query = query.where(Review.state == status)
        if min_length > 0:
            query = query.where(func.char_length(Review.body) >= min_length)
        return object_session(self).scalar(query)

    @property
    def discussion_chars(self):
        return object_session(self).scalar(
            select(func.sum(func.char_length(Review.body))).
            where(Review.pull_id == self.id))

    @property
    def discussion_chars_code_lines_ratio(self):
        code_lines = self.additions + self.deletions
        return self.discussion_chars/code_lines if code_lines > 0 else float("nan")

    def __str__(self) -> str:
        return str(vars(self))


# noinspection SpellCheckingInspection
class Repository(Base):
    __tablename__ = 'repo'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    full_name = Column(String)
    owner_id = Column(Integer, ForeignKey('user.id'))
    owner = relationship('User')
    pulls = relationship('PullRequest')

    def __str__(self) -> str:
        return str(vars(self))


# noinspection SpellCheckingInspection
class File(Base):
    __tablename__ = 'file'
    filename = Column('filename', String, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repo.id'), primary_key=True)
    repo = relationship('Repository', foreign_keys=repo_id)
    firstMerged = Column(DateTime)
    lastDeleted = Column(DateTime)
    pulls = relationship('FileChange', back_populates="file")

    def __str__(self) -> str:
        return str(vars(self))


# noinspection SpellCheckingInspection
class FileChange(Base):
    __tablename__ = 'file_change'
    filename = Column(String, primary_key=True)
    repo_id = Column(Integer, primary_key=True)
    pull_id = Column(Integer, ForeignKey('pull.id'), primary_key=True)
    file = relationship("File", back_populates="pulls")
    pull = relationship("PullRequest", back_populates="changed_files")
    additions = Column(Integer)
    deletions = Column(Integer)
    changes = Column(Integer)
    __table_args__ = (ForeignKeyConstraint((repo_id, filename),
                                           [File.repo_id, File.filename]),
                      {})

    def __str__(self) -> str:
        return str(vars(self))


# noinspection SpellCheckingInspection
class IssueForBug(Base):
    __tablename__ = "issue_for_bug"
    id = Column(Integer, primary_key=True)
    number = Column(Integer)
    repo_id = Column(Integer, ForeignKey('repo.id'))
    repo = relationship('Repository', foreign_keys=repo_id)

    def __str__(self) -> str:
        return str(vars(self))
