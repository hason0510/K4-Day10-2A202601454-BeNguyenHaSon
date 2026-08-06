from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def build_test_set(df: pd.DataFrame, output_path: Path | str) -> list[dict[str, Any]]:
    """Build a test set from the cleaned dataframe and save it to a JSON file."""
    if df.empty:
        return []

    # 1. Check minimum documents and select representative papers
    num_samples = min(5, len(df))
    sample_df = df.head(num_samples)

    test_set: list[dict[str, Any]] = []
    question_idx = 1

    # 2. Generate multiple types of questions
    for _, row in sample_df.iterrows():
        paper_id = str(row.get("paper_id", ""))
        title = str(row.get("title", ""))
        authors = str(row.get("authors_joined", ""))
        summary = str(row.get("summary", ""))
        categories = str(row.get("categories_joined", ""))
        published = str(row.get("published", ""))

        if not paper_id or not title:
            continue

        # authors
        if authors:
            test_set.append({
                "id": f"q{question_idx}",
                "question_type": "factual",
                "question": f"Ai là tác giả của bài báo '{title}'?",
                "ground_truth": authors,
                "ground_truth_doc_ids": [paper_id]
            })
            question_idx += 1

        # date
        if published:
            test_set.append({
                "id": f"q{question_idx}",
                "question_type": "factual",
                "question": f"Bài báo '{title}' được xuất bản vào ngày nào?",
                "ground_truth": published,
                "ground_truth_doc_ids": [paper_id]
            })
            question_idx += 1

        # categories
        if categories:
            test_set.append({
                "id": f"q{question_idx}",
                "question_type": "factual",
                "question": f"Bài báo '{title}' thuộc (các) chủ đề/danh mục nào?",
                "ground_truth": categories,
                "ground_truth_doc_ids": [paper_id]
            })
            question_idx += 1

        # summary
        if summary:
            test_set.append({
                "id": f"q{question_idx}",
                "question_type": "summary",
                "question": f"Nội dung tóm tắt của bài báo '{title}' là gì?",
                "ground_truth": summary,
                "ground_truth_doc_ids": [paper_id]
            })
            question_idx += 1

        # Limit to around 10-15 questions total to keep it small as requested (5-10 câu)
        if question_idx > 10:
            break

    # 3. Save JSON to output_path
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_set, f, ensure_ascii=False, indent=2)

    return test_set
