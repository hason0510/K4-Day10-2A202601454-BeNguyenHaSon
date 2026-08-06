from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from ingestion.crossref import PaperRecord


def _remove_html_tags(text: str) -> str:
    """Remove XML/HTML tags from a string."""
    if not isinstance(text, str):
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records and return a ready-to-embed DataFrame."""
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([asdict(r) for r in records])

    # 1. Normalize text first: remove XML/HTML tags from title and summary.
    #    Must run before the length rule, otherwise markup inflates the character
    #    count and a summary that is too short after cleaning would survive.
    df = df.dropna(subset=["title", "summary"])
    df["title"] = df["title"].apply(_remove_html_tags)
    df["summary"] = df["summary"].apply(_remove_html_tags)

    # 2. Drop records with missing title or short summary (< 100 characters)
    df = df[df["title"].str.strip() != ""]
    df = df[df["summary"].str.len() >= 100]

    # 3. Create joined string columns for authors and categories
    df["authors_joined"] = df["authors"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else ""
    )
    df["categories_joined"] = df["categories"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else ""
    )
    df["summary_chars"] = df["summary"].str.len()

    # 4. Calculate freshness: published date and age_days
    df["published_dt"] = pd.to_datetime(df["published"], errors="coerce")
    # Ngay khong parse duoc giu nguyen NaN thay vi sentinel -1: -1 se bi doc nham
    # la "rat moi" va lot qua freshness check.
    df["age_days"] = (pd.Timestamp(run_date.date()) - df["published_dt"]).dt.days
    df["published"] = df["published_dt"].dt.strftime("%Y-%m-%d").fillna("")
    df = df.drop(columns=["published_dt"])

    # 5. Create semantic representation column
    df["text_for_embedding"] = (
        "Title: " + df["title"] + 
        " | Authors: " + df["authors_joined"] + 
        " | Summary: " + df["summary"]
    )

    # 6. Deduplicate by paper_id
    df = df.drop_duplicates(subset=["paper_id"])

    # 7. Sort by published date descending
    df = df.sort_values(by="published", ascending=False).reset_index(drop=True)

    return df


def save_clean_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    """Save cleaned DataFrame to CSV and JSON formats."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient="records", indent=2)
