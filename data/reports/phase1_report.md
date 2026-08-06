# Phase 1 - Baseline Report

Sinh luc: 2026-08-06T09:55:22.498336+00:00

## 1. Nguon du lieu

| Thuoc tinh | Gia tri |
| --- | --- |
| source | Crossref REST API |
| query | artifical intelligence |
| filter | from-pub-date:2026-02-07,has-abstract:true |
| records_raw | 24 |
| records_clean | 24 |
| raw_mode | snapshot |
| run_date | 2026-08-06T09:54:59.742001+00:00 |

## 2. Metrics RAG tren du lieu sach

| Chi so | Gia tri |
| --- | --- |
| samples | 10 |
| Retrieval hit rate | 1.000 |
| Mean token F1 | 1.000 |
| Judge accuracy | 1.000 |
| Mean judge score | 5 |

### Ragas

| Ragas metric | Gia tri |
| --- | --- |
| skipped | Set RUN_RAGAS=1 to enable the slower Ragas pass. |

## 3. Data quality

Tong ket: **PASS** (0 check FAIL / 9 check), tren 24 dong.

| Check | Ket qua | Dong loi | Quan sat | Ky vong |
| --- | --- | --- | --- | --- |
| row_count_min | PASS | 0 | 24 | >= 15 dong |
| paper_id_not_null | PASS | 0 | 0 dong bi null hoac rong | moi dong co 'paper_id' khong null va khong rong |
| paper_id_unique | PASS | 0 | 24 gia tri duy nhat / 24 dong | paper_id unique tren toan bang |
| title_not_null | PASS | 0 | 0 dong bi null hoac rong | moi dong co 'title' khong null va khong rong |
| title_min_length | PASS | 0 | do dai nho nhat = 44, 0 dong duoi nguong | moi dong co do dai 'title' >= 10 ky tu |
| published_not_null | PASS | 0 | 0 dong bi null hoac rong | moi dong co 'published' khong null va khong rong |
| summary_min_length | PASS | 0 | summary_chars nho nhat = 210, 0 dong duoi nguong | moi dong co summary >= 100 ky tu |
| text_for_embedding_not_null | PASS | 0 | 0 dong bi null hoac rong | moi dong co 'text_for_embedding' khong null va khong rong |
| freshness_age | PASS | 0 | age_days lon nhat = 178, 0 dong stale | moi dong co age_days <= 180 |

## 4. Freshness

| Chi so | Gia tri |
| --- | --- |
| latest_published | 2026-07-17 |
| oldest_published | 2026-02-09 |
| stale_rows | 0 |
| total_rows | 24 |
| is_fresh | PASS |
