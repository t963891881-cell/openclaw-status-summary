#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


COLLECTOR_PATH = Path(__file__).with_name("collect_openclaw_summary.py")
DEFAULT_TABLE_NAMES = {
    "agents": "Agents",
    "tasks": "Tasks",
    "risks": "Risks",
    "snapshots": "Snapshots",
}
BATCH_SIZE = 200


class FeishuBitableClient:
    def __init__(self, app_id: str, app_secret: str, app_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token
        self.base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}"
        self.tenant_access_token = self._get_tenant_access_token()

    def _request(self, method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.tenant_access_token}"}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Feishu API {method} {url} failed: HTTP {exc.code} {detail}") from exc

        if payload.get("code") != 0:
            raise RuntimeError(f"Feishu API {method} {url} failed: {payload}")
        return payload

    def _get_tenant_access_token(self) -> str:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        body = {"app_id": self.app_id, "app_secret": self.app_secret}
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != 0:
            raise RuntimeError(f"Failed to get tenant access token: {payload}")
        return payload["tenant_access_token"]

    def list_tables(self) -> list[dict[str, Any]]:
        url = f"{self.base_url}/tables?page_size=100"
        return self._request("GET", url)["data"]["items"]

    def get_table_id_by_name(self, table_name: str) -> str:
        for item in self.list_tables():
            if item["name"] == table_name:
                return item["table_id"]
        raise RuntimeError(f"Table not found: {table_name}")

    def list_fields(self, table_id: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/tables/{table_id}/fields?page_size=100"
        return self._request("GET", url)["data"]["items"]

    def list_all_records(self, table_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token = None
        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            url = f"{self.base_url}/tables/{table_id}/records?{urllib.parse.urlencode(params)}"
            payload = self._request("GET", url)["data"]
            items.extend(payload.get("items", []))
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
        return items

    def batch_create_records(self, table_id: str, records: list[dict[str, Any]]) -> None:
        for chunk in chunked(records, BATCH_SIZE):
            url = f"{self.base_url}/tables/{table_id}/records/batch_create"
            self._request("POST", url, {"records": [{"fields": item} for item in chunk]})

    def batch_update_records(self, table_id: str, records: list[dict[str, Any]]) -> None:
        for chunk in chunked(records, BATCH_SIZE):
            url = f"{self.base_url}/tables/{table_id}/records/batch_update"
            payload = {"records": [{"record_id": item["record_id"], "fields": item["fields"]} for item in chunk]}
            self._request("POST", url, payload)


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def parse_iso_to_millis(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def run_collector() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(COLLECTOR_PATH)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_snapshot_record(summary_json: dict[str, Any]) -> dict[str, Any]:
    agents = summary_json["agents"]
    tasks = summary_json["tasks"]["items"]
    risks = summary_json["risks"]
    outputs = summary_json["outputs"]
    warnings = summary_json["data_quality"]["warnings"]
    missing_sources = summary_json["data_quality"]["missing_sources"]

    return {
        "snapshot_label": summary_json["generated_at"],
        "overall_status": summary_json["overall_status"],
        "agent_total": len(agents),
        "active_agents": sum(1 for item in agents if item["status"] == "active"),
        "idle_agents": sum(1 for item in agents if item["status"] == "idle"),
        "stale_agents": sum(1 for item in agents if item["status"] == "stale"),
        "unknown_agents": sum(1 for item in agents if item["status"] == "unknown"),
        "task_total": len(tasks),
        "blocked_task_total": sum(1 for item in tasks if item.get("blocked")),
        "risk_total": len(risks),
        "critical_risk_total": sum(1 for item in risks if item["severity"] == "critical"),
        "output_total": len(outputs),
        "missing_sources": "\n".join(missing_sources),
        "warnings": "\n".join(warnings),
        "snapshot_time": summary_json["generated_at"],
    }


def build_agents_records(summary_json: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot_time = summary_json["generated_at"]
    records = []
    for item in summary_json["agents"]:
        records.append(
            {
                "agent_label": item["name"] or item["id"],
                "agent_id": item["id"],
                "name": item["name"],
                "status": item["status"],
                "model": item["model"] or "",
                "workspace": item["workspace"] or "",
                "agent_dir": item["agent_dir"] or "",
                "last_active_at": item["last_active_at"] or "",
                "heartbeat_minutes": item["heartbeat_minutes"] if item["heartbeat_minutes"] is not None else None,
                "session_count": item["session_count"],
                "confidence": item["confidence"],
                "snapshot_time": snapshot_time,
            }
        )
    return records


def build_tasks_records(summary_json: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot_time = summary_json["generated_at"]
    records = []
    for item in summary_json["tasks"]["items"]:
        records.append(
            {
                "title": item["title"],
                "task_id": item["id"],
                "status": item["status"],
                "assignee": item["assignee"] or "",
                "priority": item["priority"] or "",
                "created_at": item["created_at"] or "",
                "updated_at": item["updated_at"] or "",
                "description": item["description"] or "",
                "age_hours": item["age_hours"] if item["age_hours"] is not None else None,
                "blocked": bool(item["blocked"]),
                "block_reason": item["block_reason"] or "",
                "source": item["source"],
                "confidence": item["confidence"],
                "snapshot_time": snapshot_time,
            }
        )
    return records


def build_risks_records(summary_json: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot_time = summary_json["generated_at"]
    records = []
    for item in summary_json["risks"]:
        risk_key = "::".join(
            [
                item["type"],
                item.get("agent_id") or "",
                item.get("task_id") or "",
                item["detected_at"],
            ]
        )
        records.append(
            {
                "risk_summary": item["message"],
                "risk_key": risk_key,
                "severity": item["severity"],
                "type": item["type"],
                "agent_id": item.get("agent_id") or "",
                "task_id": item.get("task_id") or "",
                "message": item["message"],
                "detected_at": item["detected_at"],
                "confidence": item["confidence"],
                "snapshot_time": snapshot_time,
            }
        )
    return records


def existing_record_map(records: list[dict[str, Any]], key_field: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for record in records:
        fields = record.get("fields", {})
        key = fields.get(key_field)
        if key:
            mapping[str(key)] = record["record_id"]
    return mapping


def normalize_fields_for_table(field_specs: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    specs_by_name = {item["field_name"]: item for item in field_specs}
    normalized: dict[str, Any] = {}

    for field_name, value in record.items():
        spec = specs_by_name.get(field_name)
        if not spec:
            continue

        field_type = spec["type"]
        if field_type == 5:
            if isinstance(value, str) and value:
                millis = parse_iso_to_millis(value)
                if millis is not None:
                    normalized[field_name] = millis
            continue

        if value is None:
            continue
        normalized[field_name] = value

    return normalized


def sync_dimension(
    client: FeishuBitableClient,
    table_id: str,
    key_field: str,
    new_records: list[dict[str, Any]],
) -> tuple[int, int]:
    field_specs = client.list_fields(table_id)
    existing_records = client.list_all_records(table_id)
    record_map = existing_record_map(existing_records, key_field)

    create_batch: list[dict[str, Any]] = []
    update_batch: list[dict[str, Any]] = []

    for item in new_records:
        normalized = normalize_fields_for_table(field_specs, item)
        key = normalized.get(key_field)
        if key and str(key) in record_map:
            update_batch.append({"record_id": record_map[str(key)], "fields": normalized})
        else:
            create_batch.append(normalized)

    if create_batch:
        client.batch_create_records(table_id, create_batch)
    if update_batch:
        client.batch_update_records(table_id, update_batch)

    return len(create_batch), len(update_batch)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync OpenClaw summary output into Feishu Bitable.")
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-secret", required=True)
    parser.add_argument("--app-token", required=True)
    parser.add_argument("--agents-table", default=DEFAULT_TABLE_NAMES["agents"])
    parser.add_argument("--tasks-table", default=DEFAULT_TABLE_NAMES["tasks"])
    parser.add_argument("--risks-table", default=DEFAULT_TABLE_NAMES["risks"])
    parser.add_argument("--snapshots-table", default=DEFAULT_TABLE_NAMES["snapshots"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_collector()
    summary_json = payload["summary_json"]

    client = FeishuBitableClient(args.app_id, args.app_secret, args.app_token)

    table_ids = {
        "agents": client.get_table_id_by_name(args.agents_table),
        "tasks": client.get_table_id_by_name(args.tasks_table),
        "risks": client.get_table_id_by_name(args.risks_table),
        "snapshots": client.get_table_id_by_name(args.snapshots_table),
    }

    agents_create, agents_update = sync_dimension(
        client,
        table_ids["agents"],
        "agent_id",
        build_agents_records(summary_json),
    )
    tasks_create, tasks_update = sync_dimension(
        client,
        table_ids["tasks"],
        "task_id",
        build_tasks_records(summary_json),
    )
    risks_create, risks_update = sync_dimension(
        client,
        table_ids["risks"],
        "risk_key",
        build_risks_records(summary_json),
    )

    snapshot_fields = client.list_fields(table_ids["snapshots"])
    client.batch_create_records(
        table_ids["snapshots"],
        [normalize_fields_for_table(snapshot_fields, build_snapshot_record(summary_json))],
    )

    result = {
        "ok": True,
        "app_token": args.app_token,
        "table_ids": table_ids,
        "summary_generated_at": summary_json["generated_at"],
        "agents": {"created": agents_create, "updated": agents_update},
        "tasks": {"created": tasks_create, "updated": tasks_update},
        "risks": {"created": risks_create, "updated": risks_update},
        "snapshots": {"created": 1},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
