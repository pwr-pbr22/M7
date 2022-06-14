from typing import List

from sqlalchemy import func, extract, select, column
from sqlalchemy.orm import Query, Session

from definitions import Repository, PullRequest, Review


class Result:
    def __init__(self, metric_name: str, repo: Repository, considered: Query, evaluated: Query):
        self.metric_name = metric_name
        self.repo = repo
        self.considered = considered
        self.evaluated = evaluated

    def to_list(self, session) -> List[float]:
        measures = list(
            map(lambda r: float(r[0]) if r[0] is not None else None,
                session.execute(select(column(self.metric_name)).select_from(self.evaluated.subquery())).all()))
        numeric_entries = list(filter(lambda e: e is not None, measures))
        average = sum(numeric_entries) / len(numeric_entries) if len(numeric_entries) > 0 else float("nan")
        return list(map(lambda e: e if e is not None else average, measures))


# noinspection PyTypeChecker
def review_window_metric(considered: Query, repo: Repository) -> Result:
    name = "review_window"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns((
                                             func.trunc(
                                                 (
                                                         extract('epoch', PullRequest.closed_at) -
                                                         extract('epoch', PullRequest.created_at)
                                                 ) / 60)
                                         ).label(name))
                  )


# noinspection PyTypeChecker
def review_window_per_line_metric(considered: Query, repo: Repository) -> Result:
    name = "review_window_per_line"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns((
                                             func.trunc(
                                                 (
                                                         extract('epoch', PullRequest.closed_at) -
                                                         extract('epoch', PullRequest.created_at)
                                                 ) / 60 / (PullRequest.additions + PullRequest.deletions))
                                         ).label(name))
                  )


# noinspection PyTypeChecker
def review_chars(considered: Query, repo: Repository) -> Result:
    name = "review_chars"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns(
                      (Session().query((
                                           func.sum(func.char_length(Review.body)))
                                       .filter(PullRequest.id == Review.pull_id))
                       ).label(name)))


# noinspection PyTypeChecker
def review_chars_code_lines_ratio(considered: Query, repo: Repository):
    name = "review_chars_per_loc"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns(
                      Session().query(
                          func.div(
                              func.sum(func.char_length(Review.body)).filter(PullRequest.id == Review.pull_id),
                              (
                                      PullRequest.additions - PullRequest.deletions
                              )
                          )
                      ).label(name)
                  )
                  )


# noinspection PyTypeChecker
def reviewed_lines_per_hour(considered: Query, repo: Repository):
    name = "reviewed_lines_per_hour"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns(
                      Session().query(
                          # func.div(
                          func.sum(func.char_length(Review.body)).filter(PullRequest.id == Review.pull_id) /
                          func.trunc((
                                  extract('epoch', PullRequest.closed_at) -
                                  extract('epoch', PullRequest.created_at)
                          ))
                          # )
                      ).label(name)
                  )
                  )


# noinspection PyTypeChecker
def no_of_reviewers(considered: Query, repo: Repository) -> Result:
    name = "no_of_reviewers"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns(
                      (Session().query((func.count(Review.user_id).filter(PullRequest.id == Review.pull_id)))).label(
                          name)))


# noinspection PyTypeChecker
def no_of_reviewers_diff_than_author(considered: Query, repo: Repository) -> Result:
    name = "no_of_reviewers_diff_than_author"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns(
                      (Session().query((func.count(Review.user_id).filter(
                          PullRequest.id == Review.pull_id and PullRequest.user_id != Review.user_id)))).label(
                          name)))


# noinspection PyTypeChecker
def no_of_reviews(considered: Query, repo: Repository) -> Result:
    name = "no_of_reviews"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns(
                      (Session().query((func.count(Review.id).filter(
                          PullRequest.id == Review.pull_id)))).label(
                          name))
                  )


# def no_of_fixes(considered: Query, repo: Repository) -> Result:
#     name = "no_of_fixes"
#     return Result(name,
#                   repo,
#                   considered,
#                   considered.add_columns(
#                       (Session().query((func.count(.id).filter(PullRequest.id == Review.pull_id)))).label(
#                       name))
#     )


# noinspection PyTypeChecker
def ping_pong(considered: Query, repo: Repository) -> Result:
    name = "ping_pong"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns(
                      (Session().query((func.count(Review.id).filter(
                          PullRequest.id == Review.pull_id and func.count(Review.id) > 3)))).label(
                          name))
                  )
