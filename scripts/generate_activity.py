import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

USERNAME = "aditya-bobate"

API = "https://api.github.com"

OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "activity" / "activity-dashboard.svg"


def github_get(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USERNAME,
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())


def get_repositories():
    repos = []

    page = 1

    while True:
        url = (
            f"{API}/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&sort=updated"
        )

        data = github_get(url)

        if not data:
            break

        repos.extend(data)

        if len(data) < 100:
            break

        page += 1

    return repos


def get_activity(repositories, start_date):
    activity = defaultdict(int)

    for repo in repositories:
        owner = repo["owner"]["login"]
        name = repo["name"]

        page = 1

        while page <= 3:
            url = (
                f"{API}/repos/{owner}/{name}/commits"
                f"?author={USERNAME}"
                f"&since={start_date.isoformat()}"
                f"&per_page=100"
                f"&page={page}"
            )

            try:
                commits = github_get(url)
            except Exception:
                break

            if not commits:
                break

            for commit in commits:
                date_string = commit["commit"]["author"]["date"]

                date = datetime.fromisoformat(
                    date_string.replace("Z", "+00:00")
                ).date()

                if date >= start_date.date():
                    activity[date] += 1

            if len(commits) < 100:
                break

            page += 1

    return activity


def esc(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def intensity(value, maximum):
    if value == 0:
        return "#161B22"

    ratio = value / max(maximum, 1)

    if ratio <= 0.25:
        return "#0E4429"

    if ratio <= 0.50:
        return "#006D32"

    if ratio <= 0.75:
        return "#26A641"

    return "#39D353"


def build_svg(repositories, activity):
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)

    max_activity = max(activity.values(), default=1)

    total_commits = sum(activity.values())

    active_days = len(activity)

    public_repos = len(
        [repo for repo in repositories if not repo.get("private", False)]
    )

    stars = sum(repo.get("stargazers_count", 0) for repo in repositories)

    width = 1000
    height = 470

    parts = []

    parts.append(
        f'''<svg xmlns="http://www.w3.org/2000/svg"
        width="{width}"
        height="{height}"
        viewBox="0 0 {width} {height}">
        <defs>
          <linearGradient id="border" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#58A6FF"/>
            <stop offset="50%" stop-color="#A371F7"/>
            <stop offset="100%" stop-color="#3FB950"/>
          </linearGradient>
        </defs>

        <rect width="100%" height="100%" rx="14"
              fill="#0D1117"
              stroke="#30363D"/>

        <rect x="1" y="1" width="998" height="3"
              rx="2"
              fill="url(#border)"/>

        <text x="32" y="48"
              fill="#8B949E"
              font-family="monospace"
              font-size="15">
          $ hedgehog --activity
        </text>

        <text x="32" y="82"
              fill="#F0F6FC"
              font-family="monospace"
              font-size="22"
              font-weight="bold">
          GITHUB ACTIVITY MATRIX
        </text>

        <text x="32" y="108"
              fill="#8B949E"
              font-family="monospace"
              font-size="13">
          public repository activity · last 12 months
        </text>
        '''
    )

    # Matrix
    cell = 14
    gap = 4

    matrix_x = 32
    matrix_y = 145

    for i in range(365):
        date = start + timedelta(days=i)

        week = i // 7
        weekday = date.weekday()

        x = matrix_x + week * (cell + gap)
        y = matrix_y + weekday * (cell + gap)

        count = activity.get(date, 0)

        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
            f'rx="3" fill="{intensity(count, max_activity)}">'
            f'<title>{date}: {count} commit(s)</title>'
            f'</rect>'
        )

    # Stats
    stats_y = 290

    stats = [
        ("COMMITS", total_commits),
        ("ACTIVE DAYS", active_days),
        ("PUBLIC REPOS", public_repos),
        ("STARS", stars),
    ]

    for index, (label, value) in enumerate(stats):
        x = 32 + index * 235

        parts.append(
            f'''
            <text x="{x}" y="{stats_y}"
                  fill="#8B949E"
                  font-family="monospace"
                  font-size="12">
              {esc(label)}
            </text>

            <text x="{x}" y="{stats_y + 34}"
                  fill="#58A6FF"
                  font-family="monospace"
                  font-size="25"
                  font-weight="bold">
              {esc(value)}
            </text>
            '''
        )

    # Status
    status = "ACTIVE" if active_days > 0 else "QUIET"

    parts.append(
        f'''
        <line x1="32" y1="355"
              x2="968" y2="355"
              stroke="#21262D"/>

        <text x="32" y="390"
              fill="#8B949E"
              font-family="monospace"
              font-size="13">
          SYSTEM STATUS
        </text>

        <circle cx="153" cy="385"
                r="5"
                fill="#3FB950"/>

        <text x="167" y="390"
              fill="#3FB950"
              font-family="monospace"
              font-size="13"
              font-weight="bold">
          {status}
        </text>

        <text x="32" y="425"
              fill="#8B949E"
              font-family="monospace"
              font-size="12">
          Activity is generated automatically from public GitHub repositories.
        </text>

        <text x="32" y="447"
              fill="#484F58"
              font-family="monospace"
              font-size="11">
          last generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
        </text>

        </svg>
        '''
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        "\n".join(parts),
        encoding="utf-8"
    )


def main():
    print("Fetching repositories...")

    repositories = get_repositories()

    print(f"Repositories found: {len(repositories)}")

    start_date = datetime.now(timezone.utc) - timedelta(days=364)

    print("Collecting activity...")

    activity = get_activity(
        repositories,
        start_date
    )

    print(f"Active days: {len(activity)}")

    build_svg(
        repositories,
        activity
    )

    print(f"Generated: {OUTPUT}")


if __name__ == "__main__":
    main()