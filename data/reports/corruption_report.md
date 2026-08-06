# Phase 2 - Corruption / Repair Comparison

Sinh luc: 2026-08-06T09:56:39.170453+00:00

Ca 3 trang thai duoc danh gia tren cung mot frozen evaluation set, cung model
va cung top_k. Chi co du lieu dau vao thay doi.

## 1. Metrics RAG

| Chi so | Baseline | Corrupted | Repaired | Delta corrupted | Delta repaired |
| --- | --- | --- | --- | --- | --- |
| samples | 10 | 10 | 10 | n/a | n/a |
| Retrieval hit rate | 1.000 | 0.400 | 1.000 | -0.600 | +0.000 |
| Mean token F1 | 1.000 | 0.310 | 1.000 | -0.690 | +0.000 |
| Judge accuracy | 1.000 | 0.400 | 1.000 | -0.600 | +0.000 |
| Mean judge score | 5 | 2.800 | 5 | -2.200 | +0.000 |

## 2. Tin hieu observability

| Tin hieu | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Check FAIL | 0 | 4 | 0 |
| all_passed | PASS | FAIL | PASS |
| total_rows | 24 | 23 | 24 |
| stale_rows | 0 | 1 | 0 |
| is_fresh | PASS | FAIL | PASS |
| oldest_published | 2026-02-09 | 2000-01-01 | 2026-02-09 |

## 3. Chi tiet tung quality check (so dong loi)

| Check | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| row_count_min | 0 (PASS) | 0 (PASS) | 0 (PASS) |
| paper_id_not_null | 0 (PASS) | 0 (PASS) | 0 (PASS) |
| paper_id_unique | 0 (PASS) | 1 (FAIL) | 0 (PASS) |
| title_not_null | 0 (PASS) | 0 (PASS) | 0 (PASS) |
| title_min_length | 0 (PASS) | 1 (FAIL) | 0 (PASS) |
| published_not_null | 0 (PASS) | 0 (PASS) | 0 (PASS) |
| summary_min_length | 0 (PASS) | 1 (FAIL) | 0 (PASS) |
| text_for_embedding_not_null | 0 (PASS) | 0 (PASS) | 0 (PASS) |
| freshness_age | 0 (PASS) | 1 (FAIL) | 0 (PASS) |

## 4. Nhan xet

- Corruption lam cac quality check chuyen sang FAIL va keo metrics RAG xuong.
- Repair dung lai tu raw snapshot nen phuc hoi duoc ca quality signal lan metrics.
- Luu y: kich ban chen nhieu (noise) khong bi quality check bat, chi lo ra qua
  metrics RAG - day la ly do can ca hai lop giam sat.
