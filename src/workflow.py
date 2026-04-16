from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import uuid

import pandas as pd


DEFAULT_STATE = {"notices": []}


### Convert non-JSON-native values into strings before writing the workflow file.
###############################################################################
def _json_default(value: Any):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


### Normalize notice payload values so timestamps are stored in a serializable form.
###############################################################################
def _normalize_notice(notice: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(notice)
    for key, value in list(normalized.items()):
        if isinstance(value, pd.Timestamp):
            normalized[key] = value.isoformat()
    return normalized


### Read the persisted workflow state from disk or return an empty default state.
###############################################################################
def load_workflow_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return dict(DEFAULT_STATE)
    return json.loads(state_path.read_text())


### Save the workflow state JSON file to the managed processed-data directory.
###############################################################################
def save_workflow_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, default=_json_default))


### Reset the workflow state to an empty notice list.
###############################################################################
def reset_workflow_state(state_path: Path) -> None:
    save_workflow_state(state_path, dict(DEFAULT_STATE))


### Create a new notice record with workflow metadata and optional validation data.
###############################################################################
def create_notice_record(
    extracted_data: dict[str, Any],
    validation_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = pd.Timestamp.now()
    record = {
        "id": str(uuid.uuid4()),
        "status": "review",
        "uploaded_at": now.isoformat(),
        "validated_at": None,
        "approved_at": None,
        "executed_at": None,
        **_normalize_notice(extracted_data),
    }
    if validation_data:
        record["validation"] = _normalize_notice(validation_data)
        record["status"] = "validated"
        record["validated_at"] = now.isoformat()
    return record


### Insert a new notice into state or replace an existing one with the same ID.
###############################################################################
def upsert_notice(state: dict[str, Any], notice_record: dict[str, Any]) -> dict[str, Any]:
    notices = state.setdefault("notices", [])
    for index, existing in enumerate(notices):
        if existing.get("id") == notice_record.get("id"):
            notices[index] = notice_record
            break
    else:
        notices.append(notice_record)
    return state


### Attach validation results to a notice and move it into validated status.
###############################################################################
def set_notice_validation(notice_record: dict[str, Any], validation_data: dict[str, Any]) -> dict[str, Any]:
    notice_record = dict(notice_record)
    notice_record["validation"] = _normalize_notice(validation_data)
    notice_record["validated_at"] = pd.Timestamp.now().isoformat()
    notice_record["status"] = "validated"
    return notice_record


### Accept reviewed notice data and move the record from review to uploaded status.
###############################################################################
def accept_notice_record(notice_record: dict[str, Any], updates: dict[str, Any] | None = None) -> dict[str, Any]:
    notice_record = dict(notice_record)
    if updates:
        notice_record.update(_normalize_notice(updates))
    notice_record["status"] = "uploaded"
    return notice_record


### Mark a notice as approved/executed and stamp the corresponding timestamps.
###############################################################################
def approve_notice(notice_record: dict[str, Any]) -> dict[str, Any]:
    notice_record = dict(notice_record)
    now = pd.Timestamp.now().isoformat()
    notice_record["status"] = "executed"
    notice_record["approved_at"] = now
    notice_record["executed_at"] = now
    return notice_record


### Mark a validated notice as scheduled for a future upcoming-capital-call step.
###############################################################################
def schedule_notice(notice_record: dict[str, Any]) -> dict[str, Any]:
    notice_record = dict(notice_record)
    notice_record["status"] = "scheduled"
    return notice_record


### Convert notice records into a filtered/sorted DataFrame for UI rendering.
###############################################################################
def notices_to_dataframe(notices: list[dict[str, Any]], statuses: list[str] | None = None) -> pd.DataFrame:
    df = pd.DataFrame(notices)
    if df.empty:
        return df
    if statuses:
        df = df[df["status"].isin(statuses)]
    if "uploaded_at" in df.columns:
        df = df.sort_values(by="uploaded_at", ascending=False)
    return df.reset_index(drop=True)


### Find a single notice in state by its generated workflow ID.
###############################################################################
def get_notice_by_id(state: dict[str, Any], notice_id: str) -> dict[str, Any] | None:
    for notice in state.get("notices", []):
        if notice.get("id") == notice_id:
            return notice
    return None


### Remove a notice from workflow state by ID.
###############################################################################
def delete_notice_by_id(state: dict[str, Any], notice_id: str) -> dict[str, Any]:
    state = dict(state)
    state["notices"] = [
        notice for notice in state.get("notices", []) if notice.get("id") != notice_id
    ]
    return state
