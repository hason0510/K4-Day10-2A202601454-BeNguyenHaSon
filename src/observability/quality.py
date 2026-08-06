from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, safe_slug, write_json

# Nguong dung chung cho cac check. MIN_SUMMARY_CHARS phai bang rule cleaning
# (drop summary < 100 ky tu), neu dat cao hon thi baseline se FAIL oan.
MIN_ROW_COUNT = 15
MIN_TITLE_CHARS = 10
MIN_SUMMARY_CHARS = 100


def _blank_mask(series: pd.Series) -> pd.Series:
    """Mask cac o null hoac chuoi rong sau khi strip."""
    return series.isna() | series.astype(str).str.strip().eq("")


def _build_check(
    name: str,
    passed: bool,
    observed: Any,
    expected: str,
    failed_rows: int,
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "failed_rows": int(failed_rows),
    }


def _missing_column_check(name: str, column: str, expected: str) -> dict[str, Any]:
    """Cot khong ton tai duoc coi la FAIL thay vi nem KeyError."""
    return _build_check(
        name=name,
        passed=False,
        observed=f"column '{column}' khong ton tai trong dataframe",
        expected=expected,
        failed_rows=0,
    )


def _check_not_blank(df: pd.DataFrame, column: str, name: str) -> dict[str, Any]:
    expected = f"moi dong co '{column}' khong null va khong rong"
    if column not in df.columns:
        return _missing_column_check(name, column, expected)

    failed = int(_blank_mask(df[column]).sum())
    return _build_check(
        name=name,
        passed=failed == 0,
        observed=f"{failed} dong bi null hoac rong",
        expected=expected,
        failed_rows=failed,
    )


def _check_min_length(df: pd.DataFrame, column: str, name: str, min_chars: int) -> dict[str, Any]:
    expected = f"moi dong co do dai '{column}' >= {min_chars} ky tu"
    if column not in df.columns:
        return _missing_column_check(name, column, expected)

    lengths = df[column].fillna("").astype(str).str.strip().str.len()
    failed = int((lengths < min_chars).sum())
    shortest = int(lengths.min()) if len(lengths) else 0
    return _build_check(
        name=name,
        passed=failed == 0,
        observed=f"do dai nho nhat = {shortest}, {failed} dong duoi nguong",
        expected=expected,
        failed_rows=failed,
    )


def _check_row_count(df: pd.DataFrame) -> dict[str, Any]:
    total = len(df)
    return _build_check(
        name="row_count_min",
        passed=total >= MIN_ROW_COUNT,
        observed=total,
        expected=f">= {MIN_ROW_COUNT} dong",
        failed_rows=0 if total >= MIN_ROW_COUNT else MIN_ROW_COUNT - total,
    )


def _check_paper_id_unique(df: pd.DataFrame) -> dict[str, Any]:
    expected = "paper_id unique tren toan bang"
    if "paper_id" not in df.columns:
        return _missing_column_check("paper_id_unique", "paper_id", expected)

    duplicated = int(df["paper_id"].duplicated().sum())
    return _build_check(
        name="paper_id_unique",
        passed=duplicated == 0,
        observed=f"{df['paper_id'].nunique()} gia tri duy nhat / {len(df)} dong",
        expected=expected,
        failed_rows=duplicated,
    )


def _check_summary_length(df: pd.DataFrame) -> dict[str, Any]:
    """Uu tien cot summary_chars neu co, fallback ve do dai cua summary."""
    if "summary_chars" not in df.columns:
        return _check_min_length(df, "summary", "summary_min_length", MIN_SUMMARY_CHARS)

    lengths = pd.to_numeric(df["summary_chars"], errors="coerce").fillna(0)
    failed = int((lengths < MIN_SUMMARY_CHARS).sum())
    shortest = int(lengths.min()) if len(lengths) else 0
    return _build_check(
        name="summary_min_length",
        passed=failed == 0,
        observed=f"summary_chars nho nhat = {shortest}, {failed} dong duoi nguong",
        expected=f"moi dong co summary >= {MIN_SUMMARY_CHARS} ky tu",
        failed_rows=failed,
    )


def _stale_mask(df: pd.DataFrame, threshold_days: int) -> pd.Series:
    """Dong stale = age_days vuot nguong, hoac age_days khong doc duoc."""
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    return ages.isna() | (ages > threshold_days)


def _check_freshness(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    threshold = settings.freshness_threshold_days
    expected = f"moi dong co age_days <= {threshold}"
    if "age_days" not in df.columns:
        return _missing_column_check("freshness_age", "age_days", expected)

    stale = int(_stale_mask(df, threshold).sum())
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    oldest = int(ages.max()) if ages.notna().any() else None
    return _build_check(
        name="freshness_age",
        passed=stale == 0,
        observed=f"age_days lon nhat = {oldest}, {stale} dong stale",
        expected=expected,
        failed_rows=stale,
    )


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay bo data quality checks va ghi report JSON theo tung trang thai.

    Ham duoc goi 3 lan voi report_name = baseline / corrupted / repaired, nen ten file
    output phai chua report_name de giu du ca 3 ban lam minh chung cho C3 va C4.
    Khong dat check nao tren categories_joined: Crossref khong con tra ve `subject`
    nen cot do rong 100% va se lam baseline FAIL oan.
    """
    checks = [
        _check_row_count(df),
        _check_not_blank(df, "paper_id", "paper_id_not_null"),
        _check_paper_id_unique(df),
        _check_not_blank(df, "title", "title_not_null"),
        _check_min_length(df, "title", "title_min_length", MIN_TITLE_CHARS),
        _check_not_blank(df, "published", "published_not_null"),
        _check_summary_length(df),
        _check_not_blank(df, "text_for_embedding", "text_for_embedding_not_null"),
        _check_freshness(df, settings),
    ]

    failed_checks = [check["name"] for check in checks if not check["passed"]]
    payload = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "total_rows": len(df),
        "checks": checks,
        "failed_checks": failed_checks,
        "all_passed": not failed_checks,
    }

    report_path = settings.paths.quality_dir / f"quality_{safe_slug(report_name)}.json"
    write_json(report_path, payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report theo dung 5 field trong contract."""
    threshold = settings.freshness_threshold_days

    if "published" in df.columns:
        published = pd.to_datetime(df["published"], errors="coerce")
    else:
        published = pd.Series(dtype="datetime64[ns]")
    has_published = bool(published.notna().any())

    if "age_days" in df.columns:
        stale_rows = int(_stale_mask(df, threshold).sum())
    else:
        # Khong co age_days thi coi nhu khong do duoc freshness -> toan bo la stale.
        stale_rows = len(df)

    payload = {
        "latest_published": published.max().date().isoformat() if has_published else None,
        "oldest_published": published.min().date().isoformat() if has_published else None,
        "stale_rows": stale_rows,
        "total_rows": len(df),
        "is_fresh": stale_rows == 0,
    }

    write_json(Path(report_path), payload)
    return payload
