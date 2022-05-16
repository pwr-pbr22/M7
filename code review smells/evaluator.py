from datetime import datetime
from functools import reduce
from typing import Callable, List, Optional, Union
from sqlalchemy import or_, and_
from sqlalchemy.orm import Query

import db
from definitions import Repository, PullRequest, FileChange
import smells
import metrics
import sql


def create_functions_in_db(session):
    if session.execute(sql.CHECK_NULL_PR_FIX_BUG).scalar():
        session.execute(sql.CREATE_FUNCTION_PR_FIX_BUG)
        session.commit()
    if session.execute(sql.CHECK_NULL_NEXT_PR_FIX_BUG).scalar():
        session.execute(sql.CREATE_FUNCTION_NEXT_PR_FIX_BUG)
        session.commit()
    if session.execute(sql.CHECK_NULL_BUGGINESS).scalar():
        session.execute(sql.CREATE_FUNCTION_BUGGINESS)
        session.commit()


def _next_file_change_fixes_bug(session, repo: Repository, filename: str, starting: datetime) -> Optional[bool]:
    return session.execute(f"""SELECT nextFixesBug({repo.id}, '{filename}', '{starting}'::TIMESTAMP)""").first()[0]


def calculate_bugginess(session, repo: Repository, filename: str, starting: datetime, files_edited: int,
                        depth: int = 4) -> Optional[float]:
    return session.execute(
        f"""SELECT bugginess({repo.id}, '{filename}', '{starting}'::TIMESTAMP, {depth}, {files_edited})""").first()[0]


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


def get_considered_prs(repo, session) -> Query:
    return session.query(PullRequest).filter(
        and_(PullRequest.repository_id == repo.id,
             or_(
                 PullRequest.deletions > 0,
                 PullRequest.additions > 0)
             ),
        PullRequest.merged
    )


def calc_impact(session, repo: Repository, evaluator: Callable, evaluator_args=None) -> (float, float):
    evaluation_results: smells.Result = \
        evaluator(get_considered_prs(repo, session), repo) if evaluator_args is None \
            else evaluator(get_considered_prs(repo, session), repo, evaluator_args)
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
