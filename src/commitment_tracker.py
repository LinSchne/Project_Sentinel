from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pandas as pd


NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

COMMITMENT_TRACKER_SHEET = "Commitment Tracker"
UPCOMING_CAPITAL_CALLS_SHEET = "Upcoming Capital Calls"
EXECUTED_CAPITAL_CALLS_SHEET = "Executed Capital Calls"


@dataclass
class CommitmentDashboardData:
    title: str
    as_of: str
    tracker_df: pd.DataFrame
    upcoming_df: pd.DataFrame
    executed_df: pd.DataFrame


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def parse_number(value: object) -> float:
    if value in ("", None):
        return 0.0
    return float(value)


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    cleaned = normalize_text(value)
    if not cleaned:
        return pd.NaT
    return pd.to_datetime(cleaned, format="%d.%m.%Y", errors="coerce")


def format_currency(value: object, currency: str = "EUR") -> str:
    amount = parse_number(value)
    formatted_amount = f"{amount:,.2f}".replace(",", "'")
    return f"{currency} {formatted_amount}"


def _load_shared_strings(workbook_zip: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    shared_strings = []

    for si in root.findall("main:si", NS):
        text = "".join(node.text or "" for node in si.iterfind(".//main:t", NS))
        shared_strings.append(text)

    return shared_strings


def _sheet_targets(workbook_zip: ZipFile) -> dict[str, str]:
    workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}

    targets: dict[str, str] = {}
    for sheet in workbook_root.find("main:sheets", NS):
        rel_id = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        targets[sheet.attrib["name"]] = f"xl/{rel_map[rel_id]}"

    return targets


def read_sheet_rows(source_workbook: Path, sheet_name: str) -> list[dict[str, str]]:
    with ZipFile(source_workbook) as workbook_zip:
        shared_strings = _load_shared_strings(workbook_zip)
        targets = _sheet_targets(workbook_zip)
        sheet_root = ET.fromstring(workbook_zip.read(targets[sheet_name]))

    rows: list[dict[str, str]] = []
    for row in sheet_root.findall(".//main:sheetData/main:row", NS):
        row_values: dict[str, str] = {}
        for cell in row.findall("main:c", NS):
            ref = cell.attrib.get("r", "")
            column = "".join(ch for ch in ref if ch.isalpha())
            cell_type = cell.attrib.get("t")
            value_node = cell.find("main:v", NS)
            inline_node = cell.find("main:is", NS)

            value = ""
            if cell_type == "s" and value_node is not None:
                value = shared_strings[int(value_node.text)]
            elif cell_type == "inlineStr" and inline_node is not None:
                value = "".join(node.text or "" for node in inline_node.iterfind(".//main:t", NS))
            elif value_node is not None and value_node.text is not None:
                value = value_node.text

            row_values[column] = value

        rows.append(row_values)

    return rows


def _header_index(rows: list[dict[str, str]], expected_headers: list[str]) -> int:
    expected = {normalize_text(header) for header in expected_headers}
    for index, row in enumerate(rows):
        values = {normalize_text(value) for value in row.values() if normalize_text(value)}
        if expected.issubset(values):
            return index
    raise ValueError(f"Could not find header row for sheet with headers: {expected_headers}")


def load_commitment_tracker_sheet(source_workbook: Path) -> tuple[str, str, pd.DataFrame]:
    rows = read_sheet_rows(source_workbook, COMMITMENT_TRACKER_SHEET)
    header_idx = _header_index(
        rows,
        [
            "Investor",
            "Fund Name",
            "Total Commitment",
            "Total Funded YTD",
            "Remaining Open Commitment",
        ],
    )

    title = normalize_text(rows[0].get("B", "Commitment Tracker"))
    as_of = normalize_text(rows[1].get("B", ""))
    data_rows = rows[header_idx + 1 :]

    parsed_rows = []
    for row in data_rows:
        investor = normalize_text(row.get("B", ""))
        fund_name = normalize_text(row.get("C", ""))
        if not investor and not fund_name:
            continue
        parsed_rows.append(
            {
                "Investor": investor,
                "Fund Name": fund_name,
                "Total Commitment": parse_number(row.get("D", "")),
                "Total Funded YTD": parse_number(row.get("E", "")),
                "Remaining Open Commitment": parse_number(row.get("F", "")),
            }
        )

    return title, as_of, pd.DataFrame(parsed_rows)


def load_upcoming_capital_calls_sheet(source_workbook: Path) -> pd.DataFrame:
    rows = read_sheet_rows(source_workbook, UPCOMING_CAPITAL_CALLS_SHEET)
    header_idx = _header_index(rows, ["Investor", "Fund Name", "Amount", "Due date"])

    parsed_rows = []
    for row in rows[header_idx + 1 :]:
        investor = normalize_text(row.get("B", ""))
        fund_name = normalize_text(row.get("C", ""))
        if not investor and not fund_name:
            continue
        parsed_rows.append(
            {
                "Investor": investor,
                "Fund Name": fund_name,
                "Amount": parse_number(row.get("D", "")),
                "Due Date": parse_date(row.get("E", "")),
            }
        )

    return pd.DataFrame(parsed_rows)


def load_executed_capital_calls_sheet(source_workbook: Path) -> pd.DataFrame:
    rows = read_sheet_rows(source_workbook, EXECUTED_CAPITAL_CALLS_SHEET)
    header_idx = _header_index(
        rows,
        ["Investor", "Fund Name", "Capital Call Amount Paid", "Value Date"],
    )

    parsed_rows = []
    for row in rows[header_idx + 1 :]:
        investor = normalize_text(row.get("B", ""))
        fund_name = normalize_text(row.get("C", ""))
        if not investor and not fund_name:
            continue
        parsed_rows.append(
            {
                "Investor": investor,
                "Fund Name": fund_name,
                "Capital Call Amount Paid": parse_number(row.get("D", "")),
                "Value Date": parse_date(row.get("E", "")),
            }
        )

    return pd.DataFrame(parsed_rows)


def load_commitment_dashboard(source_workbook: Path) -> CommitmentDashboardData:
    title, as_of, tracker_df = load_commitment_tracker_sheet(source_workbook)
    upcoming_df = load_upcoming_capital_calls_sheet(source_workbook)
    executed_df = load_executed_capital_calls_sheet(source_workbook)

    return CommitmentDashboardData(
        title=title,
        as_of=as_of,
        tracker_df=tracker_df,
        upcoming_df=upcoming_df,
        executed_df=executed_df,
    )


def ensure_commitment_dashboard_workbook(
    source_workbook: Path,
    managed_workbook: Path,
) -> Path:
    managed_workbook.parent.mkdir(parents=True, exist_ok=True)
    if not managed_workbook.exists():
        shutil.copy2(source_workbook, managed_workbook)
    return managed_workbook


def reset_commitment_dashboard_to_source(
    source_workbook: Path,
    managed_workbook: Path,
) -> Path:
    managed_workbook.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_workbook, managed_workbook)
    return managed_workbook


def prepare_commitment_tracker_display(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    for column in [
        "Total Commitment",
        "Total Funded YTD",
        "Remaining Open Commitment",
    ]:
        if column in display_df.columns:
            display_df[column] = display_df[column].apply(format_currency)
    return display_df


def prepare_upcoming_capital_calls_display(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    if "Amount" in display_df.columns:
        display_df["Amount"] = display_df["Amount"].apply(format_currency)
    if "Due Date" in display_df.columns:
        display_df["Due Date"] = display_df["Due Date"].apply(
            lambda value: value.strftime("%d.%m.%Y") if pd.notna(value) else ""
        )
    return display_df


def prepare_executed_capital_calls_display(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    if "Capital Call Amount Paid" in display_df.columns:
        display_df["Capital Call Amount Paid"] = display_df["Capital Call Amount Paid"].apply(
            format_currency
        )
    if "Value Date" in display_df.columns:
        display_df["Value Date"] = display_df["Value Date"].apply(
            lambda value: value.strftime("%d.%m.%Y") if pd.notna(value) else ""
        )
    return display_df


def dashboard_metrics(data: CommitmentDashboardData) -> dict[str, str]:
    tracker_df = data.tracker_df
    upcoming_df = data.upcoming_df
    executed_df = data.executed_df

    total_commitment = tracker_df["Total Commitment"].sum() if not tracker_df.empty else 0
    total_funded = tracker_df["Total Funded YTD"].sum() if not tracker_df.empty else 0
    remaining_open = (
        tracker_df["Remaining Open Commitment"].sum() if not tracker_df.empty else 0
    )
    next_due = (
        upcoming_df["Due Date"].dropna().min() if not upcoming_df.empty else pd.NaT
    )

    return {
        "Funds": str(len(tracker_df)),
        "Total Commitment": format_currency(total_commitment),
        "Funded YTD": format_currency(total_funded),
        "Remaining Open": format_currency(remaining_open),
        "Upcoming Calls": str(len(upcoming_df)),
        "Executed Calls": str(len(executed_df)),
        "Next Due Date": next_due.strftime("%d.%m.%Y") if pd.notna(next_due) else "-",
    }


def apply_workflow_updates(
    data: CommitmentDashboardData,
    notices: list[dict[str, object]],
) -> CommitmentDashboardData:
    tracker_df = data.tracker_df.copy()
    upcoming_df = data.upcoming_df.copy()
    executed_df = data.executed_df.copy()

    for notice in notices:
        fund_name = normalize_text(notice.get("fund_name", ""))
        amount = parse_number(notice.get("amount", 0))
        due_date = pd.to_datetime(notice.get("due_date"), errors="coerce")
        status = str(notice.get("status", "")).strip().lower()
        investor = normalize_text(notice.get("investor", ""))

        if not fund_name:
            continue

        tracker_matches = tracker_df["Fund Name"].astype(str).apply(normalize_text).eq(fund_name)
        if tracker_matches.any() and status == "executed":
            tracker_df.loc[tracker_matches, "Total Funded YTD"] = (
                tracker_df.loc[tracker_matches, "Total Funded YTD"].astype(float) + amount
            )
            tracker_df.loc[tracker_matches, "Remaining Open Commitment"] = (
                tracker_df.loc[tracker_matches, "Remaining Open Commitment"].astype(float) - amount
            )

        if status in {"uploaded", "validated"}:
            upcoming_row = {
                "Investor": investor,
                "Fund Name": notice.get("fund_name", ""),
                "Amount": amount,
                "Due Date": due_date,
            }
            existing_mask = (
                upcoming_df["Fund Name"].astype(str).apply(normalize_text).eq(fund_name)
                & upcoming_df["Amount"].astype(float).eq(amount)
            ) if not upcoming_df.empty else pd.Series(dtype=bool)
            if upcoming_df.empty or not existing_mask.any():
                upcoming_df = pd.concat([upcoming_df, pd.DataFrame([upcoming_row])], ignore_index=True)

        if status == "executed":
            executed_row = {
                "Investor": investor,
                "Fund Name": notice.get("fund_name", ""),
                "Capital Call Amount Paid": amount,
                "Value Date": pd.to_datetime(notice.get("executed_at"), errors="coerce"),
            }
            existing_mask = (
                executed_df["Fund Name"].astype(str).apply(normalize_text).eq(fund_name)
                & executed_df["Capital Call Amount Paid"].astype(float).eq(amount)
            ) if not executed_df.empty else pd.Series(dtype=bool)
            if executed_df.empty or not existing_mask.any():
                executed_df = pd.concat([executed_df, pd.DataFrame([executed_row])], ignore_index=True)

    if not executed_df.empty and "Value Date" in executed_df.columns:
        executed_df = executed_df.sort_values(by="Value Date", ascending=False, na_position="last")
    if not upcoming_df.empty and "Due Date" in upcoming_df.columns:
        upcoming_df = upcoming_df.sort_values(by="Due Date", ascending=True, na_position="last")

    return CommitmentDashboardData(
        title=data.title,
        as_of=data.as_of,
        tracker_df=tracker_df.reset_index(drop=True),
        upcoming_df=upcoming_df.reset_index(drop=True),
        executed_df=executed_df.reset_index(drop=True),
    )
