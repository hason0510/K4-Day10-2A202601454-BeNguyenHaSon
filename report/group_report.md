# Group Report — Day 10: Data Pipeline & Data Observability

> Dùng mẫu này cho báo cáo chung của nhóm 3–5 thành viên. Thay toàn bộ nội dung trong dấu `[ ]` bằng thông tin và kết quả thực tế. Xóa các dòng hướng dẫn không còn cần thiết trước khi nộp.

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4              |
| Tên nhóm         | ChillGuys     |
| Repository         | https://github.com/hason0510/K4-Day10-2A202601454-BeNguyenHaSon |
| Ngày hoàn thành | 2026-08-06               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Phạm Tùng Dương | 2A202601404 | Source Ingestion Owner | `src/ingestion/crossref.py` — `fetch_source_records`, `parse_crossref_payload`, `load_raw_records`; artifact `data/raw/crossref_response.json`, `data/raw/crossref_records.json` |
| 2 | Hồ Lương An | 2A202601332 | Data Model & Eval Set Owner | `src/ingestion/cleaning.py` — `build_clean_dataframe`, `save_clean_dataframe`; `src/evaluation/testset.py`; artifact `data/clean/papers_clean.csv|json`, `data/eval/test_set.json` |
| 3 | Bế Nguyễn Hà Sơn | 2A202601454 | Data Observability Owner | `src/observability/quality.py` — `run_data_quality_checks`, `build_freshness_report`; `src/observability/reporting.py` — `generate_phase1_report`, `generate_corruption_report`; artifact `data/quality/*.json`, `data/reports/*.md` |
| 4 | Nguyễn Thành Vinh | 2A202601556 | Corruption & Integration Owner | `src/ingestion/corruption.py` — `corrupt_clean_dataframe`; `src/pipelines/phase1.py`; `src/pipelines/corruption_flow.py`; artifact `data/results/*.json`, `data/embeddings/*.json` |

## 2. Tóm tắt kết quả

Viết từ 150–250 từ, trả lời ngắn gọn:

- Nhóm đã hoàn thành những phần nào?
- Baseline pipeline đã tạo ra các artifact nào?
- Corruption nào ảnh hưởng rõ nhất đến data quality hoặc agent?
- Repair đã phục hồi được chỉ số nào?
- Blocker hoặc giới hạn quan trọng nhất còn lại là gì?

**Tóm tắt của nhóm:**

Nhóm đã hoàn thành toàn bộ luồng end-to-end: ingestion từ Crossref, cleaning và data contract, embedding/index bằng ChromaDB, frozen evaluation set, quality/freshness monitoring, corruption và repair, cùng hai báo cáo markdown tự sinh. Baseline pipeline (`script/run_phase1.py`) tạo ra `data/raw/crossref_response.json` và `crossref_records.json` (24 records), `data/clean/papers_clean.csv|json` (24 dòng), embedding manifest `data/embeddings/papers_embeddings.json` với collection Chroma `papers-baseline`, frozen test set 10 câu tại `data/eval/test_set.json`, `data/results/baseline_metrics.json` và `baseline_answers.json`, `data/results/agent_demo_answers.json`, `data/quality/quality_baseline.json` + `freshness_report.json`, và `data/reports/phase1_report.md`.

Baseline đạt `retrieval_hit_rate` 1.000, `mean_token_f1` 1.000, `judge_accuracy` 1.000, `mean_judge_score` 5, Ragas `context_precision`/`context_recall`/`faithfulness` cùng ở 0.700, quality 0/9 check FAIL và `is_fresh: true`. Corruption gồm 6 kịch bản xác định (không random) đã kéo bốn metric xuống 0.400 / 0.310 / 0.300 / 2.500 và làm 4/9 check FAIL, `is_fresh: false`.

Kịch bản ảnh hưởng rõ nhất là `drop_latest_record`: xóa 2 tài liệu nằm trong `ground_truth_doc_ids` khiến 6/10 câu hỏi (q1–q6) trượt retrieval, chiếm toàn bộ mức sụt của `retrieval_hit_rate`. Repair bằng cách clean lại raw snapshot đã phục hồi **hoàn toàn** cả bốn metric về đúng mức baseline, quality về 0 FAIL và freshness về `Fresh` (24 dòng, `oldest_published` 2026-02-09).

Giới hạn lớn nhất còn lại: kịch bản `embedding_noise` không bị bất kỳ quality check nào bắt, `answer_relevancy` của Ragas phân biệt yếu giữa ba trạng thái (0.232 → 0.158 → 0.238), và corruption áp dụng đồng thời nên chưa tách được đóng góp riêng của từng kịch bản.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

Điều chỉnh sơ đồ dưới đây nếu cách triển khai thực tế của nhóm khác starter:

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API `https://api.crossref.org/works` (query + filter từ `Settings`) | Fetch có timeout 30s, retry tối đa 4 lần cho `429/5xx` với exponential backoff và `Retry-After`; parse `message.items`; gỡ JATS/HTML; DOI lowercase làm `paper_id`; chuẩn hóa ngày; loại record thiếu DOI/title/abstract và DOI trùng | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | TV1 — Phạm Tùng Dương |
| Cleaning          | `list[PaperRecord]` từ raw snapshot + `run_date`        | Gỡ thẻ XML/HTML trước khi đo độ dài; drop title rỗng và summary < 100 ký tự; gộp `authors_joined`/`categories_joined`; tính `summary_chars`, `age_days`; dựng `text_for_embedding`; dedupe `paper_id`; sort `published` giảm dần     | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` (24 dòng, 11 cột contract) | TV2 — Hồ Lương An |
| Embedding/index   | Cột `text_for_embedding` của cleaned DataFrame        | Local `sentence-transformers/all-MiniLM-L6-v2` (vector 384 chiều, không gọi API); ChromaDB persistent tại `data/chroma`; ba collection tách biệt `papers-baseline` / `papers-corrupted` / `papers-repaired`; metadata mang `paper_id`       | `data/embeddings/papers_embeddings.json`, `papers_embeddings_corrupted.json`, `papers_embeddings_repaired.json`; `data/chroma/` | TV4 — Nguyễn Thành Vinh (cấu hình + orchestration) |
| Evaluation        | Frozen `test_set.json` + Chroma collection tương ứng        | Sinh test set bằng template cứng (TV2); retrieval `top_k=4`, so `paper_id` với `ground_truth_doc_ids`; `token_f1`; LLM judge `gpt-4o-mini`     | `data/eval/test_set.json`; `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json` và ba file `*_answers.json` | TV2 (test set) — Hồ Lương An; TV4 (chạy evaluate) — Nguyễn Thành Vinh |
| Observability     | Cleaned/corrupted/repaired DataFrame + `Settings`        | 9 quality check (completeness, uniqueness, độ dài, freshness) và freshness report 5 field; sinh 2 báo cáo markdown thuần trình bày | `data/quality/quality_{baseline,corrupted,repaired}.json`, `data/quality/freshness_{report,corrupted,repaired}.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | TV3 — Bế Nguyễn Hà Sơn |
| Corruption/repair | Cleaned DataFrame (baseline) và raw snapshot        | 6 kịch bản corruption xác định, không random, không mutate input; repair bằng cách clean lại `crossref_records.json` qua đúng `build_clean_dataframe`    | `data/clean/papers_clean_corrupted.*`, `papers_clean_repaired.*`, `data/results/corruption_log.json` | TV4 — Nguyễn Thành Vinh |
| Orchestration     | Toàn bộ module trên        | `phase1.py`: raw → clean → index → test set → evaluate → quality/freshness → report. `corruption_flow.py`: load baseline artifacts → corrupt → re-index → re-evaluate → repair → re-index → re-evaluate → comparison report. Giữ nguyên test set, model và `top_k` ở cả ba trạng thái           | `data/reports/phase1_report.md`, `data/reports/corruption_report.md`, toàn bộ `data/results/`        | TV4 — Nguyễn Thành Vinh |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `openai`         |
| `LLM_MODEL`                | `gpt-4o-mini`         |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` chạy local (`EMBEDDING_PROVIDER=local`), vector 384 chiều, không cần API key         |
| Số lượng Crossref records | `max_results = 24`; nhận về và parse thành công 24/24         |
| Retrieval`top_k`           | `4`         |
| Freshness threshold          | `180` ngày (`freshness_threshold_days`, cũng dùng cho filter `from-pub-date`)         |
| Random seed, nếu có        | Không dùng random. Corruption là hàm xác định trên dataset đã sort `published` giảm dần; `REFRESH_SOURCE` và `REFRESH_TEST_SET` để trống nên pipeline chạy trên snapshot cố định         |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

Chỉ giữ lại cách nhóm đã dùng.

```bash
python -m pip install -e .
```

### Lệnh chạy

Baseline:

```bash
python script/run_phase1.py
```

Corruption flow:

```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công (exit code 0) | 2026-08-06, 14:51–14:52 UTC (`run_date` 14:51:32Z, `quality_baseline` 14:52:50Z)                  | `data/reports/phase1_report.md`, `data/results/baseline_metrics.json` (hit 1.000 / F1 1.000 / judge 1.000 / score 5 / Ragas 0.700), `data/results/agent_demo_answers.json` (3/3 câu trả lời từ agent, 0 lỗi), `data/quality/quality_baseline.json` (`all_passed: true`) — không file nào chứa secret |
| Corruption flow   | Thành công (exit code 0) | 2026-08-06, 14:55–14:56 UTC (`quality_corrupted` 14:55:34Z, `quality_repaired` 14:56:19Z)                  | `data/reports/corruption_report.md`, `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `corruption_log.json` (12 entry), `data/quality/quality_{corrupted,repaired}.json` — không file nào chứa secret |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API — `https://api.crossref.org/works` |
| Query/filter                | query `artifical intelligence`; filter `from-pub-date:2026-02-07,has-abstract:true`; `rows=24`                  |
| Thời điểm lấy dữ liệu | Snapshot dùng cho bài nộp: `run_date` 2026-08-06T14:51:32Z (pipeline chạy ở chế độ `raw_mode: snapshot`, chỉ fetch lại khi bật `REFRESH_SOURCE`)                           |
| Số record nhận được    | 24 items Crossref → 24 `PaperRecord` (0 DOI trùng, 0 record thiếu DOI/title/summary; 16 record có PDF URL; 24/24 không có `subject`)                         |
| Cơ chế retry/backoff      | Timeout 30s, tối đa 4 lần thử, retry cho lỗi kết nối và HTTP `429/500/502/503/504`, exponential backoff, ưu tiên header `Retry-After`                       |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | `str` | Có | DOI lowercase, document identity ổn định xuyên suốt pipeline; cũng là `ground_truth_doc_ids` | Thiếu DOI → loại record ở ingestion; DOI trùng → giữ bản đầu tiên (`drop_duplicates`) |
| `title` | `str` | Có | Tiêu đề đã gỡ JATS/HTML và chuẩn hóa khoảng trắng | Thiếu hoặc rỗng sau khi gỡ tag → loại record ở cleaning |
| `summary` | `str` | Có | Abstract đã gỡ JATS/HTML | Thiếu → loại ở ingestion; < 100 ký tự sau khi làm sạch → loại ở cleaning |
| `authors` / `authors_joined` | `list[str]` / `str` | Không | Danh sách tác giả đã dedupe và bản nối bằng `, ` để đưa vào embedding | Thiếu → list rỗng, chuỗi rỗng (không dùng `None`/`NaN`/`"N/A"`) |
| `categories` / `categories_joined` | `list[str]` / `str` | Không | Chủ đề từ Crossref `subject` | Nguồn không trả `subject` cho 24/24 record → giữ list rỗng, **không** tự sinh category để không làm sai lệch raw data |
| `published` | `str` `YYYY-MM-DD` | Có | Ngày xuất bản chuẩn hóa; ngày thiếu thành phần lấy ngày đầu kỳ (`2026-07` → `2026-07-01`) | Không parse được → `pd.to_datetime(errors="coerce")` giữ `NaT`, `published` thành chuỗi rỗng và `age_days` là `NaN` (không dùng sentinel `-1` vì sẽ bị hiểu nhầm là "rất mới") |
| `age_days` | `int`/`NaN` | Có | Số ngày từ `published` tới `run_date`, cơ sở cho freshness | `NaN` → coi là stale ở freshness check |
| `summary_chars` | `int` | Có | Độ dài summary, dùng cho check `summary_min_length` | Tính lại sau mọi thay đổi summary (kể cả sau corruption) |
| `text_for_embedding` | `str` | Có | Chuỗi đưa vào embedding model | Được dựng lại từ `title`/`authors_joined`/`summary` mỗi khi các trường nguồn đổi |
| `abs_url` / `pdf_url` | `str` | Không | Link DOI và link PDF để truy vết | Thiếu → chuỗi rỗng (8/24 record không có PDF URL) |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Gỡ thẻ XML/HTML khỏi `title` và `summary` **trước** khi đo độ dài | Validity | 24/24 record đi qua rule (markup không còn trong `papers_clean.csv`) | So `data/raw/crossref_records.json` với `data/clean/papers_clean.csv`; không còn chuỗi `<...>` |
| Loại record thiếu `title` hoặc `title` rỗng sau khi gỡ tag | Completeness | 0 | `quality_baseline.json` → `title_not_null` PASS, `title_min_length` PASS (min 44 ký tự) |
| Loại record có `summary` < 100 ký tự | Completeness/Validity | 0 (summary ngắn nhất 210 ký tự) | `quality_baseline.json` → `summary_min_length` PASS, observed `summary_chars nho nhat = 210` |
| Dedupe theo `paper_id` (`drop_duplicates`) | Uniqueness | 0 ở baseline (raw đã 0 DOI trùng) | `quality_baseline.json` → `paper_id_unique`: 24 giá trị duy nhất / 24 dòng |
| Chuẩn hóa `published` về `YYYY-MM-DD` và tính `age_days` từ `run_date` | Timeliness/Validity | 24/24 | `freshness_report.json`: `latest_published` 2026-07-17, `oldest_published` 2026-02-09, `stale_rows` 0 |
| Sort theo `published` giảm dần và reset index | Consistency (tính xác định của thứ tự) | 24/24 | Thứ tự dòng trong `papers_clean.csv` trùng khít `papers_clean_repaired.csv` (cùng kích thước 92.853 byte) |

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:

`text_for_embedding` được ghép theo mẫu cố định `Title: {title} | Authors: {authors_joined} | Summary: {summary}`. Chọn mẫu này vì test set có cả câu hỏi factual về tác giả lẫn câu hỏi summary, nên vector cần mang đồng thời tín hiệu tiêu đề, tác giả và nội dung; nếu chỉ embed summary thì câu hỏi "Who authored…" mất chỗ bám. Chuỗi được dựng **sau** bước gỡ HTML để markup không lọt vào vector.

Document ID là DOI viết thường, lấy từ ingestion và **không được đổi ở bất kỳ bước sau nào** — đây là contract chốt giữa TV1 và TV2. Nhờ vậy `ground_truth_doc_ids` trong test set, metadata trong Chroma và khóa của quality check `paper_id_unique` đều trỏ về cùng một định danh. Trong Chroma, mỗi document còn có `record_id` dạng `{paper_id}::{chunk_index}` nhưng `paper_id` luôn nằm trong metadata để đối chiếu retrieval hit.

`age_days` = `run_date.date() - published`, tính bằng pandas với `errors="coerce"`. Ngày hỏng giữ `NaT`/`NaN` thay vì sentinel `-1`, vì `-1` sẽ trượt qua điều kiện `age_days <= 180` và biến một record hỏng thành record "rất mới".

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10 (`samples: 10` trong cả ba file metrics)                 |
| Các`question_type`                    | `factual` (7 câu: tác giả, ngày xuất bản), `summary` (3 câu)                  |
| Ground-truth document ID                 | `ground_truth_doc_ids` là DOI lấy trực tiếp từ cleaned dataset; retrieval hit khi ít nhất một `paper_id` trong top-k nằm trong danh sách này     |
| Embedding model                          | Local `sentence-transformers/all-MiniLM-L6-v2` (384 chiều)                  |
| Vector store/collection                  | ChromaDB persistent tại `data/chroma`; collection `papers-baseline`, `papers-corrupted`, `papers-repaired`                 |
| Retrieval`top_k`                       | 4                   |
| LLM provider/model                       | `openai` / `gpt-4o-mini` (dùng cho LLM judge)                   |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` — 10 câu, được đóng băng và load lại ở cả `phase1.py` lẫn `corruption_flow.py`; chỉ sinh lại khi bật `REFRESH_TEST_SET=true` |

Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:

Vì test set là biến kiểm soát duy nhất khiến phép so sánh có ý nghĩa. Cả ba lần đánh giá đều dùng cùng bộ 10 câu hỏi, cùng embedding model, cùng LLM judge, cùng `top_k=4` và cùng code — thứ duy nhất thay đổi là dữ liệu đầu vào. Nhờ vậy khi `retrieval_hit_rate` tụt 1.000 → 0.400 thì nguyên nhân chắc chắn nằm ở corruption, không thể đổ cho "câu hỏi khó hơn" hay "cấu hình khác". Nếu mỗi trạng thái dùng test set riêng thì độ khó thay đổi theo và mọi delta đều không quy được về đâu. Test set cũng được sinh bằng template cứng thay vì nhờ LLM, để nếu phải tạo lại thì kết quả vẫn tái lập được và không có nguy cơ hallucinate ground truth.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | `crossref_response.json` (24 `message.items`) và `crossref_records.json` (24 `PaperRecord`, round-trip load thành công) |
| Cleaned dataset          | `data/clean/`                        | Có | `papers_clean.csv|json` 24 dòng × 11 cột; kèm bản `_corrupted` (23 dòng) và `_repaired` (24 dòng) |
| Embedding manifest/index | `data/embeddings/`                   | Có | 3 manifest ứng với 3 collection; `embedding_model: sentence-transformers/all-MiniLM-L6-v2`, `persist_path` tương đối `data\chroma`; DB nằm ở `data/chroma/` |
| Evaluation set           | `data/eval/`                         | Có | `test_set.json` — 10 câu frozen, dùng chung cho cả ba trạng thái |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Kèm `baseline_answers.json` để truy vết từng câu; `judge.reasoning` do model sinh, 0/10 câu dùng fallback heuristic |
| Quality/freshness        | `data/quality/`                      | Có | 3 file quality + 3 file freshness. Thư mục `data/quality/gx/` rỗng vì nhóm tự viết check thay cho Great Expectations |
| Agent demo               | `data/results/agent_demo_answers.json` | Có | 3 câu đầu của frozen test set chạy qua `build_agent`/`run_agent_question` (agent có tool `semantic_search_papers` và `lookup_paper`); 3/3 câu có câu trả lời từ LLM, trường `error` đều `null` |
| Baseline report          | `data/reports/phase1_report.md`      | Có | Sinh lúc 2026-08-06 14:52 UTC, số liệu khớp `baseline_metrics.json` và `quality_baseline.json` |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     1.000 | 10/10 câu lấy được đúng tài liệu chứa đáp án trong top-4 — corpus 24 tài liệu, chủ đề tách bạch nên retrieval không bị nhiễu  |
| `mean_token_f1`      |     1.000 | Trùng khít ground truth. Nguyên nhân: `_extract_answer` trích nguyên văn từ metadata (`authors_joined`, `published`, câu đầu của summary) đúng bằng nguồn dựng ground truth, nên F1 bão hòa ở 1.0 theo thiết kế chứ không phải rò rỉ đáp án                           |
| `judge_accuracy`     |     1.000 | LLM judge (`gpt-4o-mini`) chấm cả 10 câu là đúng; đã xác minh không có câu nào rơi về fallback heuristic                           |
| `mean_judge_score`   |     5 | Điểm tối đa ở toàn bộ 10 câu, tạo trần rõ ràng để đo mức sụt sau corruption                           |
| Ragas        | `answer_relevancy` 0.232, `context_precision` 0.700, `context_recall` 0.700, `faithfulness` 0.700 | Chạy với `RUN_RAGAS=1`, judge LLM `gpt-4o-mini` và embedding MiniLM local. Ba metric context/faithfulness ở mức 0.700 tạo mốc đối chứng độc lập với token F1. `answer_relevancy` thấp vì câu trả lời là chuỗi trích nguyên văn rất ngắn (tên tác giả, ngày) chứ không phải câu văn hoàn chỉnh |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `row_count_min` | Completeness (tập dữ liệu) | ≥ 15 dòng | PASS — 24 dòng | `data/quality/quality_baseline.json` |
| `paper_id_not_null` | Completeness | Mọi dòng có `paper_id` không null/rỗng | PASS — 0 dòng lỗi | `data/quality/quality_baseline.json` |
| `paper_id_unique` | Uniqueness | `paper_id` duy nhất toàn bảng | PASS — 24 giá trị duy nhất / 24 dòng | `data/quality/quality_baseline.json` |
| `title_not_null` | Completeness | Mọi dòng có `title` không null/rỗng | PASS — 0 dòng lỗi | `data/quality/quality_baseline.json` |
| `title_min_length` | Validity | `len(title)` ≥ 10 ký tự | PASS — độ dài nhỏ nhất 44 | `data/quality/quality_baseline.json` |
| `published_not_null` | Completeness | Mọi dòng có `published` | PASS — 0 dòng lỗi | `data/quality/quality_baseline.json` |
| `summary_min_length` | Validity/Completeness | `summary_chars` ≥ 100 (bằng đúng rule drop của cleaning) | PASS — nhỏ nhất 210 | `data/quality/quality_baseline.json` |
| `text_for_embedding_not_null` | Completeness | Cột đưa vào embedding không rỗng | PASS — 0 dòng lỗi | `data/quality/quality_baseline.json` |
| `freshness_age` | Timeliness | Mọi dòng có `age_days` ≤ `settings.freshness_threshold_days` (180) | PASS — lớn nhất 178, 0 dòng stale | `data/quality/quality_baseline.json`, `phase1_report.md` mục 3 |

Ghi chú: nhóm cố ý **không** đặt check trên `categories_joined`. Kiểm tra raw cho thấy Crossref không trả `subject` cho 24/24 record trong tập này, nên một check completeness trên cột đó sẽ làm baseline FAIL vĩnh viễn vì lý do không liên quan tới chất lượng pipeline. Ngưỡng `summary_min_length` cũng được đặt bằng đúng rule drop 100 ký tự của `cleaning.py` để tránh FAIL oan.

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Cleaned dataset, ngay trước bước indexing (`build_freshness_report` trên cột `age_days`/`published`) |
| Timestamp mới nhất       | `latest_published` = 2026-07-17 (`oldest_published` = 2026-02-09)                         |
| Ngưỡng freshness         | 180 ngày (`freshness_threshold_days`)                         |
| Trạng thái baseline      | Fresh (`is_fresh: true`, `stale_rows: 0` / 24 dòng)               |
| Lý do                     | `age_days` lớn nhất là 178 < 180, nên không dòng nào stale. Con số 178 sát ngưỡng là hệ quả trực tiếp của filter `from-pub-date` được tính từ chính `freshness_threshold_days` — cửa sổ lấy dữ liệu và cửa sổ giám sát dùng chung một hằng số nên luôn nhất quán |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| `drop_latest_record` | Xóa 2 record mới nhất khỏi cleaned DataFrame (`10.47861/tuturan.v4i3.2655` 2026-07-17, `10.61404/mutiara.v4i3.530` 2026-07-15) — cả hai nằm trong `ground_truth_doc_ids` | 2 | `total_rows` giảm, `latest_published` lùi lại | `total_rows` 24 → 23; `latest_published` 2026-07-17 → 2026-07-13; q1–q6 trượt retrieval → `retrieval_hit_rate` 1.000 → 0.400 (`corrupted_answers.json`) | Clean lại từ `data/raw/crossref_records.json` |
| `blank_summary` | Xóa rỗng `summary` của `10.30640/trending.v4i3.7273`, cập nhật `summary_chars` 1450 → 0 và dựng lại `text_for_embedding` | 1 | `summary_min_length` FAIL | `summary_min_length` FAIL, 1 dòng lỗi, `summary_chars` nhỏ nhất = 0. Câu q9 vẫn `retrieval_hit = True` nhưng `token_f1 = 0` — phá khâu trả lời chứ không phá khâu tìm | Clean lại từ raw snapshot |
| `stale_publication` | Đặt `published` của `10.55656/jpe.v6i2.672` từ 2026-07-01 về `2000-01-01`, `age_days` 36 → 9999 | 1 | `freshness_age` FAIL, `is_fresh: false` | `freshness_age` FAIL (1 dòng stale, `age_days` lớn nhất 9999); `oldest_published` 2026-02-09 → 2000-01-01; `is_fresh` true → false | Clean lại từ raw snapshot |
| `truncate_title` | Cắt `title` của `10.57250/ajpp.v5i2.3033` còn `"Fenom"` (5 ký tự) và dựng lại `text_for_embedding` | 1 | `title_min_length` FAIL | `title_min_length` FAIL, độ dài nhỏ nhất 44 → 5 | Clean lại từ raw snapshot |
| `duplicate_record` | Chèn thêm một bản sao của `10.61253/abdicendekia.v5i2.917` | 1 (thêm dòng) | `paper_id_unique` FAIL | `paper_id_unique` FAIL — 22 giá trị duy nhất / 23 dòng | Clean lại từ raw snapshot (`drop_duplicates` loại bản sao) |
| `embedding_noise` | Chèn 20 lần chuỗi `zzz_noise_token corrupted_context irrelevant_payload` vào đầu `text_for_embedding` của `10.61253/abdicendekia.v5i2.917` và cắt cụt phần nội dung thật | 1 | Không check nào bắt được (đây là điểm mù đã biết) | Đúng như dự đoán: 9/9 check không đổi vì `text_for_embedding` vẫn khác rỗng; chỉ lộ ra gián tiếp qua metrics RAG | Clean lại từ raw snapshot |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log có 12 entry, mỗi entry ghi `paper_id`, `scenario`, `field`, `before`, `after`. Đủ 6 loại corruption cộng 3 entry `rebuild_embedding_text` ghi lại việc cập nhật trường dẫn xuất sau khi trường nguồn đổi. Với `drop_latest_record` và `duplicate_record`, log lưu nguyên bản ghi ở `before`/`after` nên có thể tái dựng chính xác thay đổi. Tham số cụ thể (số lần lặp chuỗi nhiễu, số ký tự cắt tiêu đề) không được ghi thành field riêng mà phải suy ra từ cặp `before`/`after` — đây là điểm có thể cải thiện.

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

Repair **không** sửa trực tiếp trên corrupted DataFrame và cũng **không** gọi lại Crossref. Nhóm load `data/raw/crossref_records.json` — snapshot bất biến do TV1 lưu ở bước ingestion — rồi chạy lại đúng `build_clean_dataframe` với cùng `run_date`, sau đó re-index vào collection `papers-repaired` và re-evaluate. Hai lý do:

Thứ nhất, sửa từng dòng hỏng chỉ vá được những lỗi mình đã biết; kịch bản như `embedding_noise` không bị check nào bắt sẽ sót lại. Dựng lại toàn bộ từ nguồn thì mọi corruption đều biến mất theo cùng một cơ chế, không phụ thuộc vào việc nhóm có phát hiện ra chúng hay không.

Thứ hai, nếu fetch lại API thì Crossref sẽ trả kết quả khác (bài mới được index, cửa sổ `from-pub-date` trượt theo ngày chạy), population thay đổi và phép so sánh với baseline mất hiệu lực. Bằng chứng repair là phục hồi thật chứ không phải che lỗi: `papers_clean_repaired.csv` có kích thước và nội dung trùng khít `papers_clean.csv` (92.853 byte), quality trở lại 0/9 FAIL và cả bốn metric RAG về đúng giá trị baseline chứ không chỉ "tốt hơn corrupted".

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |      1.000 |       0.400 |      1.000 |                      −0.600 |             100% (+0.600) | Toàn bộ mức sụt đến từ 2 tài liệu bị xóa: q1–q6 trượt, q7–q10 vẫn hit |
| `mean_token_f1`        |      1.000 |       0.310 |      1.000 |                      −0.690 |             100% (+0.690) | Sụt sâu nhất vì gánh cả hai loại hỏng: retrieval trượt (q1–q6) và câu trả lời rỗng do mất summary (q9, `token_f1 = 0` dù hit) |
| `judge_accuracy`       |      1.000 |       0.300 |      1.000 |                      −0.700 |             100% (+0.700) | Thấp hơn `retrieval_hit_rate` (0.400) đúng một câu: q9 vẫn hit nhưng summary rỗng nên judge chấm sai — lấy đúng tài liệu không đảm bảo trả lời đúng |
| `mean_judge_score`     |      5 |       2.500 |      5 |                      −2.500 |             100% (+2.500) | Judge cho 1 điểm ở q1/q3/q4/q5, 2 điểm ở q2/q6 và q9 (hit nhưng rỗng nội dung), giữ 5 ở q7/q8/q10 — chấm có phân biệt chứ không phạt đồng loạt |
| `context_precision` (Ragas) |      0.700 |       0.200 |      0.700 |                      −0.500 |             100% (+0.500) | Nguồn độc lập xác nhận kết luận về retrieval: sụt mạnh nhất trong bốn metric Ragas, cùng chiều với `retrieval_hit_rate` |
| `context_recall` (Ragas) |      0.700 |       0.350 |      0.700 |                      −0.350 |             100% (+0.350) | Phản ánh việc 2 tài liệu bị xóa khỏi index nên context lấy về không còn phủ được ground truth |
| `faithfulness` (Ragas) |      0.700 |       0.444 |      0.700 |                      −0.256 |             100% (+0.256) | Sụt nhẹ hơn hai metric context vì câu trả lời vẫn bám vào context lấy được, dù context đó là tài liệu sai |
| `answer_relevancy` (Ragas) |      0.232 |       0.158 |      0.238 |                      −0.074 |             102% (+0.080) | Đúng chiều nhưng biên độ nhỏ nhất trong bốn metric Ragas; repaired nhỉnh hơn baseline 0.006 do dao động của LLM chứ không phải cải thiện thật — nhóm không dùng metric này để kết luận (xem mục 12) |
| Quality checks pass/fail |      0/9 FAIL (PASS) |       4/9 FAIL (FAIL) |      0/9 FAIL (PASS) |                      +4 check FAIL |             100% (về 0 FAIL) | FAIL đúng 4 check ứng với 4 kịch bản: `paper_id_unique`, `title_min_length`, `summary_min_length`, `freshness_age`. 5 check còn lại giữ PASS ở cả ba cột → corruption có tính chọn lọc |
| Freshness status         |      Fresh (`stale_rows` 0 / 24 dòng) |       Stale (`stale_rows` 1 / 23 dòng) |      Fresh (`stale_rows` 0 / 24 dòng) |                      `is_fresh` true → false; `oldest_published` 2026-02-09 → 2000-01-01 |             100% (`is_fresh` về true, `oldest_published` về 2026-02-09) | Tín hiệu trực quan nhất của stale injection; `latest_published` cũng lùi 2026-07-17 → 2026-07-13 do 2 record mới nhất bị xóa |

Nêu ít nhất hai kết luận có quan hệ nhân quả được hỗ trợ bởi artifacts:

1. Corruption trên `data/clean/papers_clean_corrupted.csv` (xóa 2 record mới nhất, xóa rỗng 1 summary, làm cũ 1 ngày xuất bản, nhân bản 1 `paper_id`, cắt cụt 1 tiêu đề) → `quality_corrupted.json` chuyển từ 0 lên 4 check FAIL, `freshness_corrupted.json` có `is_fresh: false`, `stale_rows: 1`, `total_rows` 24 → 23 → `corrupted_metrics.json` cho `retrieval_hit_rate` 1.000 → 0.400, `mean_token_f1` 1.000 → 0.310, `judge_accuracy` 1.000 → 0.300, `mean_judge_score` 5 → 2.500, và Ragas `context_precision` 0.700 → 0.200, `context_recall` 0.700 → 0.350, `faithfulness` 0.700 → 0.444.
2. Repair dựng lại từ `data/raw/crossref_records.json` qua đúng `build_clean_dataframe` → `quality_repaired.json` về 0 check FAIL, `freshness_repaired.json` về `is_fresh: true` với `stale_rows: 0` và 24 dòng → `repaired_metrics.json` cho cả bốn metric RAG trở lại **đúng** giá trị baseline (1.000 / 1.000 / 1.000 / 5). Cả hai lớp tín hiệu cùng phục hồi thì mới kết luận repair thành công.

Không kết luận corruption “có tác động” nếu số liệu không cho thấy thay đổi. Nếu kết quả khác kỳ vọng, mô tả giả thuyết và cách nhóm đã kiểm tra.

Ba kết quả khác kỳ vọng và cách nhóm kiểm tra:

- **`mean_token_f1` baseline = 1.000** trái với gợi ý rằng Token F1 "không bao giờ đạt 1.0". Giả thuyết ban đầu: test set rò rỉ đáp án hoặc metric tính sai. Kiểm tra bằng cách đọc `retrieval/qa.py` và thấy `_extract_answer` **không gọi LLM** mà trích nguyên văn từ metadata, trong khi ground truth cũng lấy từ chính các trường đó — hai chuỗi giống hệt nhau nên F1 = 1.0 là đúng theo thiết kế. Mệnh đề "F1 < 1.0" chỉ đúng khi câu trả lời do LLM sinh.
- **`embedding_noise` không bị check nào bắt.** Sau khi chèn nhiễu, `text_for_embedding` vẫn khác rỗng nên `text_for_embedding_not_null` vẫn PASS. Xác nhận bằng `quality_corrupted.json`: đúng 4 check FAIL, không có check nào ứng với kịch bản này.
- **`blank_summary` không bị `text_for_embedding_not_null` bắt** mà bị `summary_min_length` bắt, vì chuỗi dựng lại vẫn còn phần `Title:` và `Authors:`. Đây là bằng chứng cho thấy một check đơn lẻ không đủ, cần nhiều rule phủ chồng lên nhau.

## 11. Vấn đề tích hợp quan trọng

Mô tả một vấn đề phát sinh khi ghép các module trong pipeline và cách nhóm xử lý:

- **Triệu chứng:** Ở lần ghép baseline đầu tiên, `retrieval_hit_rate` đạt 1.0 nhưng `mean_token_f1` chỉ 0.1106 và `judge_accuracy` 0.3333. Kiểm tra `data/results/baseline_answers.json` thấy các câu hỏi về tác giả và ngày xuất bản lại nhận về đoạn summary — retrieval đúng tài liệu nhưng trích sai trường.
- **Nguyên nhân:** Test set do TV2 sinh ra bằng câu hỏi tiếng Việt, trong khi `retrieval/qa.py` nhận diện intent bằng mẫu tiếng Anh. Không câu nào khớp mẫu "who authored" / "when was … published" nên parser rơi về nhánh mặc định và luôn trả summary. Đây là lỗi ở **contract giữa hai module** (evaluation set ↔ intent parser), không phải lỗi embedding hay index — điều này được khẳng định bởi việc `retrieval_hit_rate` vẫn hoàn hảo 1.0.
- **Cách xử lý:** Chuyển toàn bộ câu hỏi sang tiếng Anh để khớp mẫu của parser, giới hạn còn 10 samples và dùng `first_sentence(summary)` làm ground truth cho nhóm câu hỏi `summary`. Sinh lại test set bằng `REFRESH_TEST_SET=true`, sau đó đóng băng lại file cho cả ba trạng thái.
- **Cách xác minh:** Chạy lại `python script/run_phase1.py` và đối chiếu `data/results/baseline_metrics.json`: `mean_token_f1` từ 0.1106 lên 1.000, `judge_accuracy` từ 0.3333 lên 1.000, `retrieval_hit_rate` giữ 1.000. Đọc lại `baseline_answers.json` xác nhận câu hỏi tác giả trả về đúng chuỗi `authors_joined`.

Một vấn đề tích hợp thứ hai đã xử lý: `judge.reasoning` trong `baseline_answers.json` ghi `"Fallback heuristic judge used because the LLM evaluator was unavailable."` ở toàn bộ các câu, dù pipeline chạy không lỗi. Nguyên nhân là `.env` đặt `LLM_PROVIDER=gemini` trong khi `GOOGLE_API_KEY` để trống, còn `metrics._judge_answer` bắt mọi exception và **âm thầm** rơi về heuristic tính từ token F1. Sửa `.env` thành `LLM_PROVIDER=openai` / `LLM_MODEL=gpt-4o-mini` cho khớp credential thực có; xác minh bằng cách đếm số câu chứa chuỗi `"Fallback heuristic"` trong `baseline_answers.json` — kết quả 0/10.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| `answer_relevancy` của Ragas phân biệt yếu giữa ba trạng thái (0.232 → 0.158 → 0.238, delta chỉ −0.074) trong khi `context_precision` sụt tới −0.500 | Một trong bốn metric Ragas không đóng góp tín hiệu; nếu chỉ nhìn `answer_relevancy` sẽ kết luận nhầm là corruption không ảnh hưởng | Nguyên nhân giả định: `_extract_answer` trả về chuỗi trích nguyên văn rất ngắn nên phần sinh câu hỏi ngược của `answer_relevancy` không có đủ ngữ cảnh. Kiểm chứng bằng cách thay bằng generation thật qua LLM rồi đo lại; thành công khi `answer_relevancy` baseline vượt 0.6 và delta corrupted đạt ít nhất −0.2 |
| Kịch bản `embedding_noise` không bị bất kỳ quality check nào bắt | Một lớp corruption chỉ lộ ra gián tiếp qua metrics RAG; nếu chỉ nhìn `quality_*.json` sẽ kết luận nhầm là dữ liệu sạch | Thêm check đo tỉ lệ ký tự không phải chữ/số và tỉ lệ token lặp trên `text_for_embedding`, cảnh báo khi lệch khỏi phân phối baseline. Thành công khi số check FAIL ở corrupted tăng 4 → 5, check mới trỏ đúng `paper_id` trong `corruption_log.json`, còn baseline và repaired vẫn 0 FAIL |
| Sáu kịch bản corruption được áp dụng đồng thời trong một lần chạy | Không tách được đóng góp riêng của từng kịch bản vào mức sụt metrics; kết luận "`drop_latest_record` ảnh hưởng mạnh nhất" dựa trên phân tích per-question chứ chưa phải ablation có kiểm soát | Chạy ablation: mỗi lần chỉ bật một kịch bản, giữ nguyên test set và cấu hình, ghi metrics riêng. Thành công khi tổng mức sụt của các lần chạy đơn lẻ giải thích được mức sụt của lần chạy gộp |
| `mean_token_f1` baseline bão hòa ở 1.000 vì `_extract_answer` trích nguyên văn metadata thay vì để LLM sinh câu trả lời | Metric mất độ phân giải ở đầu trên; không đo được chất lượng diễn đạt, chỉ đo được chất lượng dữ liệu | Thay `_extract_answer` bằng generation thật qua LLM và đo lại. Thành công khi baseline F1 rơi vào khoảng < 1.0 nhưng vẫn cao rõ rệt so với corrupted, tức metric lấy lại được dải phân biệt |
| Query nguồn có lỗi chính tả `artifical intelligence`; Crossref không trả `subject` cho 24/24 record | Tập dữ liệu lệch về các bài có lỗi chính tả trong tiêu đề (phần lớn là tạp chí tiếng Indonesia) và không có trường chủ đề để làm giàu metadata | Crawl thêm một tập với query `artificial intelligence` cùng filter, so tỉ lệ title/abstract liên quan giữa hai tập để đo tác động của lỗi chính tả lên source quality |
| Chưa có unit/integration test tự động; xác minh hiện dựa vào chạy tay hai pipeline và đọc artifact | Hồi quy có thể lọt qua khi ai đó sửa parser, rule cleaning hoặc ngưỡng check | Thêm `pytest` với fixture nhỏ và mock OpenAI API: kiểm tra parser với payload thiếu field, retry `503`, round-trip save/load, corruption không mutate input, hash test set không đổi, corrupted metrics phải giảm và repaired phải phục hồi ≥ 95% |
| Trên máy TV1, Windows Application Control chặn DLL native của pandas (`ImportError: DLL load failed while importing base`) | Một thành viên không chạy được cleaning và pipeline end-to-end trên máy cá nhân; phải xác minh phần ingestion riêng bằng payload mô phỏng và PowerShell | Dùng môi trường Python được Application Control cho phép hoặc xin whitelist binary của pandas, sau đó chạy lại cả hai pipeline trên máy đó và đối chiếu artifact với kết quả trong repo |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
