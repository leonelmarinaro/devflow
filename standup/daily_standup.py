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
import re
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
    config = {
        "GITHUB_ORG": os.environ.get("GITHUB_ORG", "FARO-DataLab"),
        "GITHUB_USERNAME": os.environ.get("GITHUB_USERNAME", "leonelmarinaro"),
        "GH_BIN": os.environ.get("GH_BIN", "/opt/homebrew/bin/gh"),
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "OBSIDIAN_VAULT_PATH": os.environ.get(
            "OBSIDIAN_VAULT_PATH",
            "/Users/lmarinaro/Documents/Obsidian/Growketing",
        ),
        "TIMEZONE": os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires"),
    }
    if not DRY_RUN:
        missing = [
            k
            for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
            if not config[k]
        ]
        if missing:
            raise ValueError(f"Variables de entorno faltantes: {missing}")
    return config


# ---------------------------------------------------------------------------
# Calculo del rango de fechas
# ---------------------------------------------------------------------------
def get_date_range(tz_name: str) -> tuple[datetime, str, str]:
    """
    Devuelve (since_dt, period_label, today_str).
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
    cmd = [gh_bin] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logging.warning(f"gh error ({' '.join(args[:3])}): {result.stderr.strip()}")
            return []
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)
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
    commits_raw = run_gh([
        "search", "commits",
        f"--author={username}",
        f"--owner={org}",
        f"--author-date=>={since_str}",
        "--json", "sha,repository,commit",
        "--limit", "50",
    ], gh)

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
                    commits.append({
                        "repo": c.get("repository", {}).get("name", ""),
                        "message": msg_lines[0].strip(),
                        "sha": c.get("sha", "")[:7],
                        "date": author_date,
                    })
            except ValueError:
                pass

    # 2. PRs propios creados/actualizados en el periodo
    prs_own_raw = run_gh([
        "search", "prs",
        f"--author={username}",
        f"--owner={org}",
        f"--created=>={since_str}",
        "--json", "number,title,state,repository,createdAt,closedAt,url",
        "--limit", "30",
    ], gh)

    # Tambien buscar PRs mergeados antes (closed en el periodo)
    prs_merged_raw = run_gh([
        "search", "prs",
        f"--author={username}",
        f"--owner={org}",
        "--state=closed",
        f"--closed=>={since_str}",
        "--json", "number,title,state,repository,createdAt,closedAt,url",
        "--limit", "30",
    ], gh)

    # Deduplicar por numero+repo
    seen_prs = set()
    prs_done = []
    for pr in prs_own_raw + prs_merged_raw:
        key = (pr.get("number"), pr.get("repository", {}).get("name"))
        if key not in seen_prs:
            seen_prs.add(key)
            prs_done.append({
                "number": pr.get("number"),
                "title": pr.get("title", ""),
                "state": pr.get("state", ""),
                "repo": pr.get("repository", {}).get("name", ""),
                "url": pr.get("url", ""),
                "created_at": pr.get("createdAt", ""),
                "closed_at": pr.get("closedAt", ""),
            })

    # 3. Issues cerrados por el usuario en el periodo
    issues_closed_raw = run_gh([
        "search", "issues",
        f"--owner={org}",
        f"--author={username}",
        "--state=closed",
        f"--closed=>={since_str}",
        "--json", "number,title,repository,closedAt,url",
        "--limit", "20",
    ], gh)

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
    prs_open_raw = run_gh([
        "search", "prs",
        f"--owner={org}",
        "--state=open",
        "--json", "number,title,repository,author,createdAt,url",
        "--limit", "20",
    ], gh)

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
    issues_open_raw = run_gh([
        "search", "issues",
        f"--owner={org}",
        f"--involves={username}",
        "--state=open",
        "--json", "number,title,repository,url,assignees",
        "--limit", "20",
    ], gh)

    issues_open = []
    seen_issues = set()
    for i in issues_open_raw:
        num = i.get("number")
        repo = i.get("repository", {}).get("name", "")
        key = (num, repo)
        if key not in seen_issues:
            seen_issues.add(key)
            issues_open.append({
                "number": num,
                "title": i.get("title", ""),
                "repo": repo,
                "url": i.get("url", ""),
            })

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
# Formateo — Obsidian Markdown
# ---------------------------------------------------------------------------
def format_markdown(data: dict, period_label: str, today_str: str, now: datetime) -> str:
    weekday_es = {
        0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
        4: "viernes", 5: "sabado", 6: "domingo",
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
        f"## Ayer hice ({period_label})",
        "",
    ]

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
            lines.append(f"- [{estado}] [#{pr['number']} {pr['title']}]({pr['url']}) — `{pr['repo']}`")
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
            lines.append(f"- [#{pr['number']} {pr['title']}]({pr['url']}) — `{pr['repo']}` (@{pr['author']})")
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
# Formateo — Telegram (MarkdownV2)
# ---------------------------------------------------------------------------
_TG_SPECIAL = re.compile(r"([_\*\[\]\(\)~`>#\+\-=\|{}.!])")


def esc(text: str) -> str:
    """Escapa caracteres especiales para Telegram MarkdownV2."""
    return _TG_SPECIAL.sub(r"\\\1", str(text))


def format_telegram(data: dict, period_label: str, today_str: str, now: datetime) -> str:
    weekday_es = {
        0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
        4: "viernes", 5: "sabado", 6: "domingo",
    }
    day_name = weekday_es.get(now.weekday(), "")

    lines = [
        f"*Daily Standup \u2014 {esc(today_str)} \\({esc(day_name)}\\)*",
        "",
        f"*Ayer hice* \\({esc(period_label)}\\)",
        "",
    ]

    # Commits
    commits = data["commits"]
    lines.append(f"*Commits \\({len(commits)}\\)*")
    if commits:
        for c in commits[:10]:  # Limitar para no saturar el chat
            lines.append(f"\u2022 `{esc(c['repo'])}` \u2014 {esc(c['message'])}")
    else:
        lines.append("_Sin commits_")
    lines.append("")

    # PRs propios
    prs = data["prs_done"]
    lines.append(f"*PRs \\({len(prs)}\\)*")
    if prs:
        for pr in prs[:8]:
            estado = esc(pr["state"].upper())
            lines.append(
                f"\u2022 \\[{estado}\\] [\\#{esc(str(pr['number']))} {esc(pr['title'])}]({pr['url']})"
            )
    else:
        lines.append("_Sin PRs_")
    lines.append("")

    # Issues cerrados
    issues_c = data["issues_closed"]
    lines.append(f"*Issues cerrados \\({len(issues_c)}\\)*")
    if issues_c:
        for i in issues_c[:5]:
            lines.append(
                f"\u2022 [\\#{esc(str(i['number']))} {esc(i['title'])}]({i['url']})"
            )
    else:
        lines.append("_Sin issues cerrados_")
    lines.append("")

    lines.append("*Para revisar hoy*")
    lines.append("")

    # PRs abiertos de la org
    prs_rev = data["prs_to_review"]
    lines.append(f"*PRs abiertos org \\({len(prs_rev)}\\)*")
    if prs_rev:
        for pr in prs_rev[:8]:
            lines.append(
                f"\u2022 [\\#{esc(str(pr['number']))} {esc(pr['title'])}]({pr['url']}) \u2014 @{esc(pr['author'])}"
            )
    else:
        lines.append("_Sin PRs de otros abiertos_")
    lines.append("")

    # Issues abiertos
    issues_o = data["issues_open"]
    lines.append(f"*Issues donde participo \\({len(issues_o)}\\)*")
    if issues_o:
        for i in issues_o[:8]:
            lines.append(
                f"\u2022 [\\#{esc(str(i['number']))} {esc(i['title'])}]({i['url']})"
            )
    else:
        lines.append("_Sin issues abiertos_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Destinos
# ---------------------------------------------------------------------------
def send_telegram(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram tiene limite de 4096 caracteres por mensaje
    chunks = [text[i: i + 4000] for i in range(0, len(text), 4000)]
    success = True
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
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

        md_content = format_markdown(data, period_label, today_str, now)
        tg_content = format_telegram(data, period_label, today_str, now)

        if DRY_RUN:
            print("\n" + "=" * 60)
            print("MARKDOWN (Obsidian)")
            print("=" * 60)
            print(md_content)
            print("\n" + "=" * 60)
            print("TELEGRAM")
            print("=" * 60)
            print(tg_content)
            logging.info("=== Dry-run completado ===")
            return

        obsidian_ok = write_obsidian(config["OBSIDIAN_VAULT_PATH"], today_str, md_content)
        telegram_ok = send_telegram(
            config["TELEGRAM_BOT_TOKEN"], config["TELEGRAM_CHAT_ID"], tg_content
        )

        if obsidian_ok:
            logging.info("Obsidian: OK")
        if telegram_ok:
            logging.info("Telegram: OK")

        if not obsidian_ok and not telegram_ok:
            logging.critical("Ambos destinos fallaron.")
            sys.exit(1)

        logging.info("=== Daily Standup completado ===")

    except Exception as e:
        logging.critical(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
