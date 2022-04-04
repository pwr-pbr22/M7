import os
import sys
from datetime import datetime
from functools import reduce
from typing import Callable, List

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


# returns query with Filechange objects which
# were changed by pr with keywords such as "bug", "fix", "error"
# or were referencing to issue tagged as bugs
def _filechangesRemovingBugs(session, repo: Repository) -> Query:
    considered = session.query(FileChange).join(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )
    with_keywords = considered.filter(
        and_(
            FileChange.filename.like("%.%"),  # files only no folders
            FileChange.filename.notilike("%.json"),  # ignore config files and similar
            FileChange.filename.notilike("%.yml"),
            FileChange.filename.notilike("%.md"),
            FileChange.filename.notilike("%.gitignore"),
            FileChange.filename.notilike("%.lock"),
            PullRequest.title.notilike("%better%"),  # remove some false-positives
            PullRequest.body.notilike("%better%"),
            or_(  # check for keywords
                PullRequest.title.ilike("%bug%"),
                PullRequest.title.ilike("%error%"),
                PullRequest.title.ilike("%fix%"),
                PullRequest.body.ilike("%bug%"),
                PullRequest.body.ilike("%error%"),
                PullRequest.body.ilike("%fix%")
            )
        )
    )
    bugsolving_filechanges = session.execute(text(f"""
        SELECT DISTINCT
            filename, pull_id
        FROM 
        (
            (
                SELECT
                    fc.filename, fc.pull_id, regexp_matches(pr.title, '#(\\d+)', 'g') AS "matches"
                FROM
                    FILE_CHANGE AS "fc" JOIN PULL AS "pr" ON fc.pull_id=pr.id
                WHERE
                        pr.repository_id = {repo.id}
                    AND
                        -- files only no folders
                        fc.filename LIKE '%.%'
                    AND
                        -- useless files
                        fc.filename NOT LIKE '%.json'
                    AND
                        fc.filename NOT LIKE '%.yml'
                    AND
                        fc.filename NOT LIKE '%.md'
                    AND
                        fc.filename NOT LIKE '%.gitignore'
                    AND
                        fc.filename NOT LIKE '%.lock'
            )
            UNION
            (
                SELECT
                    fc.filename, fc.pull_id, regexp_matches(pr.body, '#(\\d+)', 'g') AS "matches"
                FROM
                    FILE_CHANGE AS "fc" JOIN PULL AS "pr" ON fc.pull_id=pr.id
                WHERE
                        pr.repository_id = {repo.id}
                    AND
                        -- files only no folders
                        fc.filename LIKE '%.%'
                    AND
                        -- useless files
                        fc.filename NOT LIKE '%.json'
                    AND
                        fc.filename NOT LIKE '%.yml'
                    AND
                        fc.filename NOT LIKE '%.md'
                    AND
                        fc.filename NOT LIKE '%.gitignore'
                    AND
                        fc.filename NOT LIKE '%.lock'
            )
        ) AS s 
    WHERE
        CAST(matches[1] AS INTEGER) IN (SELECT number FROM issue_for_bug);"""))
    referencing = considered.filter(
        tuple_(FileChange.filename, FileChange.pull_id).in_(bugsolving_filechanges)
    )
    return referencing.union(with_keywords)


def _getNextFileChange(session, file_change: FileChange, source: Query = None) -> FileChange:
    if source is None:
        source = session.query(FileChange)
    return source.filter(
        and_(
            FileChange.repo_id == file_change.repo_id,
            FileChange.filename == file_change.filename
        )
    ).join(PullRequest). \
        filter(PullRequest.closed_at > file_change.pull.closed_at).order_by(PullRequest.closed_at).first()


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
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )

    smelly = considered.except_(considered.join(PullRequest.reviews).filter(PullRequest.user_id != Review.user_id))
    return Results("Lack of code review", repo, considered, smelly)


def missingPrDescription(session, repo: Repository) -> Results:
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )

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
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )

    smelly = considered.filter(PullRequest.deletions + PullRequest.additions > 500)
    return Results("Large changeset", repo, considered, smelly)


def sleepingReviews(session, repo: Repository) -> Results:
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )

    smelly = considered.filter((PullRequest.closed_at-PullRequest.created_at) >= func.make_interval(0, 0, 0, 2))
    return Results("Sleeping reviews", repo, considered, smelly)


def union(session, repo: Repository, evaluators: list) -> Results:
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )

    smelly = session.query(PullRequest).filter(sql.false())
    for evaluator in evaluators:
        smelly = smelly.union(evaluator(session, repo).smelly)
    name = "At least one of:"
    for e in evaluators:
        name += f"\n- {e.__name__.ljust(28)}"
    return Results(name, repo, considered, smelly)


def intersection(session, repo: Repository, evaluators: list) -> Results:
    considered = session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )

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
    filechangesRemovingBugs = _filechangesRemovingBugs(session, repo)

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
        if any(_getNextFileChange(session, file_change) == _getNextFileChange(session, file_change,
                                                                              filechangesRemovingBugs) for file_change
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
        evaluate(sys.argv[2], union, [lackOfCodeReview, missingPrDescription, largeChangesets])
        evaluate(sys.argv[2], intersection, [lackOfCodeReview, missingPrDescription, largeChangesets])
        dbsession = db.getSession()
        repo_obj: Repository = dbsession.query(Repository).filter(Repository.full_name == sys.argv[2]).first()
        if repo_obj is not None:
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
            print(f"{'Missing PR description'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, largeChangesets)
            cll()
            print(f"{'Large changesets'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, union, [lackOfCodeReview, missingPrDescription, largeChangesets])
            cll()
            print(f"{'One of aformentioned'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
            res = calcImpact(dbsession, repo_obj, intersection,
                             [lackOfCodeReview, missingPrDescription, largeChangesets])
            cll()
            print(f"{'All of aforementioned'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%")
        dbsession.close()
    else:
        print("Can't connect to db")
