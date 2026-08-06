from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the reproducible baseline pipeline end-to-end."""
    settings = load_settings()
    paths = settings.paths

    use_snapshot = paths.raw_records_json.is_file() and not settings.refresh_source
    records = load_raw_records(paths.raw_records_json) if use_snapshot else fetch_source_records(settings)
    if not records:
        raise RuntimeError("Source ingestion returned no usable paper records.")

    run_date = now_utc()
    clean_df = build_clean_dataframe(records, run_date=run_date)
    if clean_df.empty:
        raise RuntimeError("Cleaning removed every source record; baseline cannot continue.")
    write_csv(clean_df, paths.clean_csv)
    write_json(paths.clean_json, clean_df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(clean_df, settings, paths.embeddings_json)
    if settings.refresh_test_set or not paths.eval_testset.is_file():
        test_set = build_test_set(clean_df, paths.eval_testset)
        if not test_set:
            raise RuntimeError("Evaluation-set builder returned no questions.")

    bundle = evaluate_pipeline(
        settings, index, paths.eval_testset,
        paths.baseline_metrics, paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, paths.freshness_report)
    source_summary = {
        "source": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "records_raw": len(records),
        "records_clean": len(clean_df),
        "raw_mode": "snapshot" if use_snapshot else "refreshed_api",
        "run_date": run_date.isoformat(),
    }
    generate_phase1_report(paths.baseline_report, source_summary, bundle.summary, quality, freshness)

    print(f"Baseline complete: {len(clean_df)} clean records, {bundle.summary['samples']} evaluations.")
    print(f"Metrics: {paths.baseline_metrics}")
    print(f"Report: {paths.baseline_report}")
