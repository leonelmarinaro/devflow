"""
Daily Standup: recolecta actividad de GitHub (FARO-DataLab) y envía a Slack + Obsidian.

Invocado via: POST /api/automations/process  { "action": "daily_standup", "payload": {} }
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from loguru import logger


# ---------------------------------------------------------------------------
# Fecha
# ---------------------------------------------------------------------------
def _get_date_range(timezone: str) -> tuple[datetime, str, str, datetime]:
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    if now.weekday() == 0:  # Lunes
        since = now - timedelta(days=3)
        period_label = "Viernes a Lunes"
    else:
        since = now - timedelta(days=1)
        period_label = "ayer"
    return since, period_label, now.strftime("%Y-%m-%d"), now


# ---------------------------------------------------------------------------
# GitHub REST API
# ---------------------------------------------------------------------------
def _repo_name(repository_url: str) -> str:
    return repository_url.rstrip("/").split("/")[-1]


def _pr_state(item: dict) -> str:
    pr = item.get("pull_request", {})
    if pr.get("merged_at"):
        return "MERGED"
    return item.get("state", "closed").upper()


async def _search(client: httpx.AsyncClient, endpoint: str, q: str, per_page: int = 30) -> list[dict]:
    params = {"q": q, "per_page": per_page, "sort": "updated"}
    headers = {}
    if endpoint == "commits":
        # La API de búsqueda de commits requiere este header
        headers["Accept"] = "application/vnd.github.cloak-preview"
    try:
        resp = await client.get(
            f"https://api.github.com/search/{endpoint}",
            params=params,
            headers=headers,
        )
        if resp.status_code == 200:
            return resp.json().get("items", [])
        logger.warning(f"GitHub search/{endpoint} → {resp.status_code}: {resp.text[:200]}")
        return []
    except httpx.RequestError as e:
        logger.error(f"Error llamando GitHub API ({endpoint}): {e}")
        return []


async def _collect(since: datetime, org: str, username: str, token: str) -> dict:
    since_str = since.strftime("%Y-%m-%d")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # 1. Commits propios
        raw_commits = await _search(
            client, "commits",
            f"author:{username} org:{org} author-date:>={since_str}",
            per_page=50,
        )
        commits = []
        for c in raw_commits:
            date_str = c.get("commit", {}).get("author", {}).get("date", "")
            msg = c.get("commit", {}).get("message", "").split("\n")[0].strip()
            if any(msg.startswith(p) for p in ("Merge pull request", "Merge branch", "Merge remote-tracking")):
                continue
            commits.append({
                "repo": c.get("repository", {}).get("name", ""),
                "message": msg,
                "sha": c.get("sha", "")[:7],
                "date": date_str,
            })

        # 2. PRs propios (creados en el periodo)
        raw_prs_new = await _search(
            client, "issues",
            f"is:pr author:{username} org:{org} created:>={since_str}",
        )
        # 3. PRs propios (cerrados en el periodo)
        raw_prs_closed = await _search(
            client, "issues",
            f"is:pr author:{username} org:{org} state:closed closed:>={since_str}",
        )
        seen_prs: set[tuple] = set()
        prs_done = []
        for item in raw_prs_new + raw_prs_closed:
            key = (item.get("number"), _repo_name(item.get("repository_url", "")))
            if key in seen_prs:
                continue
            seen_prs.add(key)
            prs_done.append({
                "number": item.get("number"),
                "title": item.get("title", ""),
                "state": _pr_state(item),
                "repo": _repo_name(item.get("repository_url", "")),
                "url": item.get("html_url", ""),
            })

        # 4. Issues cerrados por el usuario
        raw_issues_closed = await _search(
            client, "issues",
            f"is:issue org:{org} author:{username} state:closed closed:>={since_str}",
            per_page=20,
        )
        issues_closed = [
            {
                "number": i.get("number"),
                "title": i.get("title", ""),
                "repo": _repo_name(i.get("repository_url", "")),
                "url": i.get("html_url", ""),
            }
            for i in raw_issues_closed
        ]

        # 5. PRs abiertos de otros en la org (para revisar)
        raw_prs_open = await _search(
            client, "issues",
            f"is:pr org:{org} state:open",
            per_page=20,
        )
        prs_to_review = [
            {
                "number": pr.get("number"),
                "title": pr.get("title", ""),
                "repo": _repo_name(pr.get("repository_url", "")),
                "author": pr.get("user", {}).get("login", ""),
                "url": pr.get("html_url", ""),
            }
            for pr in raw_prs_open
            if pr.get("user", {}).get("login", "") != username
        ]

        # 6. Issues abiertos donde participa el usuario
        raw_issues_open = await _search(
            client, "issues",
            f"is:issue org:{org} involves:{username} state:open",
            per_page=20,
        )
        seen_issues: set[tuple] = set()
        issues_open = []
        for i in raw_issues_open:
            key = (i.get("number"), _repo_name(i.get("repository_url", "")))
            if key not in seen_issues:
                seen_issues.add(key)
                issues_open.append({
                    "number": i.get("number"),
                    "title": i.get("title", ""),
                    "repo": _repo_name(i.get("repository_url", "")),
                    "url": i.get("html_url", ""),
                })

    logger.info(
        f"GitHub: {len(commits)} commits, {len(prs_done)} PRs propios, "
        f"{len(issues_closed)} issues cerrados, {len(prs_to_review)} PRs por revisar, "
        f"{len(issues_open)} issues abiertos"
    )
    return {
        "commits": commits,
        "prs_done": prs_done,
        "issues_closed": issues_closed,
        "prs_to_review": prs_to_review,
        "issues_open": issues_open,
    }


# ---------------------------------------------------------------------------
# Helpers de formato
# ---------------------------------------------------------------------------
def _group_by_repo(items: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for item in items:
        result.setdefault(item.get("repo", "?"), []).append(item)
    return result


# ---------------------------------------------------------------------------
# Formato Obsidian (Markdown)
# ---------------------------------------------------------------------------
_WEEKDAY_ES = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo"}


def _format_markdown(data: dict, period_label: str, today_str: str, now: datetime) -> str:
    day_name = _WEEKDAY_ES.get(now.weekday(), "")
    timestamp = now.strftime("%Y-%m-%d %H:%M ART")
    lines = [
        "---",
        f'fecha: "{today_str}"',
        "tipo: daily-standup",
        "tags:",
        "  - daily",
        "  - standup",
        f'periodo: "{period_label}"',
        "---",
        f"# Daily Standup — {today_str} ({day_name})",
        "",
        f"## Ayer hice ({period_label})",
        "",
    ]

    commits = data["commits"]
    lines.append(f"### Commits ({len(commits)})")
    for c in commits:
        lines.append(f"- `{c['repo']}` — {c['message']}")
    if not commits:
        lines.append("_Sin commits en el periodo._")
    lines.append("")

    prs = data["prs_done"]
    lines.append(f"### PRs ({len(prs)})")
    for pr in prs:
        lines.append(f"- [{pr['state']}] [#{pr['number']} {pr['title']}]({pr['url']}) — `{pr['repo']}`")
    if not prs:
        lines.append("_Sin PRs en el periodo._")
    lines.append("")

    issues_c = data["issues_closed"]
    lines.append(f"### Issues cerrados ({len(issues_c)})")
    for i in issues_c:
        lines.append(f"- [#{i['number']} {i['title']}]({i['url']}) — `{i['repo']}`")
    if not issues_c:
        lines.append("_Sin issues cerrados._")
    lines.append("")

    lines.append("## Para revisar hoy")
    lines.append("")

    prs_rev = data["prs_to_review"]
    lines.append(f"### PRs abiertos de la org ({len(prs_rev)})")
    for pr in prs_rev:
        lines.append(f"- [#{pr['number']} {pr['title']}]({pr['url']}) — `{pr['repo']}` (@{pr['author']})")
    if not prs_rev:
        lines.append("_Sin PRs abiertos de otros._")
    lines.append("")

    issues_o = data["issues_open"]
    lines.append(f"### Issues abiertos donde participo ({len(issues_o)})")
    for i in issues_o:
        lines.append(f"- [#{i['number']} {i['title']}]({i['url']}) — `{i['repo']}`")
    if not issues_o:
        lines.append("_Sin issues asignados._")
    lines.append("")

    lines += ["---", f"_Generado el {timestamp}_"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formato Slack (Block Kit)
# ---------------------------------------------------------------------------
def _sl(text: str, url: str) -> str:
    return f"<{url}|{text}>"


def _format_slack(data: dict, period_label: str, today_str: str, now: datetime) -> list[dict]:
    day_name = _WEEKDAY_ES.get(now.weekday(), "")

    def section(text: str) -> dict:
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

    def divider() -> dict:
        return {"type": "divider"}

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Daily Standup — {today_str} ({day_name})"}},
        section(f"_Periodo: {period_label}_"),
        divider(),
        section("*Ayer hice*"),
    ]

    commits_by_repo = _group_by_repo(data["commits"])
    prs_by_repo = _group_by_repo(data["prs_done"])
    issues_c_by_repo = _group_by_repo(data["issues_closed"])
    repos_ayer = set(commits_by_repo) | set(prs_by_repo) | set(issues_c_by_repo)

    if repos_ayer:
        for repo in sorted(repos_ayer):
            lines = [f"*{repo}*"]
            for c in commits_by_repo.get(repo, [])[:6]:
                lines.append(f"  \u2022 {c['message']}")
            for pr in prs_by_repo.get(repo, [])[:5]:
                pr_label = f"#{pr['number']} {pr['title']}"
                lines.append(f"  \u2022 [{pr['state']}] {_sl(pr_label, pr['url'])}")
            for i in issues_c_by_repo.get(repo, [])[:3]:
                i_label = f"#{i['number']} {i['title']}"
                lines.append(f"  \u2022 {_sl(i_label, i['url'])}")
            blocks.append(section("\n".join(lines)))
    else:
        blocks.append(section("_Sin actividad en el periodo._"))

    blocks.append(divider())
    blocks.append(section("*Para revisar hoy*"))

    prs_rev = data["prs_to_review"]
    if prs_rev:
        blocks.append(section(f"_PRs abiertos en la org ({len(prs_rev)})_"))
        for repo, items in sorted(_group_by_repo(prs_rev).items()):
            lines = [f"*{repo}*"]
            for pr in items[:4]:
                pr_label = f"#{pr['number']} {pr['title']}"
                lines.append(f"  \u2022 {_sl(pr_label, pr['url'])} @{pr['author']}")
            blocks.append(section("\n".join(lines)))
    else:
        blocks.append(section("_Sin PRs de otros abiertos._"))

    issues_o = data["issues_open"]
    if issues_o:
        blocks.append(section(f"_Issues donde participo ({len(issues_o)})_"))
        for repo, items in sorted(_group_by_repo(issues_o).items()):
            lines = [f"*{repo}*"]
            for i in items[:4]:
                i_label = f"#{i['number']} {i['title']}"
                lines.append(f"  \u2022 {_sl(i_label, i['url'])}")
            blocks.append(section("\n".join(lines)))
    else:
        blocks.append(section("_Sin issues abiertos asignados._"))

    return blocks


# ---------------------------------------------------------------------------
# Envío a destinos
# ---------------------------------------------------------------------------
async def _send_slack(webhook_url: str, blocks: list[dict]) -> bool:
    chunks = [blocks[i: i + 50] for i in range(0, len(blocks), 50)]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for chunk in chunks:
                resp = await client.post(webhook_url, json={"blocks": chunk})
                if not resp.is_success:
                    logger.error(f"Slack error {resp.status_code}: {resp.text[:200]}")
                    return False
        return True
    except httpx.RequestError as e:
        logger.error(f"Slack request failed: {e}")
        return False


def _write_obsidian(inbox_path: str, today_str: str, content: str) -> bool:
    inbox = Path(inbox_path)
    inbox.mkdir(parents=True, exist_ok=True)
    filepath = inbox / f"daily_report_{today_str}.md"
    try:
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Obsidian: {filepath}")
        return True
    except OSError as e:
        logger.error(f"Error escribiendo en Obsidian: {e}")
        return False


# ---------------------------------------------------------------------------
# Entry point (action handler)
# ---------------------------------------------------------------------------
async def generate_standup(payload: dict) -> dict:
    """
    Action handler registrado en processor.py.
    Lee config desde variables de entorno.
    """
    org = os.environ.get("GITHUB_ORG", "FARO-DataLab")
    username = os.environ.get("GITHUB_USERNAME", "leonelmarinaro")
    token = os.environ.get("GITHUB_TOKEN", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    inbox_path = os.environ.get("OBSIDIAN_INBOX_PATH", "")
    timezone = os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires")

    if not token:
        raise ValueError("GITHUB_TOKEN no configurado")

    since, period_label, today_str, now = _get_date_range(timezone)
    logger.info(f"Daily standup: {today_str} | periodo: {period_label}")

    data = await _collect(since, org, username, token)

    md_content = _format_markdown(data, period_label, today_str, now)
    slack_blocks = _format_slack(data, period_label, today_str, now)

    results = {}

    if slack_webhook:
        results["slack"] = await _send_slack(slack_webhook, slack_blocks)
    else:
        logger.warning("SLACK_WEBHOOK_URL no configurado, omitiendo envio")
        results["slack"] = None

    if inbox_path:
        results["obsidian"] = _write_obsidian(inbox_path, today_str, md_content)
    else:
        logger.warning("OBSIDIAN_INBOX_PATH no configurado, omitiendo escritura")
        results["obsidian"] = None

    return {
        "date": today_str,
        "period": period_label,
        "stats": {
            "commits": len(data["commits"]),
            "prs_done": len(data["prs_done"]),
            "issues_closed": len(data["issues_closed"]),
            "prs_to_review": len(data["prs_to_review"]),
            "issues_open": len(data["issues_open"]),
        },
        "destinations": results,
    }
