from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json


NOISE_TEXT = " zzz_noise_token corrupted_context irrelevant_payload " * 20


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy values into values accepted by json.dumps."""
    if not isinstance(value, (list, dict)) and pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _log_change(
    changes: list[dict[str, Any]], paper_id: str, scenario: str,
    field: str, before: Any, after: Any,
) -> None:
    changes.append({"paper_id": paper_id, "scenario": scenario, "field": field,
                    "before": _json_value(before), "after": _json_value(after)})


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Create deterministic corruption without mutating the clean dataframe."""
    required = {"paper_id", "title", "summary", "published", "age_days",
                "summary_chars", "text_for_embedding"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing)}")
    if len(df) < 6:
        raise ValueError("At least 6 clean rows are required to run corruption scenarios.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    changes: list[dict[str, Any]] = []

    # Test-set documents come from df.head(5), so target these rows deliberately.
    for index in (0, 1):
        row = corrupted.loc[index]
        _log_change(changes, str(row["paper_id"]), "drop_latest_record",
                    "record", row.to_dict(), None)
    corrupted = corrupted.drop(index=[0, 1]).reset_index(drop=True)

    paper_id = str(corrupted.at[0, "paper_id"])
    old_summary = corrupted.at[0, "summary"]
    corrupted.at[0, "summary"] = ""
    corrupted.at[0, "summary_chars"] = 0
    _log_change(changes, paper_id, "blank_summary", "summary", old_summary, "")
    _log_change(changes, paper_id, "blank_summary", "summary_chars", len(str(old_summary)), 0)

    paper_id = str(corrupted.at[1, "paper_id"])
    old_published, old_age = corrupted.at[1, "published"], corrupted.at[1, "age_days"]
    corrupted.at[1, "published"], corrupted.at[1, "age_days"] = "2000-01-01", 9999
    _log_change(changes, paper_id, "stale_publication", "published", old_published, "2000-01-01")
    _log_change(changes, paper_id, "stale_publication", "age_days", old_age, 9999)

    paper_id = str(corrupted.at[2, "paper_id"])
    old_text = str(corrupted.at[2, "text_for_embedding"])
    noisy_text = NOISE_TEXT + old_text[:80]
    corrupted.at[2, "text_for_embedding"] = noisy_text
    _log_change(changes, paper_id, "embedding_noise", "text_for_embedding", old_text, noisy_text)

    paper_id = str(corrupted.at[3, "paper_id"])
    old_title = str(corrupted.at[3, "title"])
    corrupted.at[3, "title"] = old_title[:5]
    _log_change(changes, paper_id, "truncate_title", "title", old_title, old_title[:5])

    for index in (0, 1, 3):
        row = corrupted.loc[index]
        rebuilt = (f"Title: {row['title']} | Authors: {row.get('authors_joined', '')} "
                   f"| Summary: {row['summary']}")
        old_text = corrupted.at[index, "text_for_embedding"]
        corrupted.at[index, "text_for_embedding"] = rebuilt
        _log_change(changes, str(row["paper_id"]), "rebuild_embedding_text",
                    "text_for_embedding", old_text, rebuilt)

    duplicate_source = corrupted.iloc[[2]].copy(deep=True)
    duplicate_id = str(duplicate_source.iloc[0]["paper_id"])
    corrupted = pd.concat([corrupted, duplicate_source], ignore_index=True)
    _log_change(changes, duplicate_id, "duplicate_record", "record",
                None, duplicate_source.iloc[0].to_dict())

    write_json(Path(output_log_path), changes)
    return corrupted
