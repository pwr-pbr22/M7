from typing import List, Callable

from sqlalchemy import func, or_, and_, not_, tuple_, sql
from sqlalchemy.orm import Query

import sql as sql_scripts
from definitions import Repository, PullRequest, Review


class Result:
    def __init__(self, evaluator_name: str, repo: Repository, considered: Query, smelly: Query):
        self.evaluator_name = evaluator_name
        self.repo = repo
        self.considered = considered
        self.smelly = smelly

    @property
    def considered_count(self) -> int:
        return self.considered.count()

    @property
    def smelly_count(self) -> int:
        return self.smelly.count()

    @property
    def percentage(self) -> float:
        return self.smelly_count / self.considered_count

    def __str__(self):
        return f"{self.evaluator_name.ljust(30)}\t{(self.percentage * 100):.2f}%"


def lack_of_review(considered: Query, repo: Repository) -> Result:
    smelly = considered.except_(considered.join(PullRequest.reviews).filter(PullRequest.user_id != Review.user_id))
    return Result("Lack of code review", repo, considered, smelly)


def missing_description(considered: Query, repo: Repository) -> Result:
    smelly = considered.filter(
        or_(
            PullRequest.title == "",
            PullRequest.body == "",
            and_(
                PullRequest.body.notlike("%\n%"),
                not_(
                    or_(
                        PullRequest.body.ilike("%fixes%"),
                        PullRequest.body.ilike("%ticket%"),
                        PullRequest.body.regexp_match("#[0-9]+")
                    )
                )
            )
        )
    )
    return Result("Missing PR description", repo, considered, smelly)


def large_changesets(considered: Query, repo: Repository) -> Result:
    smelly = considered.filter(PullRequest.deletions + PullRequest.additions > 500)
    return Result("Large changeset", repo, considered, smelly)


def sleeping_reviews(considered: Query, repo: Repository) -> Result:
    smelly = considered.filter((PullRequest.closed_at - PullRequest.created_at) >= func.make_interval(0, 0, 0, 2))
    return Result("Sleeping reviews", repo, considered, smelly)


def review_buddies(considered: Query, repo: Repository) -> Result:
    session = considered.session
    smelly_id_pairs = session.execute(sql_scripts.REVIEW_BUDDIES, {"repo_id": repo.id})

    smelly = considered.join(Review).where(
        tuple_(PullRequest.user_id, Review.user_id).in_(smelly_id_pairs)
    )

    return Result("Review Buddies", repo, considered, smelly)


def ping_pong(considered: Query, repo: Repository) -> Result:
    session = considered.session
    smelly_id_pairs = map(lambda row: row[0], session.execute(sql_scripts.PING_PONG, {"repo_id": repo.id}))

    smelly = considered.filter(PullRequest.id.in_(smelly_id_pairs))

    return Result("Ping-pong reviews", repo, considered, smelly)


def union(considered: Query, repo: Repository, evaluators: List[Callable]) -> Result:
    session = considered.session
    smelly = session.query(PullRequest).filter(sql.false())
    for evaluator in evaluators:
        smelly = smelly.union(evaluator(considered, repo).smelly)
    name = "At least one of:"
    for e in evaluators:
        name += f"\n- {e.__name__.ljust(28)}"
    return Result(name, repo, considered, smelly)


def intersection(considered: Query, repo: Repository, evaluators: List[Callable]) -> Result:
    session = considered.session
    smelly = session.query(PullRequest)
    for evaluator in evaluators:
        smelly = smelly.intersect(evaluator(considered, repo).smelly)
    name = "All of:"
    for e in evaluators:
        name += f"\n- {e.__name__.ljust(28)}"
    return Result(name, repo, considered, smelly)
