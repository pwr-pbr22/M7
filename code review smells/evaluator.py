from typing import Callable, Union

from sqlalchemy import or_, and_
from sqlalchemy.orm import Query

import db
import metrics
import smells
from definitions import Repository, PullRequest


def evaluate(repo: str, evaluator: Callable, *args) -> Union[smells.Result, metrics.Result, None]:
    session = db.get_session()
    repository = session.query(Repository).filter(Repository.full_name == repo).first()
    if repository is None:
        session.close()
        print("Specified repository does not exist in specified database")
        return None
    result = evaluator(get_considered_prs(repository, session), repository, *args)
    session.close()
    return result


def get_considered_prs(repo: Repository, session) -> Query:
    return session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )
