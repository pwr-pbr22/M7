import os
import sys
from typing import Callable

from sqlalchemy import and_, or_, not_, sql, tuple_, func
from sqlalchemy.orm import Query

import db
from definitions import *


class Results:
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
        return f"{self.evaluator_name.ljust(30)}{((1 - self.percentage) * 100):.2f}%\t {(self.percentage * 100):.2f}%"


def cll():
    print("\033[A                             \033[A")


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def evaluate(repo: str, evaluator: Callable, *args) -> None:
    session = db.get_session()
    repository = session.query(Repository).filter(Repository.full_name == repo).first()
    if repository is None:
        session.close()
        print("Specified repository does not exist in specified database")
        return
    print(evaluator(session, repository, *args))
    session.close()


def lack_of_review(session, repo: Repository) -> Results:
    considered = get_considered_prs(repo, session)

    smelly = considered.except_(considered.join(PullRequest.reviews).filter(PullRequest.user_id != Review.user_id))
    return Results("Lack of code review", repo, considered, smelly)


def missing_description(session, repo: Repository) -> Results:
    considered = get_considered_prs(repo, session)

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
    return Results("Missing PR description", repo, considered, smelly)


def large_changesets(session, repo: Repository) -> Results:
    considered = get_considered_prs(repo, session)

    smelly = considered.filter(PullRequest.deletions + PullRequest.additions > 500)
    return Results("Large changeset", repo, considered, smelly)


def sleeping_reviews(session, repo: Repository) -> Results:
    considered = get_considered_prs(repo, session)

    smelly = considered.filter((PullRequest.closed_at - PullRequest.created_at) >= func.make_interval(0, 0, 0, 2))
    return Results("Sleeping reviews", repo, considered, smelly)


def review_buddies(session, repo: Repository) -> Results:
    considered_prs = get_considered_prs(repo, session)

    smelly_id_pairs = session.execute("""
        SELECT pull.user_id AS pull_requester, review.user_id AS reviewer
        FROM pull
             JOIN review ON pull.id = review.pull_id
             JOIN (SELECT pull.user_id pull_user_id, COUNT(*) total_reviews
                   FROM pull
                        JOIN review ON pull.id = review.pull_id
                   WHERE pull.repository_id = :repo_id
                     AND pull.user_id <> review.user_id
                   GROUP BY pull.user_id) AS user_total_reviews ON user_total_reviews.pull_user_id = pull.user_id
        WHERE pull.repository_id = :repo_id
          AND pull.user_id <> review.user_id
        GROUP BY pull.user_id, review.user_id, user_total_reviews.total_reviews
        HAVING CAST(COUNT(*) AS DECIMAL) / total_reviews > 0.5
           AND total_reviews > 50;
    """, {"repo_id": repo.id})

    smelly = considered_prs.join(Review).where(
        tuple_(PullRequest.user_id, Review.user_id).in_(smelly_id_pairs)
    )

    return Results("Review Buddies", repo, considered_prs, smelly)


def get_considered_prs(repo, session):
    return session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )


def ping_pong(session, repo: Repository) -> Results:
    considered_prs = get_considered_prs(repo, session)

    smelly_id_pairs = map(lambda row: row[0], session.execute("""
select pull.id as pullId
from pull join review on review.pull_id = pull.id
join (select pull.user_id, pull_id, review.user_id, count(*) reviewNumber
        from pull join review on review.pull_id = pull.id  where pull.repository_id = :repo_id
        group by pull_id, review.user_id, pull.user_id) as ping_pong on ping_pong.pull_id = pull.id
where  reviewNumber > 3 and pull.repository_id = :repo_id
 group by pull.id
       """, {"repo_id": repo.id}))

    smelly = considered_prs.filter(PullRequest.id.in_(smelly_id_pairs))

    return Results("Ping-pong reviews", repo, considered_prs, smelly)


def union(session, repo: Repository, evaluators: list) -> Results:
    considered = get_considered_prs(repo, session)

    smelly = session.query(PullRequest).filter(sql.false())
    for evaluator in evaluators:
        smelly = smelly.union(evaluator(session, repo).smelly)
    name = "At least one of:"
    for e in evaluators:
        name += f"\n- {e.__name__.ljust(28)}"
    return Results(name, repo, considered, smelly)


def intersection(session, repo: Repository, evaluators: list) -> Results:
    considered = get_considered_prs(repo, session)

    smelly = session.query(PullRequest)
    for evaluator in evaluators:
        smelly = smelly.intersect(evaluator(session, repo).smelly)
    name = "All of:"
    for e in evaluators:
        name += f"\n- {e.__name__.ljust(28)}"
    return Results(name, repo, considered, smelly)


if __name__ == "__main__":
    cls()
    if db.prepare(sys.argv[1]):
        print("Smells in PRs:")
        print(f"{''.ljust(30)}OK      \t SMELLY")
        evaluate(sys.argv[2], lack_of_review)
        evaluate(sys.argv[2], missing_description)
        evaluate(sys.argv[2], large_changesets)
        evaluate(sys.argv[2], sleeping_reviews)
        evaluate(sys.argv[2], review_buddies)
        evaluate(sys.argv[2], ping_pong)
        evaluate(sys.argv[2], union,
                 [lack_of_review, missing_description, large_changesets, sleeping_reviews, review_buddies, ping_pong])
        evaluate(sys.argv[2], intersection,
                 [lack_of_review, missing_description, large_changesets, sleeping_reviews, review_buddies, ping_pong])
    else:
        print("Can't connect to db")
