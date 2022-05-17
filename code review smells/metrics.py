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
        return list(map(lambda r: float(r[0]),
                        session.execute(select(column(self.metric_name)).select_from(self.evaluated.subquery())).all()))


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
    name = "review_window"
    return Result(name,
                  repo,
                  considered,
                  considered.add_columns((
                                             func.trunc(
                                                 (
                                                         extract('epoch', PullRequest.closed_at) -
                                                         extract('epoch', PullRequest.created_at)
                                                 ) / 60 / (PullRequest.additions+PullRequest.deletions))
                                         ).label(name))
                  )
