from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


SOURCE_SHEET_NAME = "Approved wire instructions"
MANAGED_SHEET_NAME = "Approved Wires Master"

BASE_COLUMNS = [
    "Fund Name",
    "Beneficiary Bank",
    "Swift/BIC",
    "IBAN / Account Number",
    "Currency",
]

EXTRA_COLUMNS = {
    "Status": "Active",
    "Updated At": "",
}
VALID_STATUSES = {"Active", "Inactive"}
STATUS_LABELS = {
    "🟢 Active": "Active",
    "🔴 Inactive": "Inactive",
}


def now_ts() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().upper().split())


def normalize_iban(value: Any) -> str:
    if pd.isna(value):
        return ""
    return "".join(str(value).strip().upper().split())


def normalize_status(value: Any) -> str:
    normalized = str(value).strip() if not pd.isna(value) else ""
    if normalized in STATUS_LABELS:
        return STATUS_LABELS[normalized]
    return normalized if normalized in VALID_STATUSES else "Active"


def normalized_match(value_a: Any, value_b: Any, column_name: str) -> bool:
    if column_name == "IBAN / Account Number":
        return normalize_iban(value_a) == normalize_iban(value_b)
    return normalize_text(value_a) == normalize_text(value_b)


def iban_exists(df: pd.DataFrame, iban: Any) -> bool:
    normalized_iban = normalize_iban(iban)
    if not normalized_iban or "IBAN / Account Number" not in df.columns:
        return False

    existing_ibans = df["IBAN / Account Number"].apply(normalize_iban)
    return existing_ibans.eq(normalized_iban).any()


def find_duplicate_record(
    df: pd.DataFrame,
    record: dict[str, Any],
) -> dict[str, Any] | None:
    df = ensure_schema(df)
    iban_value = record.get("IBAN / Account Number", "")

    if not iban_exists(df, iban_value):
        return None

    normalized_iban_value = normalize_iban(iban_value)
    matched_rows = df[
        df["IBAN / Account Number"].apply(normalize_iban).eq(normalized_iban_value)
    ]

    if matched_rows.empty:
        return None

    matched_row = matched_rows.iloc[0].to_dict()
    matched_columns = [
        column
        for column in BASE_COLUMNS
        if normalized_match(record.get(column, ""), matched_row.get(column, ""), column)
    ]

    return {
        "matched_columns": matched_columns,
        "matched_row": matched_row,
    }


def make_duplicate_key(fund_name: Any, iban: Any, currency: Any) -> str:
    return "|".join(
        [
            normalize_text(fund_name),
            normalize_iban(iban),
            normalize_text(currency),
        ]
    )


def ensure_schema(
    df: pd.DataFrame,
    extra_columns: dict[str, Any] | None = None,
) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]

    merged_extra = dict(EXTRA_COLUMNS)
    if extra_columns:
        merged_extra.update(extra_columns)

    for col in BASE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    for col, default_value in merged_extra.items():
        if col not in df.columns:
            df[col] = default_value

    ordered_columns = BASE_COLUMNS + list(merged_extra.keys())
    remaining_columns = [col for col in df.columns if col not in ordered_columns]
    df = df[ordered_columns + remaining_columns]

    df = df.dropna(how="all")
    df = df.fillna("")

    if "Status" in df.columns:
        df["Status"] = df["Status"].apply(normalize_status)

    return df


def find_header_row(raw_df: pd.DataFrame) -> int:
    required_headers = set(BASE_COLUMNS)

    for idx in range(len(raw_df)):
        row_values = {
            str(value).strip()
            for value in raw_df.iloc[idx].tolist()
            if pd.notna(value) and str(value).strip()
        }

        if required_headers.issubset(row_values):
            return idx

    raise ValueError(
        f"Could not detect the header row in sheet '{SOURCE_SHEET_NAME}'. "
        f"Expected headers: {BASE_COLUMNS}"
    )


def read_source_approved_wires(source_workbook: Path) -> pd.DataFrame:
    raw_df = pd.read_excel(
        source_workbook,
        sheet_name=SOURCE_SHEET_NAME,
        header=None,
        engine="openpyxl",
    )

    header_row_idx = find_header_row(raw_df)

    headers = [
        str(value).strip() if pd.notna(value) else ""
        for value in raw_df.iloc[header_row_idx].tolist()
    ]

    data_df = raw_df.iloc[header_row_idx + 1 :].copy()
    data_df.columns = headers

    data_df = data_df.loc[:, [col for col in data_df.columns if str(col).strip() != ""]]
    data_df = data_df.dropna(how="all")
    data_df = data_df.fillna("")

    available_columns = [col for col in BASE_COLUMNS if col in data_df.columns]
    data_df = data_df[available_columns]

    for col in BASE_COLUMNS:
        if col not in data_df.columns:
            data_df[col] = ""

    data_df = data_df[BASE_COLUMNS]

    return data_df.reset_index(drop=True)


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_duplicate_key"] = df.apply(
        lambda row: make_duplicate_key(
            row["Fund Name"],
            row["IBAN / Account Number"],
            row["Currency"],
        ),
        axis=1,
    )
    df = df.drop_duplicates(subset="_duplicate_key", keep="first")
    df = df.drop(columns="_duplicate_key")
    return df


def load_approved_wires(
    source_workbook: Path,
    managed_workbook: Path,
    extra_columns: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if managed_workbook.exists():
        df = pd.read_excel(
            managed_workbook,
            sheet_name=MANAGED_SHEET_NAME,
            engine="openpyxl",
        )
    else:
        df = read_source_approved_wires(source_workbook)
        df = ensure_schema(df, extra_columns=extra_columns)

        df["Status"] = "Active"
        df["Updated At"] = now_ts()

        df = remove_duplicates(df)
        save_approved_wires(df, managed_workbook, extra_columns=extra_columns)

    df = ensure_schema(df, extra_columns=extra_columns)
    df = remove_duplicates(df)

    if "Fund Name" in df.columns:
        df = df.sort_values(by=["Fund Name", "Currency"], ascending=True).reset_index(drop=True)

    return df


def save_approved_wires(
    df: pd.DataFrame,
    managed_workbook: Path,
    extra_columns: dict[str, Any] | None = None,
) -> None:
    managed_workbook.parent.mkdir(parents=True, exist_ok=True)

    df_to_save = ensure_schema(df, extra_columns=extra_columns)

    with pd.ExcelWriter(managed_workbook, engine="openpyxl") as writer:
        df_to_save.to_excel(writer, sheet_name=MANAGED_SHEET_NAME, index=False)


def reset_approved_wires_to_source(
    source_workbook: Path,
    managed_workbook: Path,
    extra_columns: dict[str, Any] | None = None,
) -> pd.DataFrame:
    df = read_source_approved_wires(source_workbook)
    df = ensure_schema(df, extra_columns=extra_columns)

    df["Status"] = "Active"
    df["Updated At"] = now_ts()

    df = remove_duplicates(df)
    save_approved_wires(df, managed_workbook, extra_columns=extra_columns)

    if "Fund Name" in df.columns:
        df = df.sort_values(by=["Fund Name", "Currency"], ascending=True).reset_index(drop=True)

    return df


def apply_approved_wires_filters(
    df: pd.DataFrame,
    search_text: str = "",
    fund_names: list[str] | None = None,
    banks: list[str] | None = None,
    currencies: list[str] | None = None,
    statuses: list[str] | None = None,
) -> pd.DataFrame:
    filtered = df.copy()

    if search_text:
        search_value = search_text.strip().lower()

        search_columns = [
            "Fund Name",
            "Beneficiary Bank",
            "Swift/BIC",
            "IBAN / Account Number",
            "Currency",
        ]

        mask = filtered[search_columns].astype(str).apply(
            lambda col: col.str.lower().str.contains(search_value, na=False)
        ).any(axis=1)

        filtered = filtered[mask]

    if fund_names:
        filtered = filtered[filtered["Fund Name"].isin(fund_names)]

    if banks:
        filtered = filtered[filtered["Beneficiary Bank"].isin(banks)]

    if currencies:
        filtered = filtered[filtered["Currency"].isin(currencies)]

    if statuses:
        filtered = filtered[filtered["Status"].isin(statuses)]

    return filtered


def add_approved_wire_record(
    df: pd.DataFrame,
    record: dict[str, Any],
    extra_columns: dict[str, Any] | None = None,
) -> pd.DataFrame:
    df = ensure_schema(df, extra_columns=extra_columns)

    if iban_exists(df, record.get("IBAN / Account Number", "")):
        raise ValueError("Duplicate detected. Warning: IBAN already exists.")

    merged_extra = dict(EXTRA_COLUMNS)
    if extra_columns:
        merged_extra.update(extra_columns)

    new_row = {col: "" for col in df.columns}

    for col in BASE_COLUMNS:
        new_row[col] = str(record.get(col, "")).strip()

    for col, default_value in merged_extra.items():
        new_row[col] = record.get(col, default_value)

    new_row["Status"] = new_row.get("Status") or "Active"
    new_row["Status"] = normalize_status(new_row["Status"])
    new_row["Updated At"] = now_ts()

    result = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    result = ensure_schema(result, extra_columns=extra_columns)

    return result


def update_editable_fields(
    master_df: pd.DataFrame,
    edited_df: pd.DataFrame,
) -> pd.DataFrame:
    updated = master_df.copy()

    editable_columns = [
        col
        for col in master_df.columns
        if col not in BASE_COLUMNS + ["Updated At"]
    ]

    for idx in edited_df.index:
        for col in editable_columns:
            if col in edited_df.columns:
                updated.at[idx, col] = edited_df.at[idx, col]

        if "Status" in updated.columns:
            updated.at[idx, "Status"] = normalize_status(updated.at[idx, "Status"])
        updated.at[idx, "Updated At"] = now_ts()

    return updated


def editable_columns_for_ui(df: pd.DataFrame) -> list[str]:
    return [
        col
        for col in df.columns
        if col not in BASE_COLUMNS + ["Updated At"]
    ]
