#!/usr/bin/env python3
"""
Daily Standup Automatizado
Genera un reporte con la actividad de GitHub (FARO-DataLab) del dia anterior
y lo envia a Telegram + guarda en Obsidian.

Uso:
    python3 daily_standup.py           # Ejecucion normal
    python3 daily_standup.py --dry-run # Imprime el reporte sin enviar ni guardar
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuracion de logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "standup.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

DRY_RUN = "--dry-run" in sys.argv


# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
def load_config() -> dict:
    load_dotenv(Path(__file__).parent / ".env")
    load_dotenv(Path(__file__).parent.parent / ".env")
    config = {
        "GITHUB_ORG": os.environ.get("GITHUB_ORG", "FARO-DataLab"),
        "GITHUB_USERNAME": os.environ.get("GITHUB_USERNAME", "leonelmarinaro"),
        "GH_BIN": os.environ.get("GH_BIN", "/opt/homebrew/bin/gh"),
        # Slack — destino principal del daily
        "SLACK_WEBHOOK_URL": os.environ.get("SLACK_WEBHOOK_URL", ""),
        # Telegram — disponible para futuros triggers/usos
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "OBSIDIAN_VAULT_PATH": os.environ.get(
            "OBSIDIAN_VAULT_PATH",
            "/Users/lmarinaro/Documents/Obsidian/Growketing",
        ),
        "TIMEZONE": os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires"),
        # LLM — resumen narrativo opcional (compatible OpenAI API)
        "LLM_API_KEY": os.environ.get("LLM_API_KEY", ""),
        "LLM_BASE_URL": os.environ.get(
            "LLM_BASE_URL", "https://api.groq.com/openai/v1"
        ),
        "LLM_MODEL": os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile"),
    }
    if not DRY_RUN and not config["SLACK_WEBHOOK_URL"]:
        raise ValueError("Variable de entorno faltante: SLACK_WEBHOOK_URL")
    return config


# ---------------------------------------------------------------------------
# Calculo del rango de fechas
# ---------------------------------------------------------------------------
def get_date_range(tz_name: str) -> tuple[datetime, str, str, datetime]:
    """
    Devuelve (since_dt, period_label, today_str, now).
    - Lunes: desde el viernes anterior (3 dias atras)
    - Resto: desde ayer
    """
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    weekday = now.weekday()  # 0=Lunes ... 6=Domingo

    if weekday == 0:
        since = now - timedelta(days=3)
        period_label = "Viernes a Lunes"
    else:
        since = now - timedelta(days=1)
        period_label = "ayer"

    return since, period_label, now.strftime("%Y-%m-%d"), now


# ---------------------------------------------------------------------------
# Llamadas a gh CLI
# ---------------------------------------------------------------------------
def run_gh(args: list[str], gh_bin: str) -> list[dict]:
    """Llama gh CLI y devuelve lista parseada de JSON. Devuelve [] en error."""
    cmd = [gh_bin, *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logging.warning(f"gh error ({' '.join(args[:3])}): {result.stderr.strip()}")
            return []
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)  # type: ignore[no-any-return]
    except subprocess.TimeoutExpired:
        logging.error(f"Timeout ejecutando: {' '.join(cmd)}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"JSON invalido de gh: {e}")
        return []


def collect_github_data(since: datetime, config: dict) -> dict:
    org = config["GITHUB_ORG"]
    username = config["GITHUB_USERNAME"]
    gh = config["GH_BIN"]
    since_str = since.strftime("%Y-%m-%d")

    logging.info(f"Recolectando datos de GitHub org={org} desde={since_str}")

    # 1. Commits propios
    commits_raw = run_gh(
        [
            "search",
            "commits",
            f"--author={username}",
            f"--owner={org}",
            f"--author-date=>={since_str}",
            "--json",
            "sha,repository,commit",
            "--limit",
            "50",
        ],
        gh,
    )

    commits = []
    for c in commits_raw:
        author_date = c.get("commit", {}).get("author", {}).get("date", "")
        if author_date:
            try:
                # Parsear la fecha y comparar
                dt = datetime.fromisoformat(author_date)
                if dt.tzinfo is None:
                    from zoneinfo import ZoneInfo

                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                if dt >= since:
                    msg_lines = c.get("commit", {}).get("message", "").split("\n")
                    commits.append(
                        {
                            "repo": c.get("repository", {}).get("name", ""),
                            "message": msg_lines[0].strip(),
                            "sha": c.get("sha", "")[:7],
                            "date": author_date,
                        }
                    )
            except ValueError:
                pass

    # 2. PRs propios creados/actualizados en el periodo
    prs_own_raw = run_gh(
        [
            "search",
            "prs",
            f"--author={username}",
            f"--owner={org}",
            f"--created=>={since_str}",
            "--json",
            "number,title,state,repository,createdAt,closedAt,url",
            "--limit",
            "30",
        ],
        gh,
    )

    # Tambien buscar PRs mergeados antes (closed en el periodo)
    prs_merged_raw = run_gh(
        [
            "search",
            "prs",
            f"--author={username}",
            f"--owner={org}",
            "--state=closed",
            f"--closed=>={since_str}",
            "--json",
            "number,title,state,repository,createdAt,closedAt,url",
            "--limit",
            "30",
        ],
        gh,
    )

    # Deduplicar por numero+repo
    seen_prs = set()
    prs_done = []
    for pr in prs_own_raw + prs_merged_raw:
        key = (pr.get("number"), pr.get("repository", {}).get("name"))
        if key not in seen_prs:
            seen_prs.add(key)
            prs_done.append(
                {
                    "number": pr.get("number"),
                    "title": pr.get("title", ""),
                    "state": pr.get("state", ""),
                    "repo": pr.get("repository", {}).get("name", ""),
                    "url": pr.get("url", ""),
                    "created_at": pr.get("createdAt", ""),
                    "closed_at": pr.get("closedAt", ""),
                }
            )

    # 3. Issues cerrados por el usuario en el periodo
    issues_closed_raw = run_gh(
        [
            "search",
            "issues",
            f"--owner={org}",
            f"--author={username}",
            "--state=closed",
            f"--closed=>={since_str}",
            "--json",
            "number,title,repository,closedAt,url",
            "--limit",
            "20",
        ],
        gh,
    )

    issues_closed = [
        {
            "number": i.get("number"),
            "title": i.get("title", ""),
            "repo": i.get("repository", {}).get("name", ""),
            "url": i.get("url", ""),
        }
        for i in issues_closed_raw
    ]

    # 4. PRs abiertos de la org para revisar (excluyendo los propios)
    prs_open_raw = run_gh(
        [
            "search",
            "prs",
            f"--owner={org}",
            "--state=open",
            "--json",
            "number,title,repository,author,createdAt,url",
            "--limit",
            "20",
        ],
        gh,
    )

    prs_to_review = [
        {
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "repo": pr.get("repository", {}).get("name", ""),
            "author": pr.get("author", {}).get("login", ""),
            "url": pr.get("url", ""),
        }
        for pr in prs_open_raw
        if pr.get("author", {}).get("login", "") != username
    ]

    # 5. Issues abiertos asignados al usuario
    issues_open_raw = run_gh(
        [
            "search",
            "issues",
            f"--owner={org}",
            f"--involves={username}",
            "--state=open",
            "--json",
            "number,title,repository,url,assignees",
            "--limit",
            "20",
        ],
        gh,
    )

    issues_open = []
    seen_issues = set()
    for i in issues_open_raw:
        num = i.get("number")
        repo = i.get("repository", {}).get("name", "")
        key = (num, repo)
        if key not in seen_issues:
            seen_issues.add(key)
            issues_open.append(
                {
                    "number": num,
                    "title": i.get("title", ""),
                    "repo": repo,
                    "url": i.get("url", ""),
                }
            )

    logging.info(
        f"Datos: {len(commits)} commits, {len(prs_done)} PRs propios, "
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
# Helpers compartidos
# ---------------------------------------------------------------------------
_MERGE_PREFIXES = ("Merge pull request", "Merge branch", "Merge remote-tracking")


def _is_merge_commit(message: str) -> bool:
    return any(message.startswith(p) for p in _MERGE_PREFIXES)


# ---------------------------------------------------------------------------
# Resumen LLM (opcional)
# ---------------------------------------------------------------------------
def _build_llm_prompt(data: dict, period_label: str) -> str:
    """Convierte los datos de GitHub en texto plano para el prompt del LLM."""
    lines = [f"Periodo: {period_label}", ""]

    commits = [c for c in data["commits"] if not _is_merge_commit(c["message"])]
    lines.append(f"Commits ({len(commits)}):")
    for c in commits:
        lines.append(f"- {c['repo']}: {c['message']}")
    lines.append("")

    prs = data["prs_done"]
    lines.append(f"PRs ({len(prs)}):")
    for pr in prs:
        lines.append(f"- [{pr['state']}] {pr['repo']}#{pr['number']}: {pr['title']}")
    lines.append("")

    issues_c = data["issues_closed"]
    lines.append(f"Issues cerrados ({len(issues_c)}):")
    for i in issues_c:
        lines.append(f"- {i['repo']}#{i['number']}: {i['title']}")
    lines.append("")

    issues_o = data["issues_open"]
    lines.append(f"Issues abiertos ({len(issues_o)}):")
    for i in issues_o:
        lines.append(f"- {i['repo']}#{i['number']}: {i['title']}")

    return "\n".join(lines)


def _call_llm(prompt: str, config: dict) -> str | None:
    """Llama a la API LLM (compatible OpenAI) y retorna el resumen o None en error."""
    url = f"{config['LLM_BASE_URL'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['LLM_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["LLM_MODEL"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sos un asistente que resume actividad de desarrollo en un daily standup. "
                    "Genera un resumen narrativo en español, primera persona, 2-4 oraciones. "
                    "No uses markdown ni bullet points. Se conciso y natural."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 300,
        "temperature": 0.7,
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.RequestException as e:
        logging.warning(f"LLM request error: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        logging.warning(f"LLM response parse error: {e}")
        return None


def generate_summary(data: dict, period_label: str, config: dict) -> str | None:
    """Genera un resumen narrativo via LLM. Retorna None si no hay API key o falla."""
    if not config.get("LLM_API_KEY"):
        logging.info("LLM_API_KEY no configurada, omitiendo resumen LLM")
        return None
    prompt = _build_llm_prompt(data, period_label)
    return _call_llm(prompt, config)


# ---------------------------------------------------------------------------
# Formateo — Obsidian Markdown
# ---------------------------------------------------------------------------
def format_markdown(
    data: dict, period_label: str, today_str: str, now: datetime, summary: str | None = None
) -> str:
    weekday_es = {
        0: "lunes",
        1: "martes",
        2: "miercoles",
        3: "jueves",
        4: "viernes",
        5: "sabado",
        6: "domingo",
    }
    day_name = weekday_es.get(now.weekday(), "")
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
    ]

    if summary:
        lines.extend([
            "## Resumen",
            "",
            summary,
            "",
        ])

    lines.extend([
        f"## Ayer hice ({period_label})",
        "",
    ])

    # Commits
    commits = data["commits"]
    lines.append(f"### Commits ({len(commits)})")
    if commits:
        for c in commits:
            lines.append(f"- `{c['repo']}` — {c['message']}")
    else:
        lines.append("_Sin commits en el periodo._")
    lines.append("")

    # PRs propios
    prs = data["prs_done"]
    lines.append(f"### PRs ({len(prs)})")
    if prs:
        for pr in prs:
            estado = pr["state"].upper()
            lines.append(
                f"- [{estado}] [#{pr['number']} {pr['title']}]({pr['url']}) — `{pr['repo']}`"
            )
    else:
        lines.append("_Sin PRs en el periodo._")
    lines.append("")

    # Issues cerrados
    issues_c = data["issues_closed"]
    lines.append(f"### Issues cerrados ({len(issues_c)})")
    if issues_c:
        for i in issues_c:
            lines.append(f"- [#{i['number']} {i['title']}]({i['url']}) — `{i['repo']}`")
    else:
        lines.append("_Sin issues cerrados en el periodo._")
    lines.append("")

    lines.append("## Para revisar hoy")
    lines.append("")

    # PRs abiertos de la org
    prs_rev = data["prs_to_review"]
    lines.append(f"### PRs abiertos de la org ({len(prs_rev)})")
    if prs_rev:
        for pr in prs_rev:
            lines.append(
                f"- [#{pr['number']} {pr['title']}]({pr['url']}) — `{pr['repo']}` (@{pr['author']})"
            )
    else:
        lines.append("_Sin PRs abiertos de otros en la org._")
    lines.append("")

    # Issues abiertos
    issues_o = data["issues_open"]
    lines.append(f"### Issues abiertos donde participo ({len(issues_o)})")
    if issues_o:
        for i in issues_o:
            lines.append(f"- [#{i['number']} {i['title']}]({i['url']}) — `{i['repo']}`")
    else:
        lines.append("_Sin issues abiertos asignados._")
    lines.append("")

    lines.append("---")
    lines.append(f"_Generado el {timestamp}_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formateo — Telegram (HTML)
# ---------------------------------------------------------------------------
def _h(text: str) -> str:
    """Escapa HTML para Telegram."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _link(text: str, url: str) -> str:
    return f'<a href="{url}">{_h(text)}</a>'


def _group_by_repo(items: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for item in items:
        result.setdefault(item.get("repo", "?"), []).append(item)
    return result


def format_telegram(
    data: dict, period_label: str, today_str: str, now: datetime, summary: str | None = None
) -> str:
    weekday_es = {
        0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
        4: "viernes", 5: "sabado", 6: "domingo",
    }
    day_name = weekday_es.get(now.weekday(), "")

    sections: list[str] = []

    # --- Encabezado ---
    sections.append(
        f"<b>Daily Standup \u2014 {_h(today_str)} ({_h(day_name)})</b>\n"
        f"<i>Periodo: {_h(period_label)}</i>"
    )

    if summary:
        sections.append(f"<i>{_h(summary)}</i>")

    # --- Ayer hice ---
    commits_real = [c for c in data["commits"] if not _is_merge_commit(c["message"])]
    prs_done = data["prs_done"]
    issues_c = data["issues_closed"]

    # Unir commits y PRs por repo para la seccion "ayer"
    repos_ayer: set[str] = set()
    for c in commits_real:
        repos_ayer.add(c["repo"])
    for pr in prs_done:
        repos_ayer.add(pr["repo"])
    for i in issues_c:
        repos_ayer.add(i["repo"])

    if repos_ayer:
        ayer_lines = ["<b>Ayer hice</b>"]
        commits_by_repo = _group_by_repo(commits_real)
        prs_by_repo = _group_by_repo(prs_done)
        issues_c_by_repo = _group_by_repo(issues_c)

        for repo in sorted(repos_ayer):
            repo_lines = [f"\n<b>{_h(repo)}</b>"]

            repo_commits = commits_by_repo.get(repo, [])
            if repo_commits:
                repo_lines.append("  <i>commits</i>")
                for c in repo_commits[:6]:
                    repo_lines.append(f"  \u2022 {_h(c['message'])}")

            repo_prs = prs_by_repo.get(repo, [])
            if repo_prs:
                repo_lines.append("  <i>PRs</i>")
                for pr in repo_prs[:5]:
                    estado = pr["state"].upper()
                    pr_label = f"#{pr['number']} {pr['title']}"
                    repo_lines.append(f"  \u2022 [{estado}] {_link(pr_label, pr['url'])}")

            repo_issues_c = issues_c_by_repo.get(repo, [])
            if repo_issues_c:
                repo_lines.append("  <i>issues cerrados</i>")
                for i in repo_issues_c[:3]:
                    i_label = f"#{i['number']} {i['title']}"
                    repo_lines.append(f"  \u2022 {_link(i_label, i['url'])}")

            ayer_lines.extend(repo_lines)

        sections.append("\n".join(ayer_lines))
    else:
        sections.append("<b>Ayer hice</b>\n<i>Sin actividad en el periodo.</i>")

    # --- Para revisar hoy ---
    prs_rev = data["prs_to_review"]
    issues_o = data["issues_open"]

    revisar_lines = ["<b>Para revisar hoy</b>"]

    if prs_rev:
        revisar_lines.append(f"  <i>PRs abiertos en la org ({len(prs_rev)})</i>")
        prs_rev_by_repo = _group_by_repo(prs_rev)
        for repo in sorted(prs_rev_by_repo):
            revisar_lines.append(f"  <b>{_h(repo)}</b>")
            for pr in prs_rev_by_repo[repo][:4]:
                pr_label = f"#{pr['number']} {pr['title']}"
                revisar_lines.append(
                    f"    \u2022 {_link(pr_label, pr['url'])} @{_h(pr['author'])}"
                )
    else:
        revisar_lines.append("  <i>Sin PRs de otros abiertos</i>")

    if issues_o:
        revisar_lines.append(f"\n  <i>Issues donde participo ({len(issues_o)})</i>")
        issues_o_by_repo = _group_by_repo(issues_o)
        for repo in sorted(issues_o_by_repo):
            revisar_lines.append(f"  <b>{_h(repo)}</b>")
            for i in issues_o_by_repo[repo][:4]:
                i_label = f"#{i['number']} {i['title']}"
                revisar_lines.append(f"    \u2022 {_link(i_label, i['url'])}")
    else:
        revisar_lines.append("  <i>Sin issues abiertos asignados</i>")

    sections.append("\n".join(revisar_lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Formateo — Slack (Block Kit)
# ---------------------------------------------------------------------------
def _sl(text: str, url: str) -> str:
    """Enlace en Slack mrkdwn: <url|texto>"""
    return f"<{url}|{text}>"


def format_slack(
    data: dict, period_label: str, today_str: str, now: datetime, summary: str | None = None
) -> list[dict]:
    """Devuelve una lista de bloques Block Kit para Slack."""
    weekday_es = {
        0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
        4: "viernes", 5: "sabado", 6: "domingo",
    }
    day_name = weekday_es.get(now.weekday(), "")
    blocks: list[dict] = []

    def section(text: str) -> dict:
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

    def divider() -> dict:
        return {"type": "divider"}

    # Encabezado
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"Daily Standup — {today_str} ({day_name})"},
    })
    blocks.append(section(f"_Periodo: {period_label}_"))
    if summary:
        blocks.append(section(f"_{summary}_"))
    blocks.append(divider())

    # --- Ayer hice ---
    commits_real = [c for c in data["commits"] if not _is_merge_commit(c["message"])]
    prs_done = data["prs_done"]
    issues_c = data["issues_closed"]

    repos_ayer: set[str] = set()
    for c in commits_real:
        repos_ayer.add(c["repo"])
    for pr in prs_done:
        repos_ayer.add(pr["repo"])
    for i in issues_c:
        repos_ayer.add(i["repo"])

    blocks.append(section("*Ayer hice*"))

    if repos_ayer:
        commits_by_repo = _group_by_repo(commits_real)
        prs_by_repo = _group_by_repo(prs_done)
        issues_c_by_repo = _group_by_repo(issues_c)

        for repo in sorted(repos_ayer):
            lines = [f"*{repo}*"]

            repo_commits = commits_by_repo.get(repo, [])
            if repo_commits:
                lines.append("  _commits_")
                for c in repo_commits[:6]:
                    lines.append(f"  \u2022 {c['message']}")

            repo_prs = prs_by_repo.get(repo, [])
            if repo_prs:
                lines.append("  _PRs_")
                for pr in repo_prs[:5]:
                    estado = pr["state"].upper()
                    pr_label = f"#{pr['number']} {pr['title']}"
                    lines.append(f"  \u2022 [{estado}] {_sl(pr_label, pr['url'])}")

            repo_issues_c = issues_c_by_repo.get(repo, [])
            if repo_issues_c:
                lines.append("  _issues cerrados_")
                for i in repo_issues_c[:3]:
                    i_label = f"#{i['number']} {i['title']}"
                    lines.append(f"  \u2022 {_sl(i_label, i['url'])}")

            blocks.append(section("\n".join(lines)))
    else:
        blocks.append(section("_Sin actividad en el periodo._"))

    blocks.append(divider())

    # --- Para revisar hoy ---
    blocks.append(section("*Para revisar hoy*"))

    prs_rev = data["prs_to_review"]
    if prs_rev:
        blocks.append(section(f"_PRs abiertos en la org ({len(prs_rev)})_"))
        prs_rev_by_repo = _group_by_repo(prs_rev)
        for repo in sorted(prs_rev_by_repo):
            lines = [f"*{repo}*"]
            for pr in prs_rev_by_repo[repo][:4]:
                pr_label = f"#{pr['number']} {pr['title']}"
                lines.append(f"  \u2022 {_sl(pr_label, pr['url'])} @{pr['author']}")
            blocks.append(section("\n".join(lines)))
    else:
        blocks.append(section("_Sin PRs de otros abiertos_"))

    issues_o = data["issues_open"]
    if issues_o:
        blocks.append(section(f"_Issues donde participo ({len(issues_o)})_"))
        issues_o_by_repo = _group_by_repo(issues_o)
        for repo in sorted(issues_o_by_repo):
            lines = [f"*{repo}*"]
            for i in issues_o_by_repo[repo][:4]:
                i_label = f"#{i['number']} {i['title']}"
                lines.append(f"  \u2022 {_sl(i_label, i['url'])}")
            blocks.append(section("\n".join(lines)))
    else:
        blocks.append(section("_Sin issues abiertos asignados_"))

    return blocks


def send_slack(webhook_url: str, blocks: list[dict]) -> bool:
    """Envia el reporte a Slack via Incoming Webhook con Block Kit."""
    # Slack limita a 50 bloques por mensaje; dividimos si hay mas
    max_blocks = 50
    chunks = [blocks[i: i + max_blocks] for i in range(0, len(blocks), max_blocks)]
    success = True
    for chunk in chunks:
        try:
            resp = requests.post(webhook_url, json={"blocks": chunk}, timeout=15)
            if not resp.ok:
                logging.error(f"Slack error {resp.status_code}: {resp.text[:200]}")
                success = False
        except requests.RequestException as e:
            logging.error(f"Slack request failed: {e}")
            success = False
    return success


# ---------------------------------------------------------------------------
# Destinos
# ---------------------------------------------------------------------------
def send_telegram(token: str, chat_id: str, text: str) -> bool:
    """Envia texto en HTML a Telegram, dividiendo por secciones si supera el limite."""
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    max_len = 4000

    # Dividir por secciones (doble salto) para no cortar entidades HTML
    raw_sections = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for section in raw_sections:
        candidate = f"{current}\n\n{section}".strip() if current else section
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = section
    if current:
        chunks.append(current)

    success = True
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(api_url, json=payload, timeout=15)
            if not resp.ok:
                logging.error(f"Telegram error {resp.status_code}: {resp.text[:200]}")
                success = False
        except requests.RequestException as e:
            logging.error(f"Telegram request failed: {e}")
            success = False
    return success


def write_obsidian(vault_path: str, today_str: str, content: str) -> bool:
    inbox = Path(vault_path) / "00-Inbox"
    if not inbox.exists():
        logging.warning(f"Carpeta Obsidian Inbox no existe: {inbox}")
        inbox.mkdir(parents=True, exist_ok=True)
    filepath = inbox / f"daily_report_{today_str}.md"
    try:
        filepath.write_text(content, encoding="utf-8")
        logging.info(f"Reporte escrito en: {filepath}")
        return True
    except OSError as e:
        logging.error(f"Error escribiendo en Obsidian: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    logging.info("=== Daily Standup iniciado ===")
    if DRY_RUN:
        logging.info("Modo DRY-RUN activado: no se enviara ni guardara nada.")

    try:
        config = load_config()
        since, period_label, today_str, now = get_date_range(config["TIMEZONE"])

        logging.info(f"Fecha: {today_str} | Periodo: {period_label}")

        data = collect_github_data(since, config)

        summary = generate_summary(data, period_label, config)

        md_content = format_markdown(data, period_label, today_str, now, summary=summary)
        slack_blocks = format_slack(data, period_label, today_str, now, summary=summary)

        if DRY_RUN:
            if summary:
                print("\n" + "=" * 60)
                print("RESUMEN LLM")
                print("=" * 60)
                print(summary)
            print("\n" + "=" * 60)
            print("MARKDOWN (Obsidian)")
            print("=" * 60)
            print(md_content)
            print("\n" + "=" * 60)
            print(f"SLACK BLOCKS ({len(slack_blocks)} bloques)")
            print("=" * 60)
            for b in slack_blocks:
                btype = b.get("type")
                if btype == "header":
                    print(f"[HEADER] {b['text']['text']}")
                elif btype == "section":
                    print(f"[SECTION] {b['text']['text'][:120]}")
                elif btype == "divider":
                    print("[---]")
            logging.info("=== Dry-run completado ===")
            return

        obsidian_ok = write_obsidian(config["OBSIDIAN_VAULT_PATH"], today_str, md_content)
        slack_ok = send_slack(config["SLACK_WEBHOOK_URL"], slack_blocks)

        if obsidian_ok:
            logging.info("Obsidian: OK")
        if slack_ok:
            logging.info("Slack: OK")

        if not obsidian_ok and not slack_ok:
            logging.critical("Ambos destinos fallaron.")
            sys.exit(1)

        logging.info("=== Daily Standup completado ===")

    except Exception as e:
        logging.critical(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
