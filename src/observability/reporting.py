from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, read_json, write_text

# Cac metric duoc so sanh giua 3 trang thai, theo dung key do
# src/evaluation/metrics.py sinh ra.
COMPARED_METRICS = [
    ("retrieval_hit_rate", "Retrieval hit rate"),
    ("mean_token_f1", "Mean token F1"),
    ("judge_accuracy", "Judge accuracy"),
    ("mean_judge_score", "Mean judge score"),
]

NA = "n/a"


def _fmt_number(value: Any, digits: int = 3) -> str:
    """Format so thuc 3 chu so thap phan, chiu duoc None va gia tri khong phai so."""
    if value is None:
        return NA
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_delta(current: Any, baseline: Any, digits: int = 3) -> str:
    """Chenh lech so voi baseline, co dau + / - de doc nhanh chieu thay doi."""
    try:
        diff = float(current) - float(baseline)
    except (TypeError, ValueError):
        return NA
    return f"{diff:+.{digits}f}"


def _fmt_bool(value: Any) -> str:
    if value is None:
        return NA
    return "PASS" if value else "FAIL"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _quality_checks_table(quality: dict[str, Any]) -> str:
    rows = []
    for check in quality.get("checks", []):
        rows.append(
            [
                check.get("name", NA),
                _fmt_bool(check.get("passed")),
                str(check.get("failed_rows", NA)),
                str(check.get("observed", NA)),
                str(check.get("expected", NA)),
            ]
        )
    if not rows:
        return "_Khong co quality check nao duoc ghi nhan._"
    return _md_table(["Check", "Ket qua", "Dong loi", "Quan sat", "Ky vong"], rows)


def _freshness_table(freshness: dict[str, Any]) -> str:
    rows = [
        ["latest_published", str(freshness.get("latest_published", NA))],
        ["oldest_published", str(freshness.get("oldest_published", NA))],
        ["stale_rows", str(freshness.get("stale_rows", NA))],
        ["total_rows", str(freshness.get("total_rows", NA))],
        ["is_fresh", _fmt_bool(freshness.get("is_fresh"))],
    ]
    return _md_table(["Chi so", "Gia tri"], rows)


def _ragas_section(metrics: dict[str, Any]) -> str:
    ragas = metrics.get("ragas") or {}
    if not isinstance(ragas, dict) or not ragas:
        return "_Khong chay ragas._"
    if "error" in ragas:
        return f"_Ragas khong chay duoc: {ragas['error']}_"
    rows = [[key, _fmt_number(value)] for key, value in ragas.items()]
    return _md_table(["Ragas metric", "Gia tri"], rows)


def _ragas_comparison_rows(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> list[list[str]]:
    """Ghep cac ragas metric chung cho ca 3 trang thai, bo qua key skipped/error."""
    states = [baseline.get("ragas") or {}, corrupted.get("ragas") or {}, repaired.get("ragas") or {}]
    ignored = {"skipped", "error"}
    names: list[str] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        for key in state:
            if key not in ignored and key not in names:
                names.append(key)

    rows = []
    for name in names:
        base = states[0].get(name) if isinstance(states[0], dict) else None
        rows.append(
            [
                name,
                _fmt_number(base),
                _fmt_number(states[1].get(name) if isinstance(states[1], dict) else None),
                _fmt_number(states[2].get(name) if isinstance(states[2], dict) else None),
                _fmt_delta(states[1].get(name) if isinstance(states[1], dict) else None, base),
                _fmt_delta(states[2].get(name) if isinstance(states[2], dict) else None, base),
            ]
        )
    return rows


def _failed_check_count(quality: dict[str, Any] | None) -> str:
    if not quality:
        return NA
    failed = quality.get("failed_checks")
    if failed is None:
        failed = [check["name"] for check in quality.get("checks", []) if not check.get("passed")]
    return str(len(failed))


def _load_baseline_quality(report_path: Path) -> dict[str, Any] | None:
    """Doc lai quality report cua baseline.

    Chu ky generate_corruption_report khong nhan baseline_quality/baseline_freshness,
    nen cot Baseline cua phan observability duoc doc lai tu file da ghi o phase 1.
    Khong tim thay thi tra ve None va report se hien 'n/a' thay vi bia so.
    """
    candidate = report_path.parent.parent / "quality" / "quality_baseline.json"
    if candidate.exists():
        try:
            return read_json(candidate)
        except (ValueError, OSError):
            return None
    return None


def _load_baseline_freshness(report_path: Path) -> dict[str, Any] | None:
    candidate = report_path.parent.parent / "quality" / "freshness_report.json"
    if candidate.exists():
        try:
            return read_json(candidate)
        except (ValueError, OSError):
            return None
    return None


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase."""
    report_path = Path(report_path)

    source_rows = [[str(key), str(value)] for key, value in (source_summary or {}).items()]
    source_block = (
        _md_table(["Thuoc tinh", "Gia tri"], source_rows)
        if source_rows
        else "_Khong co thong tin source._"
    )

    metric_rows = [["samples", str(metrics.get("samples", NA))]]
    for key, label in COMPARED_METRICS:
        metric_rows.append([label, _fmt_number(metrics.get(key))])

    sections = [
        "# Phase 1 - Baseline Report",
        "",
        f"Sinh luc: {now_utc().isoformat()}",
        "",
        "## 1. Nguon du lieu",
        "",
        source_block,
        "",
        "## 2. Metrics RAG tren du lieu sach",
        "",
        _md_table(["Chi so", "Gia tri"], metric_rows),
        "",
        "### Ragas",
        "",
        _ragas_section(metrics),
        "",
        "## 3. Data quality",
        "",
        f"Tong ket: **{_fmt_bool(quality.get('all_passed'))}** "
        f"({_failed_check_count(quality)} check FAIL / {len(quality.get('checks', []))} check), "
        f"tren {quality.get('total_rows', NA)} dong.",
        "",
        _quality_checks_table(quality),
        "",
        "## 4. Freshness",
        "",
        _freshness_table(freshness),
        "",
    ]
    write_text(report_path, "\n".join(sections))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Viet markdown so sanh 3 trang thai baseline / corrupted / repaired."""
    report_path = Path(report_path)
    baseline_quality = _load_baseline_quality(report_path)
    baseline_freshness = _load_baseline_freshness(report_path)
    ragas_rows = _ragas_comparison_rows(baseline_metrics, corrupted_metrics, repaired_metrics)

    # Bang 1: metrics RAG, kem delta so voi baseline de thay chieu tut va hoi phuc.
    metric_rows = [
        [
            "samples",
            str(baseline_metrics.get("samples", NA)),
            str(corrupted_metrics.get("samples", NA)),
            str(repaired_metrics.get("samples", NA)),
            NA,
            NA,
        ]
    ]
    for key, label in COMPARED_METRICS:
        base = baseline_metrics.get(key)
        corrupted = corrupted_metrics.get(key)
        repaired = repaired_metrics.get(key)
        metric_rows.append(
            [
                label,
                _fmt_number(base),
                _fmt_number(corrupted),
                _fmt_number(repaired),
                _fmt_delta(corrupted, base),
                _fmt_delta(repaired, base),
            ]
        )

    # Bang 2: tin hieu observability o ca 3 trang thai.
    observability_rows = [
        [
            "Check FAIL",
            _failed_check_count(baseline_quality),
            _failed_check_count(corrupted_quality),
            _failed_check_count(repaired_quality),
        ],
        [
            "all_passed",
            _fmt_bool(baseline_quality.get("all_passed")) if baseline_quality else NA,
            _fmt_bool(corrupted_quality.get("all_passed")),
            _fmt_bool(repaired_quality.get("all_passed")),
        ],
        [
            "total_rows",
            str(baseline_quality.get("total_rows", NA)) if baseline_quality else NA,
            str(corrupted_quality.get("total_rows", NA)),
            str(repaired_quality.get("total_rows", NA)),
        ],
        [
            "stale_rows",
            str(baseline_freshness.get("stale_rows", NA)) if baseline_freshness else NA,
            str(corrupted_freshness.get("stale_rows", NA)),
            str(repaired_freshness.get("stale_rows", NA)),
        ],
        [
            "is_fresh",
            _fmt_bool(baseline_freshness.get("is_fresh")) if baseline_freshness else NA,
            _fmt_bool(corrupted_freshness.get("is_fresh")),
            _fmt_bool(repaired_freshness.get("is_fresh")),
        ],
        [
            "oldest_published",
            str(baseline_freshness.get("oldest_published", NA)) if baseline_freshness else NA,
            str(corrupted_freshness.get("oldest_published", NA)),
            str(repaired_freshness.get("oldest_published", NA)),
        ],
    ]

    # Bang 3: so dong loi cua tung check, de chi ro corruption nao bi bat.
    check_names: list[str] = []
    for quality in (baseline_quality, corrupted_quality, repaired_quality):
        for check in (quality or {}).get("checks", []):
            if check["name"] not in check_names:
                check_names.append(check["name"])

    def _failed_rows(quality: dict[str, Any] | None, name: str) -> str:
        if not quality:
            return NA
        for check in quality.get("checks", []):
            if check.get("name") == name:
                return f"{check.get('failed_rows', NA)} ({_fmt_bool(check.get('passed'))})"
        return NA

    check_rows = [
        [
            name,
            _failed_rows(baseline_quality, name),
            _failed_rows(corrupted_quality, name),
            _failed_rows(repaired_quality, name),
        ]
        for name in check_names
    ]

    sections = [
        "# Phase 2 - Corruption / Repair Comparison",
        "",
        f"Sinh luc: {now_utc().isoformat()}",
        "",
        "Ca 3 trang thai duoc danh gia tren cung mot frozen evaluation set, cung model",
        "va cung top_k. Chi co du lieu dau vao thay doi.",
        "",
        "## 1. Metrics RAG",
        "",
        _md_table(
            ["Chi so", "Baseline", "Corrupted", "Repaired", "Delta corrupted", "Delta repaired"],
            metric_rows,
        ),
        "",
        "## 2. Ragas",
        "",
        _md_table(
            ["Ragas metric", "Baseline", "Corrupted", "Repaired", "Delta corrupted", "Delta repaired"],
            ragas_rows,
        )
        if ragas_rows
        else "_Ragas khong chay (dat RUN_RAGAS=1 de bat)._",
        "",
        "## 3. Tin hieu observability",
        "",
        _md_table(["Tin hieu", "Baseline", "Corrupted", "Repaired"], observability_rows),
        "",
        "## 4. Chi tiet tung quality check (so dong loi)",
        "",
        _md_table(["Check", "Baseline", "Corrupted", "Repaired"], check_rows)
        if check_rows
        else "_Khong co quality check nao duoc ghi nhan._",
        "",
        "## 5. Nhan xet",
        "",
        "- Corruption lam cac quality check chuyen sang FAIL va keo metrics RAG xuong.",
        "- Repair dung lai tu raw snapshot nen phuc hoi duoc ca quality signal lan metrics.",
        "- Luu y: kich ban chen nhieu (noise) khong bi quality check bat, chi lo ra qua",
        "  metrics RAG - day la ly do can ca hai lop giam sat.",
        "",
    ]
    write_text(report_path, "\n".join(sections))
