import os
import sys
from datetime import datetime
from functools import reduce
from typing import Callable, List, Optional

from sqlalchemy import and_, or_, not_, sql, tuple_, text, func
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


def __createFunctionsInDb(session):
    session.execute(f"""
        CREATE OR REPLACE FUNCTION prFixesBug(pr_id integer) RETURNS boolean AS $$
            DECLARE
                pr record;
                nt text;
            BEGIN
                -- check id
                IF 
                    (SELECT EXISTS(SELECT id FROM Issue_for_bug where id=pr_id))
                THEN
                    RETURN true;
                END IF;
                
                -- check content
                SELECT * INTO pr FROM Pull WHERE Pull.id=pr_id;
                IF
                        pr.title ILIKE '%bug%'
                    OR
                        pr.title ILIKE '%error%'
                    OR
                        pr.title ILIKE '%fix%'
                    OR
                        pr.body ILIKE '%bug%'
                    OR
                        pr.body ILIKE '%error%'
                    OR
                        pr.body ILIKE '%fix%'
                THEN
                    RETURN true;
                END IF;
                
                -- check referenced
                IF
                (
                    SELECT EXISTS
                    (
                        SELECT 
                            * 
                        FROM 
                        (
                            (
                                SELECT pr.id, regexp_matches(pr.title, '#(\\d+)', 'g') AS "matches"
                            )
                            UNION
                            (
                                SELECT pr.id, regexp_matches(pr.body, '#(\\d+)', 'g') AS "matches"
                            )
                        ) AS "mi"
                        WHERE
                            CAST(mi.matches[1] AS INTEGER) IN (SELECT number FROM issue_for_bug WHERE repo_id=pr.repository_id)
                    )
                )
                THEN
                    RETURN true;
                END IF;
                
                RETURN false;
            END;
        $$
        Language plpgsql;


        CREATE OR REPLACE FUNCTION nextFixesBug(repo_id integer, filename text, starting timestamp) RETURNS boolean AS $$
            DECLARE
                pr_id integer;
            BEGIN
                SELECT INTO pr_id
                    p.id
                FROM
                    File_change AS "fc" 
                    JOIN Pull AS "p" ON fc.pull_id=p.id
                WHERE
                    p.repository_id = $1 AND
                    fc.filename = $2 AND
                    p.closed_at > $3
                ORDER BY
                    p.closed_at
                LIMIT 1;
                
                IF 
                    pr_id IS NULL
                THEN
                    RETURN null;
                ELSE
                    RETURN prFixesBug(pr_id);
                END IF;
            END;
        $$
        Language plpgsql;
    """)


def _nextFileChangeFixesBug(session, repo: Repository, filename: str, starting: datetime) -> Optional[bool]:
    return session.execute(f"""SELECT nextFixesBug({repo.id}, '{filename}', '{starting}'::TIMESTAMP)""").first()[0]


def evaluate(repo: str, evaluator: Callable, *args) -> None:
    session = db.getSession()
    repository = session.query(Repository).filter(Repository.full_name == repo).first()
    if repository is None:
        session.close()
        print("Specified repository does not exist in specified database")
        return
    print(evaluator(session, repository, *args))
    session.close()


def lackOfCodeReview(session, repo: Repository) -> Results:
    considered = get_considered_prs(repo, session)

    smelly = considered.except_(considered.join(PullRequest.reviews).filter(PullRequest.user_id != Review.user_id))
    return Results("Lack of code review", repo, considered, smelly)


def missingPrDescription(session, repo: Repository) -> Results:
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


def largeChangesets(session, repo: Repository) -> Results:
    considered = get_considered_prs(repo, session)

    smelly = considered.filter(PullRequest.deletions + PullRequest.additions > 500)
    return Results("Large changeset", repo, considered, smelly)


def sleepingReviews(session, repo: Repository) -> Results:
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
                   WHERE pull.repository_id = 6786166
                     AND pull.user_id <> review.user_id
                   GROUP BY pull.user_id) AS user_total_reviews ON user_total_reviews.pull_user_id = pull.user_id
        WHERE pull.repository_id = 6786166
          AND pull.user_id <> review.user_id
        GROUP BY pull.user_id, review.user_id, user_total_reviews.total_reviews
        HAVING CAST(COUNT(*) AS DECIMAL) / total_reviews > 0.5
           AND total_reviews > 50;
    """)

    conditions = [and_(PullRequest.user_id == pruid, Review.user_id == revuid) for (pruid, revuid) in smelly_id_pairs]
    smelly = considered_prs.join(Review).where(or_(*conditions))

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


def pingPong(session, repo: Repository) -> Results:
    considered_prs = get_considered_prs(repo, session)

    smelly_id_pairs = session.execute("""
         with consolidated_reviewers as
        (
            select pull_id, user_id, count(*) reviewNumber
            from review
            group by pull_id, user_id
            order by reviewNumber desc, pull_id, user_id
        )
        select pull_id, user_id
        from consolidated_reviewers
        where reviewNumber > 3
         order by reviewNumber desc,  pull_id, user_id;
       """)

    conditions = [and_(PullRequest.user_id == pruid, Review.user_id == revuid) for (pruid, revuid) in smelly_id_pairs]
    smelly = considered_prs.join(Review).where(or_(*conditions))

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


def calcImpact(session, repo: Repository, evaluator: Callable, evaluator_args=None) -> (float, float):
    evaluation_results: Results = \
        evaluator(session, repo) if evaluator_args is None else evaluator(session, repo, evaluator_args)
    smelly: List[PullRequest] = evaluation_results.smelly.all()
    ok: List[PullRequest] = evaluation_results.considered.except_(evaluation_results.smelly).all()
    # filechangesRemovingBugs = _filechangesRemovingBugs(session, repo)

    counter = 0.0
    startTime = datetime.now()
    total = evaluation_results.considered_count
    print()

    def helper(filechanges: List[FileChange]) -> int:
        def printProgress():
            cll()
            nonlocal counter
            percentage = counter / total
            if percentage > 0:
                remainingTime = int((datetime.now() - startTime).seconds / percentage * (1 - percentage))
                print(
                    f"[{(percentage * 100):.2f}%, {remainingTime // 60}m{str(remainingTime % 60).rjust(2, '0')}s]")

        nonlocal counter
        counter += 1
        printProgress()
        if any(_nextFileChangeFixesBug(session, repo, file_change.filename, file_change.pull.closed_at) for file_change
               in filechanges):
            return 1
        return 0

    return reduce(lambda a, b: a + b, list(map(lambda pr: helper(pr.changed_files), ok))) / float(
        evaluation_results.considered_count - evaluation_results.smelly_count), reduce(lambda a, b: a + b, list(
        map(lambda pr: helper(pr.changed_files), smelly))) / float(evaluation_results.smelly_count)


if __name__ == "__main__":
    cls()
    if db.prepare(sys.argv[1]):
        print("Występowanie poszczególnych smelli w PR:")
        print(f"{''.ljust(30)}OK      \t SMELLY")
        evaluate(sys.argv[2], lackOfCodeReview)
        evaluate(sys.argv[2], missingPrDescription)
        evaluate(sys.argv[2], largeChangesets)
        evaluate(sys.argv[2], sleepingReviews)
        evaluate(sys.argv[2], review_buddies)
        evaluate(sys.argv[2], pingPong)
        evaluate(sys.argv[2], union,
                 [lackOfCodeReview, missingPrDescription, largeChangesets, sleepingReviews, review_buddies, pingPong])
        evaluate(sys.argv[2], intersection,
                 [lackOfCodeReview, missingPrDescription, largeChangesets, sleepingReviews, review_buddies, pingPong])
        dbsession = db.getSession()
        repo_obj: Repository = dbsession.query(Repository).filter(Repository.full_name == sys.argv[2]).first()
        if repo_obj is not None:
            __createFunctionsInDb(dbsession)
            print()
            print(
                f"Prawdopodobieństwa, że dla przynajmniej jednego z plików zmodyfikowanych "
                f"przez dany PR następna edycja zostanie dokonana przez bug solving PR:")
            print(f"{''.ljust(30)}OK    \t SMELLY")
            res = calcImpact(dbsession, repo_obj, lackOfCodeReview)
            cll()
            print(f"{'Lack of code review'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, missingPrDescription)
            cll()
            print(f"{'Sleeping review'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, sleepingReviews)
            cll()
            print(f"{'Missing PR description'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, largeChangesets)
            cll()
            print(f"{'Large changesets'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, union,
                             [lackOfCodeReview, missingPrDescription, largeChangesets, sleepingReviews])
            cll()
            print(f"{'One of aformentioned'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, intersection,
                             [lackOfCodeReview, missingPrDescription, largeChangesets, sleepingReviews])
            cll()
            print(f"{'All of aforementioned'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
        dbsession.close()
    else:
        print("Can't connect to db")
