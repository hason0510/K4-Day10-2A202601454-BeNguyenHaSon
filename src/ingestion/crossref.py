from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
import html
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_API_URL = "https://api.crossref.org/works"
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_MAX_REQUEST_ATTEMPTS = 4
_REQUEST_TIMEOUT_SECONDS = 30
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    decoded = html.unescape(value)
    without_tags = _HTML_TAG_PATTERN.sub(" ", decoded)
    return normalize_whitespace(html.unescape(without_tags))


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            cleaned = _clean_text(item)
            if cleaned:
                return cleaned
        return ""
    return _clean_text(value)


def _unique_texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    results: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = _clean_text(item)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            results.append(cleaned)
    return results


def _date_from_parts(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts or not isinstance(date_parts[0], list):
        return ""

    parts = date_parts[0]
    if not parts:
        return ""
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _normalize_date(value: Any) -> str:
    from_parts = _date_from_parts(value)
    if from_parts:
        return from_parts

    if isinstance(value, dict):
        date_time = value.get("date-time")
        if isinstance(date_time, str):
            return _normalize_date(date_time)
        timestamp = value.get("timestamp")
        if isinstance(timestamp, (int, float)):
            try:
                return datetime.fromtimestamp(timestamp / 1000, tz=UTC).date().isoformat()
            except (OSError, OverflowError, ValueError):
                return ""

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return ""
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            match = re.match(r"^\d{4}-\d{2}-\d{2}", candidate)
            if match:
                try:
                    return date.fromisoformat(match.group(0)).isoformat()
                except ValueError:
                    return ""
    return ""


def _authors_from_item(item: dict[str, Any]) -> list[str]:
    raw_authors = item.get("author")
    if not isinstance(raw_authors, list):
        return []

    authors: list[str] = []
    seen: set[str] = set()
    for raw_author in raw_authors:
        if not isinstance(raw_author, dict):
            continue
        given = _clean_text(raw_author.get("given"))
        family = _clean_text(raw_author.get("family"))
        name = normalize_whitespace(" ".join(part for part in (given, family) if part))
        if not name:
            name = _clean_text(raw_author.get("name"))
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            authors.append(name)
    return authors


def _pdf_url_from_item(item: dict[str, Any]) -> str:
    links = item.get("link")
    if not isinstance(links, list):
        return ""
    for link in links:
        if not isinstance(link, dict):
            continue
        url = _clean_text(link.get("URL"))
        content_type = _clean_text(link.get("content-type")).lower()
        if url and (content_type == "application/pdf" or url.lower().split("?", 1)[0].endswith(".pdf")):
            return url
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref works response into normalized, unique paper records."""
    if not isinstance(payload, dict):
        raise ValueError("Crossref payload must be a JSON object.")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Crossref payload is missing the 'message' object.")
    items = message.get("items")
    if not isinstance(items, list):
        raise ValueError("Crossref payload is missing the 'message.items' list.")

    records: list[PaperRecord] = []
    seen_paper_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = _clean_text(item.get("DOI")).lower()
        title = _first_text(item.get("title"))
        summary = _clean_text(item.get("abstract"))
        if not paper_id or not title or not summary or paper_id in seen_paper_ids:
            continue

        categories = _unique_texts(item.get("subject"))
        published = next(
            (
                normalized
                for key in ("published-print", "published-online", "published", "issued", "created")
                if (normalized := _normalize_date(item.get(key)))
            ),
            "",
        )
        updated = next(
            (
                normalized
                for key in ("indexed", "deposited", "created")
                if (normalized := _normalize_date(item.get(key)))
            ),
            published,
        )
        abs_url = _clean_text(item.get("URL")) or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=_authors_from_item(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=_pdf_url_from_item(item),
                comment="",
            )
        )
        seen_paper_ids.add(paper_id)
    return records


def _retry_delay_seconds(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "").strip()
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), 60.0)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                return min(max((retry_at - datetime.now(UTC)).total_seconds(), 0.0), 60.0)
            except (TypeError, ValueError, OverflowError):
                pass
    return float(2**attempt)


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref works, persist the raw response, and persist parsed records."""
    if settings.max_results <= 0:
        raise ValueError("settings.max_results must be greater than zero.")

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "day10-data-observability-lab/0.1 (Crossref metadata ingestion)",
    }

    payload: dict[str, Any] | None = None
    for attempt in range(_MAX_REQUEST_ATTEMPTS):
        try:
            response = requests.get(
                CROSSREF_API_URL,
                params=params,
                headers=headers,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            if attempt == _MAX_REQUEST_ATTEMPTS - 1:
                raise RuntimeError(
                    f"Crossref request failed after {_MAX_REQUEST_ATTEMPTS} attempts: {exc}"
                ) from exc
            time.sleep(float(2**attempt))
            continue

        if response.status_code in _TRANSIENT_STATUS_CODES and attempt < _MAX_REQUEST_ATTEMPTS - 1:
            time.sleep(_retry_delay_seconds(response, attempt))
            continue

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"Crossref returned HTTP {response.status_code}.") from exc

        try:
            decoded = response.json()
        except ValueError as exc:
            raise RuntimeError("Crossref returned a response that is not valid JSON.") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Crossref returned JSON with an unexpected top-level type.")
        payload = decoded
        break

    if payload is None:  # Defensive guard; every loop exit above either assigns or raises.
        raise RuntimeError("Crossref request ended without a response payload.")

    write_json(settings.paths.raw_api_response, payload)
    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a parsed raw-record snapshot and validate its PaperRecord schema."""
    snapshot_path = Path(path)
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Raw records snapshot does not exist: {snapshot_path}")

    payload = read_json(snapshot_path)
    if not isinstance(payload, list):
        raise ValueError("Raw records snapshot must contain a JSON list.")

    expected_fields = {field.name for field in fields(PaperRecord)}
    records: list[PaperRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} must be a JSON object.")
        actual_fields = set(item)
        missing = sorted(expected_fields - actual_fields)
        unexpected = sorted(actual_fields - expected_fields)
        if missing or unexpected:
            details = []
            if missing:
                details.append(f"missing fields: {', '.join(missing)}")
            if unexpected:
                details.append(f"unexpected fields: {', '.join(unexpected)}")
            raise ValueError(f"Invalid raw record at index {index} ({'; '.join(details)}).")
        if not isinstance(item["authors"], list) or not all(isinstance(value, str) for value in item["authors"]):
            raise ValueError(f"Raw record at index {index} has an invalid authors list.")
        if not isinstance(item["categories"], list) or not all(
            isinstance(value, str) for value in item["categories"]
        ):
            raise ValueError(f"Raw record at index {index} has an invalid categories list.")
        records.append(PaperRecord(**item))
    return records
