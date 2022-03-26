import sys
from typing import Callable

from sqlalchemy import and_, or_, func, not_, sql

import db
from definitions import *


class Results:
    def __init__(self, evaluator_name, repo: Repository, considered, smelly):
        self.evaluator_name = evaluator_name
        self.repo = repo
        self.considered = considered
        self.smelly = smelly

    @property
    def considered_count(self):
        return self.considered.count()

    @property
    def smelly_count(self):
        return self.smelly.count()

    @property
    def percentage(self):
        return self.smelly_count / self.considered_count

    def __str__(self):
        return f"[{self.repo.full_name}] {self.evaluator_name} found {self.smelly_count} in " \
               f"{self.considered.count()} pulls ({(self.percentage * 100):.2f}%)"


def evaluate(repo: str, evaluator: Callable, *args):
    session = db.getSession()
    repository = session.query(Repository).filter(Repository.full_name == repo).first()
    if repository is None:
        session.close()
        print("Specified repository does not exist in specified database")
        return
    print(evaluator(session, repository, *args))
    session.close()


def lackOfCodeReview(session, repo: Repository):
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             )
    )

    smelly = considered.except_(considered.join(PullRequest.reviews).filter(PullRequest.user_id != Review.user_id))
    return Results("Lack of code review", repo, considered, smelly)


def missingPrDescription(session, repo: Repository):
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             )
    )

    smelly = considered.filter(
        or_(
            PullRequest.title == "",
            PullRequest.body == "",
            and_(
                PullRequest.body.notlike("%\n%"),
                not_(
                    or_(
                        func.lower(PullRequest.body).like("%fixes%"),
                        func.lower(PullRequest.body).like("%ticket%"),
                        PullRequest.body.regexp_match("#[0-9]+")
                    )
                )
            )
        )
    )
    return Results("Missing pull request description", repo, considered, smelly)


def largeChangesets(session, repo: Repository):
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             )
    )

    smelly = considered.filter(PullRequest.deletions + PullRequest.additions > 500)
    return Results("Large changeset", repo, considered, smelly)


def union(session, repo: Repository, evaluators: list):
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             )
    )

    smelly = session.query(PullRequest).filter(sql.false())
    for evaluator in evaluators:
        smelly = smelly.union(evaluator(session, repo).smelly)
    return Results(f"At least one of {list(map(lambda e: e.__name__, evaluators))}", repo, considered, smelly)


def intersection(session, repo: Repository, evaluators: list):
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             )
    )

    smelly = session.query(PullRequest)
    for evaluator in evaluators:
        smelly = smelly.intersect(evaluator(session, repo).smelly)
    return Results(f"{list(map(lambda e: e.__name__, evaluators))} at once", repo, considered, smelly)


if __name__ == "__main__":
    if db.prepare(sys.argv[1]):
        evaluate(sys.argv[2], lackOfCodeReview)
        evaluate(sys.argv[2], missingPrDescription)
        evaluate(sys.argv[2], largeChangesets)
        evaluate(sys.argv[2], union, [lackOfCodeReview, missingPrDescription, largeChangesets])
        evaluate(sys.argv[2], intersection, [lackOfCodeReview, missingPrDescription, largeChangesets])
