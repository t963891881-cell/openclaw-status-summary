#!/usr/bin/env python3

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


UTC = timezone.utc
ACTIVE_WINDOW_MINUTES = 10
STALE_WINDOW_HOURS = 2
MAX_OUTPUTS_PER_AGENT = 3
OUTPUT_EXTENSIONS = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".py",
    ".sh",
}
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".next",
    ".cache",
    "dist",
    "build",
    "tmp",
    "temp",
    "sessions",
    "agent",
}
SKIP_FILE_NAMES = {
    "sessions.json",
    "models.json",
    "SKILL.md",
    "BOOTSTRAP.md",
    "USER.md",
    "SOUL.md",
    "TOOLS.md",
    "IDENTITY.md",
    "AGENTS.md",
    "HEARTBEAT.md",
    "_meta.json",
    "SSE-EVENTS.md",
    "AGENT_HANDOFF_TEMPLATES.md",
    "REQUIREMENTS_REVIEW_CHECKLIST.md",
    "PRD_TEMPLATE_ZH.md",
}
SKIP_PATH_PARTS = {
    "/skills/",
    "/references/",
    "/agent/",
    "/sessions/",
    "/.git/",
    "/.clawhub/",
    "/.openclaw/",
}
PREFERRED_OUTPUT_EXTENSIONS = {
    ".md",
    ".txt",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".pdf",
}


@dataclass
class Risk:
    severity: str
    type: str
    agent_id: str | None
    task_id: str | None
    message: str
    detected_at: str
    confidence: str


@dataclass
class TaskRecord:
    id: str
    title: str
    status: str
    assignee: str | None
    priority: str | None
    created_at: str | None
    updated_at: str | None
    description: str | None
    age_hours: float | None
    blocked: bool
    block_reason: str | None
    source: str
    confidence: str


def now_utc() -> datetime:
    return datetime.now(UTC)


def isoformat(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(UTC).isoformat()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(UTC)
    except ValueError:
        return None


def classify_status(last_active: datetime | None) -> str:
    if not last_active:
        return "unknown"

    delta = now_utc() - last_active
    if delta <= timedelta(minutes=ACTIVE_WINDOW_MINUTES):
        return "active"
    if delta <= timedelta(hours=STALE_WINDOW_HOURS):
        return "idle"
    return "stale"


def infer_confidence(status: str, direct: bool = True) -> str:
    if direct and status in {"active", "idle"}:
        return "high"
    if status in {"stale", "unknown"}:
        return "medium"
    return "low"


def safe_read_text(path: Path, limit: int = 400) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None
    if not text:
        return None
    return text[:limit]


def safe_read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []


def first_meaningful_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:180]
    return None


def extract_token_usage(text: str | None) -> dict[str, Any]:
    usage = {"input_used": None, "input_limit": None, "percent": None, "raw": None}
    if not text:
        return usage

    match = re.search(r"(\d+)k/(\d+)k\s*\((\d+)%\)", text, flags=re.IGNORECASE)
    if match:
        used_k, limit_k, percent = match.groups()
        usage["input_used"] = int(used_k) * 1000
        usage["input_limit"] = int(limit_k) * 1000
        usage["percent"] = int(percent)
        usage["raw"] = match.group(0)
        return usage

    return usage


def iter_recent_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []

    candidates: list[Path] = []
    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name not in SKIP_DIR_NAMES and not name.startswith(".")]
        for file_name in file_names:
            path = Path(current_root) / file_name
            if file_name in SKIP_FILE_NAMES:
                continue
            path_text = str(path)
            if any(part in path_text for part in SKIP_PATH_PARTS):
                continue
            if path.suffix.lower() not in OUTPUT_EXTENSIONS and path.suffix.lower() not in PREFERRED_OUTPUT_EXTENSIONS:
                continue
            candidates.append(path)

    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[:MAX_OUTPUTS_PER_AGENT]


def find_agent_session_dir(openclaw_root: Path, agent_id: str) -> Path | None:
    direct = openclaw_root / "agents" / agent_id / "sessions"
    if direct.exists():
        return direct

    for candidate in (openclaw_root / "agents").glob("*/sessions"):
        if candidate.parent.name == agent_id:
            return candidate
    return None


def collect_sessions(agent_id: str, session_dir: Path | None, warnings: list[str], risks: list[Risk]) -> tuple[list[dict[str, Any]], datetime | None]:
    if not session_dir or not session_dir.exists():
        return [], None

    session_files = sorted(
        [
            path
            for path in session_dir.rglob("*")
            if path.is_file() and path.name != "sessions.json" and ".deleted." not in path.name
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not session_files:
        return [], None

    latest_active: datetime | None = None
    session_items: list[dict[str, Any]] = []

    for path in session_files[:5]:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        latest_active = max(latest_active, mtime) if latest_active else mtime
        text = safe_read_text(path, limit=600)
        token_usage = extract_token_usage(text)
        session_items.append(
            {
                "agent_id": agent_id,
                "session_id": path.stem,
                "channel": "unknown",
                "last_active_at": isoformat(mtime),
                "status": "active" if path == session_files[0] else classify_status(mtime),
                "model": None,
                "token_usage": token_usage,
                "confidence": "medium",
            }
        )

    unreadable_count = 0
    for path in session_files[:5]:
        if safe_read_text(path, limit=50) is None:
            unreadable_count += 1
    if unreadable_count:
        warnings.append(f"{agent_id}: {unreadable_count} recent session files could not be parsed")
        risks.append(
            Risk(
                severity="warning",
                type="session_parse_error",
                agent_id=agent_id,
                task_id=None,
                message=f"{unreadable_count} recent session files could not be parsed for {agent_id}",
                detected_at=isoformat(now_utc()),
                confidence="medium",
            )
        )

    return session_items, latest_active


def parse_task_message(text: str, timestamp: str | None, default_agent_id: str) -> TaskRecord | None:
    task_id_match = re.search(r"\*{0,2}Task ID:\*{0,2}\s*([a-zA-Z0-9-]+)", text)
    if not task_id_match:
        return None

    task_id = task_id_match.group(1)
    title = task_id
    assigned_title_match = re.search(r"ASSIGNED:\s*(.+)", text)
    markdown_title_match = re.search(r"\*{0,2}Task:\*{0,2}\s*(.+)", text)
    if assigned_title_match:
        title = assigned_title_match.group(1).strip()
    elif markdown_title_match:
        title = markdown_title_match.group(1).strip()

    description_match = re.search(r"## Description\s*(.+?)(?:## |\Z)", text, flags=re.DOTALL)
    description = description_match.group(1).strip() if description_match else None

    status = "assigned"
    blocked = False
    block_reason = None
    if "PERSISTENT Stuck Task Alert" in text or "Task Stuck Alert" in text:
        status_match = re.search(r"\*{0,2}Status:\*{0,2}\s*([A-Z_]+)", text)
        duration_match = re.search(r"for\s*([0-9.]+)\s*hours", text, flags=re.IGNORECASE)
        status = status_match.group(1).lower() if status_match else "assigned"
        blocked = True
        if duration_match:
            block_reason = f"stuck for {duration_match.group(1)} hours"
        else:
            block_reason = "stuck task alert"

    assignee_match = re.search(r"\*{0,2}Assignee:\*{0,2}\s*(.+)", text)
    assignee = None
    if assignee_match:
        assignee_line = assignee_match.group(1).strip()
        paren_match = re.search(r"\(([^)]+)\)", assignee_line)
        assignee = paren_match.group(1).strip() if paren_match else assignee_line
    elif "ASSIGNED:" in text:
        assignee = default_agent_id

    priority_match = re.search(r"\*{0,2}Priority:\*{0,2}\s*([A-Z_]+)", text)
    priority = priority_match.group(1).lower() if priority_match else None

    age_hours = None
    if blocked and block_reason:
        hours_match = re.search(r"([0-9.]+)\s*hours", block_reason)
        if hours_match:
            age_hours = float(hours_match.group(1))

    return TaskRecord(
        id=task_id,
        title=title,
        status=status,
        assignee=assignee,
        priority=priority,
        created_at=timestamp,
        updated_at=timestamp,
        description=description,
        age_hours=age_hours,
        blocked=blocked,
        block_reason=block_reason,
        source="session_messages",
        confidence="medium",
    )


def collect_tasks_from_sessions(openclaw_root: Path, agent_ids: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    task_records: dict[str, TaskRecord] = {}

    for agent_id in agent_ids:
        session_dir = find_agent_session_dir(openclaw_root, agent_id)
        if not session_dir or not session_dir.exists():
            continue

        session_files = [
            path
            for path in session_dir.rglob("*.jsonl")
            if path.is_file() and ".deleted." not in path.name
        ]
        for path in session_files:
            for line in safe_read_lines(path):
                if "Task ID:" not in line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"{agent_id}: failed to parse session line in {path.name}")
                    continue

                message = record.get("message", {})
                contents = message.get("content", [])
                text_chunks = []
                for item in contents:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_chunks.append(item.get("text", ""))
                if not text_chunks:
                    continue

                text = "\n".join(text_chunks)
                parsed = parse_task_message(text, record.get("timestamp"), agent_id)
                if not parsed:
                    continue

                existing = task_records.get(parsed.id)
                if not existing:
                    task_records[parsed.id] = parsed
                    continue

                existing_updated = parse_timestamp(existing.updated_at)
                parsed_updated = parse_timestamp(parsed.updated_at)
                if parsed_updated and (not existing_updated or parsed_updated >= existing_updated):
                    merged = TaskRecord(
                        id=parsed.id,
                        title=parsed.title or existing.title,
                        status=parsed.status or existing.status,
                        assignee=parsed.assignee or existing.assignee,
                        priority=parsed.priority or existing.priority,
                        created_at=existing.created_at or parsed.created_at,
                        updated_at=parsed.updated_at or existing.updated_at,
                        description=existing.description or parsed.description,
                        age_hours=parsed.age_hours if parsed.age_hours is not None else existing.age_hours,
                        blocked=existing.blocked or parsed.blocked,
                        block_reason=parsed.block_reason or existing.block_reason,
                        source="session_messages",
                        confidence="medium",
                    )
                    task_records[parsed.id] = merged

    items = [record.__dict__ for record in task_records.values()]
    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return items


def heartbeat_candidate_files(openclaw_root: Path, agent_ids: list[str]) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = [("main", openclaw_root / "workspace" / "HEARTBEAT.md")]
    for agent_id in agent_ids:
        candidates.append((agent_id, openclaw_root / "agents" / agent_id / "HEARTBEAT.md"))
    return candidates


def markdown_task_candidate_files(openclaw_root: Path, agent_ids: list[str]) -> list[tuple[str, Path]]:
    file_names = ("TODO.md", "TASKS.md", "tasks.md", "todo.md")
    candidates: list[tuple[str, Path]] = []

    for file_name in file_names:
        candidates.append(("main", openclaw_root / "workspace" / file_name))

    for agent_id in agent_ids:
        agent_root = openclaw_root / "agents" / agent_id
        for file_name in file_names:
            candidates.append((agent_id, agent_root / file_name))

    return candidates


def parse_heartbeat_line(line: str) -> tuple[str | None, dict[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None, {}

    prefixes = ("- [ ]", "* [ ]", "- ", "* ")
    content = None
    for prefix in prefixes:
        if stripped.startswith(prefix):
            content = stripped[len(prefix):].strip()
            break
    if content is None:
        return None, {}

    metadata: dict[str, str] = {}
    for key in ("id", "priority", "status", "schedule"):
        match = re.search(rf"\b{key}:([^\s\]]+)", content, flags=re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()

    content = re.sub(r"\b(id|priority|status|schedule):([^\s\]]+)", "", content, flags=re.IGNORECASE).strip()
    content = re.sub(r"\s{2,}", " ", content)
    return content or None, metadata


def collect_tasks_from_heartbeat(openclaw_root: Path, agent_ids: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for agent_id, path in heartbeat_candidate_files(openclaw_root, agent_ids):
        if not path.exists():
            continue

        lines = safe_read_lines(path)
        if not lines:
            continue

        for index, line in enumerate(lines, start=1):
            title, metadata = parse_heartbeat_line(line)
            if not title:
                continue

            updated_at = isoformat(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
            task_id = metadata.get("id") or f"heartbeat:{agent_id}:{path.name}:{index}"
            status = metadata.get("status", "scheduled").lower()
            priority = metadata.get("priority", "normal").lower()
            schedule = metadata.get("schedule")
            description = f"Heartbeat task from {path.name}"
            if schedule:
                description += f" (schedule: {schedule})"

            items.append(
                {
                    "id": task_id,
                    "title": title,
                    "status": status,
                    "assignee": agent_id,
                    "priority": priority,
                    "created_at": updated_at,
                    "updated_at": updated_at,
                    "description": description,
                    "age_hours": None,
                    "blocked": False,
                    "block_reason": None,
                    "source": "heartbeat_markdown",
                    "confidence": "medium",
                }
            )

    return items


def collect_tasks_from_markdown_files(openclaw_root: Path, agent_ids: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for agent_id, path in markdown_task_candidate_files(openclaw_root, agent_ids):
        if not path.exists():
            continue

        lines = safe_read_lines(path)
        if not lines:
            continue

        current_status = None
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            heading_match = re.match(r"^#+\s+(.+)$", stripped)
            if heading_match:
                heading = heading_match.group(1).strip().lower()
                if heading in {"inbox", "todo", "assigned", "in progress", "review", "done", "blocked"}:
                    current_status = heading.replace(" ", "_")
                continue

            title, metadata = parse_heartbeat_line(line)
            if not title:
                continue

            updated_at = isoformat(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
            task_id = metadata.get("id") or f"markdown:{agent_id}:{path.name}:{index}"
            status = metadata.get("status", current_status or "todo").lower()
            priority = metadata.get("priority", "normal").lower()
            schedule = metadata.get("schedule")
            description = f"Markdown task from {path.name}"
            if schedule:
                description += f" (schedule: {schedule})"

            items.append(
                {
                    "id": task_id,
                    "title": title,
                    "status": status,
                    "assignee": agent_id,
                    "priority": priority,
                    "created_at": updated_at,
                    "updated_at": updated_at,
                    "description": description,
                    "age_hours": None,
                    "blocked": status == "blocked",
                    "block_reason": "marked blocked in markdown" if status == "blocked" else None,
                    "source": "markdown_tasks",
                    "confidence": "medium",
                }
            )

    return items


def collect_outputs(agent_id: str, workspace: Path | None, memory_root: Path | None) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []

    if workspace and workspace.exists():
        for path in iter_recent_files(workspace):
            text = safe_read_text(path, limit=400)
            outputs.append(
                {
                    "agent_id": agent_id,
                    "type": "file",
                    "title": path.name,
                    "path": str(path),
                    "updated_at": isoformat(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)),
                    "summary": first_meaningful_line(text),
                    "confidence": "medium",
                }
            )

    if memory_root and memory_root.exists():
        memory_files = sorted(
            [path for path in memory_root.rglob("*.md") if path.is_file()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if memory_files:
            path = memory_files[0]
            text = safe_read_text(path, limit=400)
            outputs.append(
                {
                    "agent_id": agent_id,
                    "type": "memory_entry",
                    "title": path.name,
                    "path": str(path),
                    "updated_at": isoformat(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)),
                    "summary": first_meaningful_line(text),
                    "confidence": "medium",
                }
            )

    return outputs[:MAX_OUTPUTS_PER_AGENT]


def resolve_workspace(agent: dict[str, Any], defaults: dict[str, Any]) -> Path | None:
    workspace = agent.get("workspace") or defaults.get("workspace")
    return Path(workspace).expanduser() if workspace else None


def resolve_model(agent: dict[str, Any], defaults: dict[str, Any]) -> str | None:
    agent_model = agent.get("model", {})
    if isinstance(agent_model, dict):
        primary = agent_model.get("primary")
        if primary:
            return primary
    default_model = defaults.get("model", {})
    if isinstance(default_model, dict):
        return default_model.get("primary")
    return None


def build_summary_text(payload: dict[str, Any]) -> str:
    agents = payload["agents"]
    risks = payload["risks"]
    outputs = payload["outputs"]
    tasks = payload["tasks"]
    active_count = sum(1 for item in agents if item["status"] == "active")
    stale_count = sum(1 for item in agents if item["status"] == "stale")
    lines = [
        f"OpenClaw summary at {payload['generated_at']}",
        f"Agents: {len(agents)} total, {active_count} active, {stale_count} stale",
        f"Tasks: {tasks['totals'].get('all', 0)} total" if tasks["available"] else "Tasks: unavailable",
        f"Recent outputs: {len(outputs)}",
        f"Risks: {len(risks)}",
    ]

    if risks:
        top_risk = risks[0]
        lines.append(f"Top risk: {top_risk['type']} - {top_risk['message']}")

    for agent in agents[:5]:
        heartbeat = agent["heartbeat_minutes"]
        heartbeat_text = f"{heartbeat}m ago" if heartbeat is not None else "unknown"
        lines.append(f"- {agent['id']}: {agent['status']} ({heartbeat_text})")

    return "\n".join(lines)


def merge_task_items(*task_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for task_list in task_lists:
        for item in task_list:
            existing = merged.get(item["id"])
            if not existing:
                merged[item["id"]] = item.copy()
                continue

            existing_updated = parse_timestamp(existing.get("updated_at"))
            item_updated = parse_timestamp(item.get("updated_at"))

            if item_updated and (not existing_updated or item_updated >= existing_updated):
                combined = existing.copy()
                combined.update(item)
            else:
                combined = item.copy()
                combined.update(existing)

            if existing.get("source") and item.get("source") and existing["source"] != item["source"]:
                combined["source"] = f"{existing['source']}+{item['source']}"

            combined["blocked"] = bool(existing.get("blocked") or item.get("blocked"))
            combined["block_reason"] = item.get("block_reason") or existing.get("block_reason")
            combined["description"] = existing.get("description") or item.get("description")
            merged[item["id"]] = combined

    items = list(merged.values())
    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return items


def main() -> None:
    home = Path.home()
    openclaw_root = home / ".openclaw"
    config_path = openclaw_root / "openclaw.json"

    generated_at = isoformat(now_utc())
    data_quality = {"missing_sources": [], "warnings": []}
    risks: list[Risk] = []

    if not config_path.exists():
        data_quality["missing_sources"].append(str(config_path))
        payload = {
            "generated_at": generated_at,
            "host": "local",
            "scope": "all_agents",
            "overall_status": "critical",
            "agents": [],
            "sessions": [],
            "tasks": {"available": False, "source": None, "totals": {}, "items": []},
            "outputs": [],
            "risks": [
                {
                    "severity": "critical",
                    "type": "missing_source",
                    "agent_id": None,
                    "task_id": None,
                    "message": f"Missing OpenClaw config at {config_path}",
                    "detected_at": generated_at,
                    "confidence": "high",
                }
            ],
            "suggested_actions": [
                {
                    "priority": "high",
                    "action": "restore_openclaw_config",
                    "message": "Restore or initialize ~/.openclaw/openclaw.json before running the summary skill.",
                    "owner": "user",
                }
            ],
            "data_quality": data_quality,
        }
        print(json.dumps({"summary_text": build_summary_text(payload), "summary_json": payload}, ensure_ascii=False, indent=2))
        return

    config = load_json(config_path)
    agent_config = config.get("agents", {})
    defaults = agent_config.get("defaults", {})
    agent_list = agent_config.get("list", [])

    agents_output: list[dict[str, Any]] = []
    sessions_output: list[dict[str, Any]] = []
    outputs_output: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []

    global_memory = openclaw_root / "memory"

    for agent in agent_list:
        agent_id = agent.get("id")
        if not agent_id:
            data_quality["warnings"].append("Encountered agent entry without id")
            continue

        workspace = resolve_workspace(agent, defaults)
        agent_dir_value = agent.get("agentDir")
        agent_dir = Path(agent_dir_value).expanduser() if agent_dir_value else None
        session_dir = find_agent_session_dir(openclaw_root, agent_id)

        session_items, latest_active = collect_sessions(agent_id, session_dir, data_quality["warnings"], risks)
        sessions_output.extend(session_items)

        if workspace and not workspace.exists():
            risks.append(
                Risk(
                    severity="warning",
                    type="missing_workspace",
                    agent_id=agent_id,
                    task_id=None,
                    message=f"Workspace does not exist for {agent_id}: {workspace}",
                    detected_at=generated_at,
                    confidence="high",
                )
            )
            data_quality["warnings"].append(f"{agent_id}: missing workspace {workspace}")

        if agent_dir and not agent_dir.exists():
            risks.append(
                Risk(
                    severity="warning",
                    type="missing_agent_dir",
                    agent_id=agent_id,
                    task_id=None,
                    message=f"Agent dir does not exist for {agent_id}: {agent_dir}",
                    detected_at=generated_at,
                    confidence="high",
                )
            )
            data_quality["warnings"].append(f"{agent_id}: missing agent dir {agent_dir}")

        status = classify_status(latest_active)
        if status == "stale":
            risks.append(
                Risk(
                    severity="warning",
                    type="stale_agent",
                    agent_id=agent_id,
                    task_id=None,
                    message=f"No recent activity detected for {agent_id} in the last {STALE_WINDOW_HOURS} hours",
                    detected_at=generated_at,
                    confidence="medium",
                )
            )
            suggestions.append(
                {
                    "priority": "medium",
                    "action": f"follow_up_{agent_id}",
                    "message": f"Check whether {agent_id} is intentionally idle or needs attention.",
                    "owner": "user",
                }
            )

        heartbeat_minutes = None
        if latest_active:
            heartbeat_minutes = int((now_utc() - latest_active).total_seconds() // 60)

        outputs_output.extend(
            collect_outputs(
                agent_id=agent_id,
                workspace=workspace,
                memory_root=global_memory if global_memory.exists() else None,
            )
        )

        agents_output.append(
            {
                "id": agent_id,
                "name": agent.get("name") or agent.get("identity", {}).get("name") or agent_id,
                "status": status,
                "model": resolve_model(agent, defaults),
                "workspace": str(workspace) if workspace else None,
                "agent_dir": str(agent_dir) if agent_dir else None,
                "last_active_at": isoformat(latest_active),
                "heartbeat_minutes": heartbeat_minutes,
                "session_count": len(session_items),
                "confidence": infer_confidence(status, direct=bool(latest_active)),
            }
        )

    if not global_memory.exists():
        data_quality["missing_sources"].append(str(global_memory))

    agent_ids = [agent["id"] for agent in agents_output]
    session_task_items = collect_tasks_from_sessions(openclaw_root, agent_ids, data_quality["warnings"])
    heartbeat_task_items = collect_tasks_from_heartbeat(openclaw_root, agent_ids, data_quality["warnings"])
    markdown_task_items = collect_tasks_from_markdown_files(openclaw_root, agent_ids, data_quality["warnings"])
    task_items = merge_task_items(session_task_items, heartbeat_task_items, markdown_task_items)
    task_totals: dict[str, int] = {}
    if task_items:
        task_totals["all"] = len(task_items)
        for item in task_items:
            task_totals[item["status"]] = task_totals.get(item["status"], 0) + 1
            if item["blocked"]:
                risks.append(
                    Risk(
                        severity="critical" if item["age_hours"] and item["age_hours"] >= 6 else "warning",
                        type="stuck_task",
                        agent_id=item["assignee"],
                        task_id=item["id"],
                        message=f"Task {item['title']} is blocked ({item['block_reason'] or 'stuck'})",
                        detected_at=generated_at,
                        confidence="medium",
                    )
                )
                suggestions.append(
                    {
                        "priority": "high" if item["age_hours"] and item["age_hours"] >= 6 else "medium",
                        "action": f"resolve_task_{item['id']}",
                        "message": f"Review task '{item['title']}' and decide whether to clarify, reassign, or close it.",
                        "owner": "user",
                    }
                )

    severity_rank = {"critical": 2, "warning": 1}
    overall_status = "healthy"
    if risks:
        top_severity = max(severity_rank.get(risk.severity, 0) for risk in risks)
        overall_status = "critical" if top_severity >= 2 else "warning"

    risks_output = [risk.__dict__ for risk in risks]
    risks_output.sort(key=lambda item: (item["severity"] != "critical", item["type"], item["agent_id"] or ""))

    if not outputs_output:
        data_quality["warnings"].append(
            "No recent output artifacts matched the current filters; workspace activity may be limited to templates, skills, or config files."
        )

    payload = {
        "generated_at": generated_at,
        "host": "local",
        "scope": "all_agents",
        "overall_status": overall_status,
        "agents": agents_output,
        "sessions": sessions_output,
        "tasks": {
            "available": bool(task_items),
            "source": "session_messages" if task_items else None,
            "totals": task_totals,
            "items": task_items,
        },
        "outputs": outputs_output,
        "risks": risks_output,
        "suggested_actions": suggestions,
        "data_quality": data_quality,
    }

    print(json.dumps({"summary_text": build_summary_text(payload), "summary_json": payload}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
