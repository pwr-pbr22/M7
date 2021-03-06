import asyncio
import json
import os
import random
import re
import time
from datetime import datetime

import aiohttp
import requests

import db
from configuration import ProjectConfiguration
from definitions import User, PullRequest, Repository, AuthorAssociationEnum, Review, ReviewStatusesEnum, Commit


def cls() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')


def _count_subpages(url: str) -> int:
    github_token = random.choice(github_tokens)
    pattern = re.compile('([0-9]+)>; rel="last"')
    request = requests.get(url, headers={"Authorization": f"token {github_token}"})
    if request.status_code != 200:
        print(f"Failed to fetch the number of pages for {url}")
        print(request.text)
        return 0
    try:
        repo = json.loads(request.text)[0]["base"]["repo"]
        session = db.get_session()
        session.merge(User(
            id=repo["owner"]["id"],
            login=repo["owner"]["login"]
        ))
        session.merge(Repository(
            id=repo["id"],
            name=repo["name"],
            full_name=repo["full_name"],
            owner_id=repo["owner"]["id"]
        ))
        session.commit()
        session.close()
    except:
        pass
    # przemilczmy jakość kodu w tym miejscu
    return int(pattern.search(request.headers["Link"]).group(1)) if "Link" in request.headers else 1


def _print_status(general: str, overall: float, started: datetime) -> None:
    cls()
    print(general)
    print(f"Done in: 0%{' ' * 94}100%")
    line4 = f"General: {'#' * int(overall * 100)}".ljust(110, " ")
    print(line4 + "{:.2f}".format(overall * 100) + "%")
    if overall > 0:
        delta = (datetime.now() - started).seconds
        remaining_time = delta / overall - delta
        print(f"\nRemaining time: {int(remaining_time // 60)}m{int(remaining_time % 60)}s")


async def _fetch_pr(session: aiohttp.ClientSession, link: str):
    github_token = random.choice(github_tokens)

    async def _get_results(url):
        request = await session.request('GET',
                                        url=url,
                                        headers={"Authorization": f"token {github_token}"})
        if request.status == 403:
            waiting = int(request.headers["x-ratelimit-reset"]) - int(time.time()) + 60
            print(f"\n[{datetime.now()}] Exceeded number of requests, waiting {waiting // 60}m{waiting % 60}s",
                  end="")
            time.sleep(waiting)
            return await _fetch_pr(session, link)
        elif request.status >= 400:
            print(f"\n[{datetime.now()}] Something went wrong\n"
                  f"\tstatus:\t{request.status}/{request.status}/{request.status}\n"
                  f"\taddress:\t{link}\n"
                  f"\tnext request in 1 minute", end="")
            return await _fetch_pr(session, link)
        else:
            return await request.json(), request

    async def _get_paginated_results(url):
        results, request = await _get_results(url)
        all_results = [results]
        while request.links is not None and request.links.get('next') is not None:
            results, request = await _get_results(request.links.get('next').get('url'))
            all_results.append(results)
        return all_results

    def _add_pull_to_db() -> None:
        # pr user
        dbsession.merge(User(
            id=pull["user"]["id"],
            login=pull["user"]["login"]
        ))
        # pr assignee
        if pull["assignee"] is not None:
            dbsession.merge(User(
                id=pull["assignee"]["id"],
                login=pull["assignee"]["login"]
            ))
        # pr pull
        pr = PullRequest(
            id=pull["id"],
            number=pull["number"],
            title=pull["title"],
            user_id=pull["user"]["id"] if pull["user"] is not None else None,
            body=pull["body"],
            created_at=pull["created_at"],
            closed_at=pull["closed_at"],
            assignee_id=pull["assignee"]["id"] if pull["assignee"] is not None else None,
            repository_id=pull["base"]["repo"]["id"],
            author_association=AuthorAssociationEnum[pull["author_association"]],
            merged=pull["merged"],
            additions=pull["additions"],
            deletions=pull["deletions"])
        # pr assignees
        for assignee in pull["assignees"]:
            user = User(
                id=assignee["id"],
                login=assignee["login"]
            )
            dbsession.merge(user)
            pr.assignees.append(user)
        dbsession.merge(pr)
        dbsession.commit()

    def _add_reviews_to_db() -> None:
        for page in review_pages:
            for review in page:
                # rev user
                if review["user"] is not None:
                    dbsession.merge(User(
                        id=review["user"]["id"],
                        login=review["user"]["login"]
                    ))
                # rev
                dbsession.merge(Review(
                    id=review["id"],
                    pull_id=pull["id"],
                    user_id=review["user"]["id"] if review["user"] is not None else None,
                    body=review["body"],
                    state=ReviewStatusesEnum[review["state"]],
                    author_association=AuthorAssociationEnum[review["author_association"]],
                    submitted_at=review["submitted_at"]
                ))

    try:
        commit_pages = await _get_paginated_results(link + '/commits')
        dbsession = db.get_session()

        for page in commit_pages:
            for commit in page:
                if dbsession.query(Commit).get(commit['sha']):
                    pull, _ = await _get_results(link)
                    review_pages = await _get_paginated_results(link + '/reviews')
                    _add_pull_to_db()
                    _add_reviews_to_db()
                    dbsession.commit()
                    pr = dbsession.query(PullRequest).get(pull['id'])
                    for page2 in commit_pages:
                        for commit2 in page2:
                            db_commit = dbsession.query(Commit).get(commit2['sha'])
                            if db_commit:
                                pr.commits.append(db_commit)
                    dbsession.merge(pr)
                    dbsession.commit()
                    dbsession.close()
                    print("Saved", pull['id'])
                    return
        dbsession.close()
    except Exception as e:
        print(f"\n[{datetime.now()}] Something went wrong\n"
              f"\taddress:\t{link}\n"
              f"{repr(e)}", end="")
        await _fetch_pr(session, link)


async def download_project_pulls(project: str) -> None:
    started = datetime.now()
    subpages = _count_subpages(
        f"https://api.github.com/repos/{project}/pulls?state=closed&direction=asc&per_page=100")
    for i in range(1, subpages + 1):
        _print_status(f"Downloading PR subpage: {i} of {subpages} for {project} (≈{subpages * 300} requests)",
                      (i - 1) / subpages,
                      started)
        links = list(map(lambda entry: entry["url"], json.loads(_fetch(
            f"https://api.github.com/repos/{project}/pulls?state=closed&direction=asc&per_page=100&page={i}"))))
        async with aiohttp.ClientSession() as session:
            tasks = []
            for link in links:
                tasks.append(_fetch_pr(session, link))
            await asyncio.gather(*tasks, return_exceptions=True)
            await session.close()
        _print_status(f"Downloading PR subpage: {i} of {subpages} for {project} (≈{subpages * 300} requests)",
                      i / subpages, started)


def _fetch(url: str) -> str:
    github_token = random.choice(github_tokens)
    try:
        request = requests.get(url, headers={"Authorization": f"token {github_token}"},
                               timeout=10)
    except Exception as e:
        print(f"\n[{datetime.now()}] Something went wrong\n"
              f"\taddress:\t{url}\n"
              f"{repr(e)}", end="")
        return _fetch(url)
    if request.status_code < 400:
        return request.text
    elif request.status_code == 403:
        waiting = int(request.headers["x-ratelimit-reset"]) - int(time.time()) + 60
        print(f"\n[{datetime.now()}] Exceeded number of requests, waiting {waiting // 60}m{waiting % 60}s", end="")
        time.sleep(waiting)
    else:
        print(f"\n[{datetime.now()}] Something went wrong\n"
              f"\tstatus:\t{request.status_code}\n"
              f"\taddress:\t{request.url}\n"
              f"\tnext request in 1 minute", end="")
    return _fetch(url)


if __name__ == '__main__':
    config = ProjectConfiguration()
    db.prepare(config.connstr)
    github_tokens = config.gh_keys

    for project in config.projects:
        asyncio.run(download_project_pulls(project))
