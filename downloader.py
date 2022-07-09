import asyncio
import json
import os
import random
import re
import sys
import time
from datetime import datetime

import aiohttp
import requests

import db
from definitions import User, PullRequest, Repository, AuthorAssociationEnum, Review, ReviewStatusesEnum, File, \
    FileChange


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def _count_subpages(url):
    github_token = random.choice(github_tokens)[0]
    pattern = re.compile('([0-9]+)>; rel="last"')
    request = requests.get(url, headers={"Authorization": f"token {github_token}"})
    if request.status_code != 200:
        print(f"Failed to fetch the number of pages for {url}")
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
    except Exception:
        pass
    return int(pattern.search(request.headers["Link"]).group(1)) if "Link" in request.headers else 1


def _print_status(general, overall: float, started):
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
    github_token = random.choice(github_tokens)[0]

    async def _request():
        pull_request = await session.request('GET',
                                             url=link,
                                             headers={"Authorization": f"token {github_token}"})
        reviews_request = await session.request('GET',
                                                url=link + "/reviews",
                                                headers={"Authorization": f"token {github_token}"})
        files_request = await session.request('GET',
                                              url=link + "/files",
                                              headers={"Authorization": f"token {github_token}"})
        if pull_request.status == 403 or reviews_request.status == 403 or files_request.status == 403:
            waiting = int(files_request.headers["x-ratelimit-reset"]) - int(time.time()) + 60
            print(f"\n[{datetime.now()}] Exceeded number of requests, waiting {waiting // 60}m{waiting % 60}s",
                  end="")
            time.sleep(waiting)
            return await _fetch_pr(session, link)
        elif pull_request.status >= 400 or reviews_request.status >= 400 or files_request.status >= 400:
            print(f"\n[{datetime.now()}] Something went wrong\n"
                  f"\tstatus:\t{pull_request.status}/{reviews_request.status}/{files_request.status}\n"
                  f"\taddress:\t{link}\n"
                  f"\tnext request in 1 minute", end="")
            time.sleep(60)
            return await _fetch_pr(session, link)
        return await pull_request.json(), await reviews_request.json(), await files_request.json()

    def _add_pull_to_db():
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

    def _add_revs_to_db():
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
                pull_id=pull["id"],
                user_id=review["user"]["id"] if review["user"] is not None else None,
                body=review["body"],
                state=ReviewStatusesEnum[review["state"]],
                author_association=AuthorAssociationEnum[review["author_association"]],
                submitted_at=review["submitted_at"]
            ))

    def _add_files_to_db():
        pr = dbsession.query(PullRequest).get(pull["id"])
        for file in files_changed:
            # add or update files to db
            existing = dbsession.query(File).get({"filename": file["filename"], "repo_id": pr.repository_id})
            if existing is None:
                new_file = File(filename=file["filename"], repo_id=pr.repository_id)
                if file["status"] == "deleted":
                    new_file.lastDeleted = pr.closed_at
                elif file["status"] == "added":
                    new_file.firstMerged = pr.closed_at
                dbsession.add(new_file)
                existing = new_file
            else:
                if file["status"] == "deleted" and (
                        existing.lastDeleted is None or existing.lastDeleted < pr.closed_at):
                    existing.lastDeleted = pr.closed_at
                elif file["status"] == "added" and (
                        existing.firstMerged is None or existing.firstMerged > pr.closed_at):
                    existing.firstMerged = pr.closed_at
            # add to info on pull
            if dbsession.query(FileChange).get(
                    {"filename": existing.filename, "repo_id": existing.repo_id, "pull_id": pr.id}) is None:
                change = FileChange(additions=file["additions"],
                                    deletions=file["deletions"],
                                    changes=file["changes"]
                                    )
                change.file = existing
                change.pull = pr

    try:
        pull, revs, files_changed = await _request()

        dbsession = db.get_session()

        _add_pull_to_db()
        _add_revs_to_db()
        dbsession.commit()

        _add_files_to_db()
        dbsession.commit()

        dbsession.close()
    except Exception as e:
        print(f"\n[{datetime.now()}] Something went wrong\n"
              f"\taddress:\t{link}\n"
              f"\tnext request in 1 minute\n"
              f"{repr(e)}", end="")
        time.sleep(60)
        await _fetch_pr(session, link)


async def download_project_pulls(project):
    started = datetime.now()
    subpages = _count_subpages(
        f"https://api.github.com/repos/{project}/pulls?state=closed&direction=asc&per_page=100")
    for i in range(1, subpages + 1):
        _print_status(f"Downloading PR subpage: {i} of {subpages} (≈{subpages * 300} requests)", (i - 1) / subpages,
                      started)
        links = list(map(lambda entry: entry["url"], json.loads(_fetch(
            f"https://api.github.com/repos/{project}/pulls?state=closed&direction=asc&per_page=100&page={i}"))))
        async with aiohttp.ClientSession() as session:
            tasks = []
            for link in links:
                tasks.append(_fetch_pr(session, link))
            await asyncio.gather(*tasks, return_exceptions=True)
            await session.close()
        _print_status(f"Downloading PR subpage: {i} of {subpages} (≈{subpages * 300} requests)", i / subpages, started)


def _fetch(url):
    github_token = random.choice(github_tokens)[0]
    try:
        request = requests.get(url, headers={"Authorization": f"token {github_token}"},
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
    if len(sys.argv) < 4:
        print("Not sufficient args")
    else:
        github_tokens = list(map(lambda token: (token, True, datetime.now()), sys.argv[3:]))

        if db.prepare(sys.argv[1]):
            asyncio.run(download_project_pulls(sys.argv[2]))
        else:
            print("Can't connect to db")
