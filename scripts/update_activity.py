#!/usr/bin/env python3
"""Refresh public GitHub data atomically; never replace it with invented or empty data."""
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
    repositories(first: 30, privacy: PUBLIC, isFork: false,
      ownerAffiliations: OWNER, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        nameWithOwner
        defaultBranchRef { target { ... on Commit {
          history(first: 2) { nodes { oid messageHeadline committedDate url } }
        } } }
      }
    }
  }
}
"""


def normalize(response, login):
    if response.get("errors"):
        raise ValueError("GitHub GraphQL returned errors")
    user = response.get("data", {}).get("user")
    if not user:
        raise ValueError("GitHub user not found")
    calendar = user["contributionsCollection"]["contributionCalendar"]
    if not calendar.get("weeks"):
        raise ValueError("GitHub returned no calendar")
    commits = []
    for repo in user["repositories"]["nodes"]:
        if repo["nameWithOwner"].lower() == f"{login}/{login}".lower():
            continue  # Keep automated profile refreshes out of the build log.
        branch = repo.get("defaultBranchRef")
        for commit in (branch or {}).get("target", {}).get("history", {}).get("nodes", []):
            commits.append({"repo": repo["nameWithOwner"], "sha": commit["oid"],
                            "message": commit["messageHeadline"], "date": commit["committedDate"], "url": commit["url"]})
    if not commits:
        raise ValueError("GitHub returned no public project commits")
    commits.sort(key=lambda x: x["date"], reverse=True)
    return {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "calendar": calendar, "commits": commits[:3]}


def main():
    login = os.environ.get("PROFILE_LOGIN", "jesusjodar")
    token = os.environ["GH_TOKEN"]
    request = urllib.request.Request("https://api.github.com/graphql", method="POST",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "jesusjodar-profile", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        result = normalize(json.load(response), login)
    path = ROOT/"data/activity.json"
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    main()
