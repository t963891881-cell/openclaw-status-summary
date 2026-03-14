---
name: openclaw-status-summary
description: Generate a reusable OpenClaw multi-agent runtime summary without relying on ClawController. Use this when the user wants a direct status report from OpenClaw config, sessions, memory, or workspaces, or wants structured output that can later be sent to systems like Feishu.
---

# OpenClaw Status Summary

Use this skill when the user wants a direct summary of OpenClaw agents and runtime activity without depending on ClawController.

## What This Skill Produces

- `summary_text`: short human-readable status summary
- `summary_json`: structured output for downstream systems

The first-pass collector covers:
- agent inventory from `~/.openclaw/openclaw.json`
- recent session activity from `~/.openclaw/agents/*/sessions/`
- task recovery from task-bearing session messages and `HEARTBEAT.md`
- task recovery from common local markdown task files such as `TODO.md` and `TASKS.md`
- recent outputs from agent workspaces and memory files
- risk detection for stale agents, missing paths, and parse issues
- data quality warnings when expected sources are missing

## Workflow

1. Run `scripts/collect_openclaw_summary.py`.
2. Read the JSON output.
3. Use `summary_text` for chat/reporting.
4. Use `summary_json` for automations, Feishu sync, or custom formatting.

## Defaults

- Reads from the current user's `~/.openclaw` directory.
- Works even when some optional sources are missing.
- Does not assume a unified task backend exists.

## When Data Is Missing

- Do not invent task totals or outputs.
- Preserve empty arrays and add entries to `data_quality`.
- Treat inferred status as lower confidence than directly observed values.

## Output Contract

Read [references/schema.md](references/schema.md) when you need field-level details.

## Notes

- This first version is intentionally conservative.
- It is better to emit partial structured truth than a polished but guessed report.
- For lightweight local tasks, `HEARTBEAT.md` supports markdown checklist entries such as:
  - `- [ ] Check inbox priority:high schedule:daily`
  - `- [ ] Review landing page copy id:copy-review status:scheduled`
- `TODO.md` or `TASKS.md` can use the same checklist syntax.
- Optional markdown headings map to task status:
  - `# Inbox`
  - `# Assigned`
  - `# In Progress`
  - `# Review`
  - `# Done`
  - `# Blocked`
