from datetime import datetime
from functools import reduce
from typing import Callable, List, Optional, Union
from sqlalchemy import or_, and_
from sqlalchemy.orm import Query

import db
from definitions import Repository, PullRequest, FileChange
import smells
import metrics


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
        session.commit()
    if session.execute("SELECT to_regproc('pbr.public.nextFixesBug') IS NULL;").scalar():
        session.execute("""
            CREATE FUNCTION nextFixesBug(repo_id integer, filename text, starting timestamp) RETURNS boolean AS $$
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
        session.commit()


def _next_file_change_fixes_bug(session, repo: Repository, filename: str, starting: datetime) -> Optional[bool]:
    return session.execute(f"""SELECT nextFixesBug({repo.id}, '{filename}', '{starting}'::TIMESTAMP)""").first()[0]


def evaluate(repo: str, evaluator: Callable, *args) -> Union[smells.Result, metrics.Result, None]:
    session = db.getSession()
    repository = session.query(Repository).filter(Repository.full_name == repo).first()
    if repository is None:
        session.close()
        print("Specified repository does not exist in specified database")
        return None
    session.close()
    return evaluator(get_considered_prs(repository, session), repository, *args)


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
        if any(_next_file_change_fixes_bug(session, repo, file_change.filename, file_change.pull.closed_at) for file_change
               in filechanges):
            return 1
        return 0

    ok_bugfixing = (reduce(lambda a, b: a + b,
                           list(map(lambda pr: helper(pr.changed_files), ok))) / float(ok_count)) \
        if ok_count > 0 else float("nan")
    smelly_bugfixing = (reduce(lambda a, b: a + b,
                               list(map(lambda pr: helper(pr.changed_files), smelly))) / float(smelly_count)) \
        if smelly_count > 0 else float("nan")
    return ok_bugfixing, smelly_bugfixing
