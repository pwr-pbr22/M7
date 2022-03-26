import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime

import aiohttp
import requests

import db
from definitions import User, PullRequest, Repository, AuthorAssociationEnum, Review, ReviewStatusesEnum


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def _countSubpages(url):
    pattern = re.compile('([0-9]+)>; rel="last"')
    request = requests.get(url, headers={"Authorization": f"token {githubToken}"})
    if request.status_code != 200:
        print(f"Failed to fetch the number of pages for {url}")
        return 0
    repo = json.loads(request.text)[0]["base"]["repo"]
    session = db.getSession()
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
    session.close()
    return int(pattern.search(request.headers["Link"]).group(1))


def _printStatus(general, overall: float, started):
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
    try:
        resp = await session.request('GET',
                                     url=link,
                                     headers={"Authorization": f"token {githubToken}"})
        resp2 = await session.request('GET',
                                      url=link + "/reviews",
                                      headers={"Authorization": f"token {githubToken}"})
        if resp.status == 403 or resp2.status == 403:
            waiting = int(resp.headers["x-ratelimit-reset"]) - int(time.time()) + 60
            print(f"\n[{datetime.now()}] Exceeded number of requests, waiting {waiting // 60}m{waiting % 60}s", end="")
            time.sleep(waiting)
            return await _fetch_pr(session, link)
        elif resp.status > 400 or resp2.status > 400:
            print(f"\n[{datetime.now()}] Something went wrong\n"
                  f"\tstatus:\t{resp.status}\n"
                  f"\taddress:\t{link}\n"
                  f"\tnext request in 1 minute", end="")
            time.sleep(60)
            return await _fetch_pr(session, link)

        response = await resp.json()
        revs = await resp2.json()
        dbsession = db.getSession()
        # pr user
        dbsession.merge(User(
            id=response["user"]["id"],
            login=response["user"]["login"]
        ))
        # pr assignee
        if response["assignee"] is not None:
            dbsession.merge(User(
                id=response["assignee"]["id"],
                login=response["assignee"]["login"]
            ))
        # pr pull
        pr = PullRequest(
            id=response["id"],
            number=response["number"],
            title=response["title"],
            user_id=response["user"]["id"] if response["user"] is not None else None,
            body=response["body"],
            created_at=response["created_at"],
            closed_at=response["closed_at"],
            assignee_id=response["assignee"]["id"] if response["assignee"] is not None else None,
            repository_id=response["base"]["repo"]["id"],
            author_association=AuthorAssociationEnum[response["author_association"]],
            merged=response["merged"],
            additions=response["additions"],
            deletions=response["deletions"],
            changed_files=response["changed_files"])
        # pr assignees
        for assignee in response["assignees"]:
            user = User(
                id=assignee["id"],
                login=assignee["login"]
            )
            dbsession.merge(user)
            pr.assignees.append(user)
        dbsession.merge(pr)
        dbsession.commit()
        for review in revs:
            # rev user
            if review["user"] is not None:
                dbsession.merge(User(
                    id=review["user"]["id"],
                    login=review["user"]["login"]
                ))
            # rev
            dbsession.merge(Review(
                id=review["id"],
                pull_id=response["id"],
                user_id=review["user"]["id"] if review["user"] is not None else None,
                body=review["body"],
                state=ReviewStatusesEnum[review["state"]],
                author_association=AuthorAssociationEnum[review["author_association"]],
                submitted_at=review["submitted_at"]
            ))
        dbsession.commit()
        dbsession.close()
    except Exception as e:
        print(f"\n[{datetime.now()}] Something went wrong\n"
              f"\taddress:\t{link}\n"
              f"\tnext request in 1 minute\n"
              f"{repr(e)}", end="")
        time.sleep(60)
        await _fetch_pr(session, link)


async def downloadProjectPulls(project):
    started = datetime.now()
    subpages = _countSubpages(
        f"https://api.github.com/repos/{project}/pulls?state=closed&direction=asc&per_page=100")
    for i in range(1, subpages + 1):
        _printStatus(f"Downloading subpage: {i} of {subpages}", (i - 1) / subpages, started)
        links = list(map(lambda entry: entry["url"], json.loads(_fetch(
            f"https://api.github.com/repos/{project}/pulls?state=closed&direction=asc&per_page=100&page={i}"))))
        async with aiohttp.ClientSession() as session:
            tasks = []
            for link in links:
                tasks.append(_fetch_pr(session, link))
                await asyncio.gather(*tasks, return_exceptions=True)
        _printStatus(f"Downloading subpage: {i} of {subpages}", i / subpages, started)


def _fetch(url):
    try:
        request = requests.get(url, headers={"Authorization": f"token {githubToken}"},
                               timeout=10)
    except:
        print(f"\n[{datetime.now()}] Something went wrong\n"
              f"\taddress:\t{url}\n"
              f"\tnext request in 1 minute", end="")
        time.sleep(60)
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
        time.sleep(60)
    return _fetch(url)


if __name__ == '__main__':
    githubToken = sys.argv[1]
    if db.prepare(sys.argv[2]):
        asyncio.run(downloadProjectPulls(sys.argv[3]))
