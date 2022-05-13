from sqlalchemy import func, extract

from definitions import Repository, PullRequest
from sqlalchemy.orm import Query


class Result:
    def __str__(self) -> str:
        return super().__str__()


# TODO return proper structure
def review_window_metric(considered: Query, repo: Repository):
    return considered.add_columns((
                                      func.trunc(
                                          (
                                                  extract('epoch', PullRequest.closed_at) -
                                                  extract('epoch', PullRequest.created_at)
                                          ) / 60)
                                  ).label("metric"))


# TODO return proper structure
def review_window_per_line_metric(considered: Query, repo: Repository):
    return considered.add_columns((
                                      func.trunc(
                                          (
                                                  extract('epoch', PullRequest.closed_at) -
                                                  extract('epoch', PullRequest.created_at)
                                          ) / 60 / (PullRequest.additions+PullRequest.deletions))
                                  ).label("metric"))
