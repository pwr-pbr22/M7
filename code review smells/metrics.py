from typing import List

from sqlalchemy import func, extract, select, column

from definitions import Repository, PullRequest
from sqlalchemy.orm import Query


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


def count_reviews_chards(reviews):
    return sum(map(lambda r: r.review_chars, reviews))


def review_chars(considered: Query, repo: Repository) -> Result:
    name = "review_chars"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns((
                                             count_reviews_chards(PullRequest.reviews)).label(name)))


def review_chars_code_lines_ratio(considered: Query, repo: Repository):
    name = "review_chars_per_loc"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns((
                                                 count_reviews_chards(PullRequest.reviews) / (
                                                 PullRequest.additions - PullRequest.deletions)).label(name)))


def count_reviews_hours(reviews, creation_time):
    return sum(map(lambda r: r.submitted_at - creation_time, reviews)) / len(reviews)


def reviewed_lines_per_hour(considered: Query, repo: Repository):
    name = "reviewed_lines_per_hour"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns((
                                                 (
                                                         PullRequest.additions - PullRequest.deletions) /
                                                 count_reviews_hours(PullRequest.reviews,
                                                                     PullRequest.created_at)).label(name)))
