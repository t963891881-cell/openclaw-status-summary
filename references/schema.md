# Output Schema

The collector returns one JSON document with two main payloads:

```json
{
  "summary_text": "string",
  "summary_json": {}
}
```

## `summary_json`

```json
{
  "generated_at": "ISO-8601 timestamp",
  "host": "local",
  "scope": "all_agents",
  "overall_status": "healthy | warning | critical | unknown",
  "agents": [],
  "sessions": [],
  "tasks": {
    "available": false,
    "source": null,
    "totals": {},
    "items": []
  },
  "outputs": [],
  "risks": [],
  "suggested_actions": [],
  "data_quality": {
    "missing_sources": [],
    "warnings": []
  }
}
```

## Current Task Adapter

The first task adapter reads task-like records from agent session messages.

It currently recognizes:
- assignment notifications containing `ASSIGNED:` and `Task ID`
- stuck-task alerts containing `Task Stuck Alert` or `PERSISTENT Stuck Task Alert`
- markdown checklist items from `HEARTBEAT.md`, for example:
  - `- [ ] Check inbox priority:high schedule:daily`
  - `- [ ] Review copy id:copy-review status:scheduled`
- markdown checklist items from `TODO.md` or `TASKS.md`
- optional markdown section headings that imply status:
  - `# Inbox`
  - `# Assigned`
  - `# In Progress`
  - `# Review`
  - `# Done`
  - `# Blocked`

When both are present for the same task ID, the collector merges them into one task record and updates:
- `updated_at`
- `blocked`
- `block_reason`
- `age_hours`
- `priority`

## `agents[]`

```json
{
  "id": "string",
  "name": "string",
  "status": "active | idle | stale | offline | unknown",
  "model": "string | null",
  "workspace": "absolute path | null",
  "agent_dir": "absolute path | null",
  "last_active_at": "ISO-8601 timestamp | null",
  "heartbeat_minutes": "number | null",
  "session_count": "number",
  "confidence": "high | medium | low"
}
```

## `sessions[]`

```json
{
  "agent_id": "string",
  "session_id": "string",
  "channel": "string",
  "last_active_at": "ISO-8601 timestamp | null",
  "status": "active | stale | unknown",
  "model": "string | null",
  "token_usage": {
    "input_used": "number | null",
    "input_limit": "number | null",
    "percent": "number | null",
    "raw": "string | null"
  },
  "confidence": "high | medium | low"
}
```

## `outputs[]`

```json
{
  "agent_id": "string",
  "type": "file | memory_entry | unknown",
  "title": "string",
  "path": "absolute path | null",
  "updated_at": "ISO-8601 timestamp | null",
  "summary": "string | null",
  "confidence": "high | medium | low"
}
```

## `risks[]`

```json
{
  "severity": "warning | critical",
  "type": "stale_agent | missing_workspace | missing_agent_dir | session_parse_error | missing_source",
  "agent_id": "string | null",
  "task_id": "string | null",
  "message": "string",
  "detected_at": "ISO-8601 timestamp",
  "confidence": "high | medium | low"
}
```

## `suggested_actions[]`

```json
{
  "priority": "high | medium | low",
  "action": "string",
  "message": "string",
  "owner": "user | agent | system"
}
```

## `data_quality`

```json
{
  "missing_sources": ["string"],
  "warnings": ["string"]
}
```

## Current Limits

- Tasks are intentionally stubbed until a reusable task source contract exists.
- Token usage depends on the session format and may be absent.
- Output summaries are lightweight and based on file names or memory excerpts.
