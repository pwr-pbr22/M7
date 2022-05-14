from datetime import datetime
from functools import reduce
from typing import Callable, List, Optional, Union
from sqlalchemy import or_, and_
from sqlalchemy.orm import Query


import db
from definitions import Repository, PullRequest, FileChange
import smells
import metrics


<<<<<<< Updated upstream
def create_functions_in_db(session):
    if session.execute("SELECT to_regproc('pbr.public.prFixesBug') IS NULL;").scalar():
        session.execute(f"""
            CREATE FUNCTION prFixesBug(pr_id integer) RETURNS boolean AS $$
                DECLARE
                    pr record;
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
        """)
=======

def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def __createFunctionsInDb(session):
    if session.execute(sql.CHECK_NULL_PR_FIX_BUG).scalar():
        session.execute(sql.CREATE_FUNCTION_PR_FIX_BUG)
>>>>>>> Stashed changes
        session.commit()
    if session.execute(sql.CHECK_NULL_NEXT_PR_FIX_BUG).scalar():
        session.execute(sql.CREATE_FUNCTION_NEXT_PR_FIX_BUG)
        session.commit()


def _next_file_change_fixes_bug(session, repo: Repository, filename: str, starting: datetime) -> Optional[bool]:
    return session.execute(f"""SELECT nextFixesBug({repo.id}, '{filename}', '{starting}'::TIMESTAMP)""").first()[0]


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


<<<<<<< Updated upstream
def get_considered_prs(repo, session) -> Query:
=======
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


# TODO return proper structure
def review_window_metric(session, repo: Repository):
    considered = get_considered_prs(repo, session)
    return considered.add_columns((
                                      func.trunc(
                                          (
                                                  extract('epoch', PullRequest.closed_at) -
                                                  extract('epoch', PullRequest.created_at)
                                          ) / 60)
                                  ).label("metric"))


# TODO return proper structure
def review_window_per_line_metric(session, repo: Repository):
    considered = get_considered_prs(repo, session)
    return considered.add_columns((
                                      func.trunc(
                                          (
                                                  extract('epoch', PullRequest.closed_at) -
                                                  extract('epoch', PullRequest.created_at)
                                          ) / 60 / (PullRequest.additions + PullRequest.deletions))
                                  ).label("metric"))


def review_buddies(session, repo: Repository) -> Results:
    considered_prs = get_considered_prs(repo, session)

    smelly_id_pairs = session.execute(sql.REVIEW_BUDDIES, {"repo_id": repo.id})

    smelly = considered_prs.join(Review).where(
        tuple_(PullRequest.user_id, Review.user_id).in_(smelly_id_pairs)
    )

    return Results("Review Buddies", repo, considered_prs, smelly)


def get_considered_prs(repo, session):
>>>>>>> Stashed changes
    return session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )


<<<<<<< Updated upstream
def calc_impact(session, repo: Repository, evaluator: Callable, evaluator_args=None) -> (float, float):
    evaluation_results: smells.Result = \
        evaluator(get_considered_prs(repo, session), repo) if evaluator_args is None \
            else evaluator(get_considered_prs(repo, session), repo, evaluator_args)
=======
def pingPong(session, repo: Repository) -> Results:
    considered_prs = get_considered_prs(repo, session)

    smelly_id_pairs = map(lambda row: row[0], session.execute(sql.PING_PONG, {"repo_id": repo.id}))
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


def calcImpact(session, repo: Repository, evaluator: Callable, evaluator_args=None) -> (float, float):
    evaluation_results: Results = \
        evaluator(session, repo) if evaluator_args is None else evaluator(session, repo, evaluator_args)
>>>>>>> Stashed changes
    smelly: List[PullRequest] = evaluation_results.smelly.all()
    ok: List[PullRequest] = evaluation_results.considered.except_(evaluation_results.smelly).all()

    total = evaluation_results.considered_count
    smelly_count = evaluation_results.smelly_count
    ok_count = total - smelly_count

    def helper(filechanges: List[FileChange]) -> int:
        if any(_next_file_change_fixes_bug(session, repo, file_change.filename, file_change.pull.closed_at)
               for file_change in filechanges):
            return 1
        return 0

    ok_bugfixing = (reduce(lambda a, b: a + b,
                           list(map(lambda pr: helper(pr.changed_files), ok))) / float(ok_count)) \
        if ok_count > 0 else float("nan")
    smelly_bugfixing = (reduce(lambda a, b: a + b,
                               list(map(lambda pr: helper(pr.changed_files), smelly))) / float(smelly_count)) \
        if smelly_count > 0 else float("nan")
    return ok_bugfixing, smelly_bugfixing
<<<<<<< Updated upstream
=======


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
            print(f"{''.ljust(30)}OK    \t SMELLY\t IMPACT")

            res = calcImpact(dbsession, repo_obj, lackOfCodeReview)
            cll()
            print(
                f"{'Lack of code review'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")

            res = calcImpact(dbsession, repo_obj, missingPrDescription)
            cll()
            print(
                f"{'Sleeping review'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")

            res = calcImpact(dbsession, repo_obj, sleepingReviews)
            cll()
            print(
                f"{'Review buddies'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")

            res = calcImpact(dbsession, repo_obj, review_buddies)
            cll()
            print(
                f"{'Ping-pong'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")

            res = calcImpact(dbsession, repo_obj, pingPong)
            cll()
            print(
                f"{'Missing PR description'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")

            res = calcImpact(dbsession, repo_obj, largeChangesets)
            cll()
            print(
                f"{'Large changesets'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")

            res = calcImpact(dbsession, repo_obj, union, [lackOfCodeReview, sleepingReviews, review_buddies, pingPong])
            cll()
            print(
                f"{'One of review related'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")

            res = calcImpact(dbsession, repo_obj, intersection,
                             [lackOfCodeReview, sleepingReviews, review_buddies, pingPong])
            cll()
            print(
                f"{'All of review related'.ljust(30)}{(res[0] * 100):.2f}%\t {(res[1] * 100):.2f}%\t {'+' if res[1] > res[0] else ''}{((res[1] - res[0]) * 100):.2f}%")
        dbsession.close()
    else:
        print("Can't connect to db")
>>>>>>> Stashed changes
