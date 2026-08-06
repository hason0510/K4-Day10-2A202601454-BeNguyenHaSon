from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _require_files(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Run the baseline pipeline first. Missing required artifacts: " + ", ".join(missing)
        )


def main() -> None:
    """Measure corruption impact and repair from the frozen raw snapshot."""
    settings = load_settings()
    paths = settings.paths
    _require_files([
        paths.raw_records_json,
        paths.clean_json,
        paths.eval_testset,
        paths.baseline_metrics,
        paths.freshness_report,
        paths.quality_dir / "quality_baseline.json",
    ])

    baseline_payload = read_json(paths.clean_json)
    if not isinstance(baseline_payload, list) or not baseline_payload:
        raise ValueError("Baseline clean JSON must contain a non-empty record list.")
    baseline_df = pd.DataFrame(baseline_payload)
    baseline_metrics = read_json(paths.baseline_metrics)

    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings, corrupted_index, paths.eval_testset,
        paths.corrupted_metrics, paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "freshness_corrupted.json",
    )

    # Reclean the exact raw snapshot; refetching would invalidate comparison.
    raw_records = load_raw_records(paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date=now_utc())
    if repaired_df.empty:
        raise RuntimeError("Repair from raw snapshot produced an empty dataframe.")
    write_csv(repaired_df, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, paths.repaired_embeddings_json,
    )
    repaired_bundle = evaluate_pipeline(
        settings, repaired_index, paths.eval_testset,
        paths.repaired_metrics, paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, paths.quality_dir / "freshness_repaired.json",
    )

    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_bundle.summary,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    print(
        "Corruption flow complete: "
        f"baseline={len(baseline_df)}, corrupted={len(corrupted_df)}, "
        f"repaired={len(repaired_df)} records."
    )
    print(f"Comparison report: {paths.comparison_report}")
