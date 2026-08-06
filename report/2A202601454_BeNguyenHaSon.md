# Member Role Report — Day 10: Data Pipeline & Data Observability

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                        |
| ------------------ |-----------------------------------------------------------------|
| Họ và tên       | Bế Nguyễn Hà Sơn                                                |
| MSSV               | 2A202601454                                                     |
| Khóa/Lớp         | K4                                                              |
| Tên nhóm         | ChillGuys                                                       |
| Vai trò chính    | Thành viên 3 — Data Observability Owner                         |
| Repository         | https://github.com/hason0510/K4-Day10-2A202601454-BeNguyenHaSon |
| Ngày hoàn thành | 2026-08-06                                                      |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Data quality checks      | `src/observability/quality.py` — `run_data_quality_checks`, `build_freshness_report`           | Cleaned DataFrame từ `cleaning.build_clean_dataframe` (TV2) và `Settings`          | `data/quality/quality_baseline.json`, `quality_corrupted.json`, `quality_repaired.json`, `freshness_report.json`, `freshness_corrupted.json`, `freshness_repaired.json` | Hoàn thành |
| Markdown reporting      | `src/observability/reporting.py` — `generate_phase1_report`, `generate_corruption_report`           | Dict metrics từ `evaluation.metrics.evaluate_pipeline`, dict quality/freshness của chính tôi          | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Hoàn thành |

Chỉ nhận ownership cho phần bạn trực tiếp thực hiện. Liên hệ rõ phần việc của bạn với đầu vào, đầu ra và các thành viên phụ thuộc vào phần đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Xác định ngưỡng corruption cần đạt để quality check chuyển sang FAIL | TV4 — `src/ingestion/corruption.py` | Thống nhất bảng ánh xạ kịch bản ↔ check; kết quả `quality_corrupted.json` FAIL đúng 4 check dự kiến |
| Kiểm chứng cấu hình LLM provider trước khi chạy evaluate | TV4 — `src/pipelines/phase1.py` | Phát hiện judge đang rơi về fallback heuristic; sau khi sửa `.env`, `baseline_answers.json` có 0/10 câu dùng fallback |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Xây 9 data quality check (completeness, uniqueness, độ dài, freshness) | `src/observability/quality.py` — `run_data_quality_checks` | 3 file quality JSON, mỗi file ghi rõ `passed`, `observed`, `expected`, `failed_rows` từng check | `data/quality/quality_baseline.json` → `all_passed: true`; `quality_corrupted.json` → `all_passed: false`, 4 check FAIL |
| Xây freshness monitoring theo `age_days` | `src/observability/quality.py` — `build_freshness_report` | 3 file freshness JSON đúng 5 field contract | `freshness_report.json` → `is_fresh: true`, `stale_rows: 0`; `freshness_corrupted.json` → `is_fresh: false`, `stale_rows: 1` |
| Sinh báo cáo markdown baseline | `src/observability/reporting.py` — `generate_phase1_report` | `data/reports/phase1_report.md` | Mở file, đối chiếu số với `data/results/baseline_metrics.json` |
| Sinh báo cáo so sánh 3 trạng thái | `src/observability/reporting.py` — `generate_corruption_report` | `data/reports/corruption_report.md` với 3 bảng: metrics RAG + delta, tín hiệu observability, chi tiết từng check | Mở file, đối chiếu với 3 file `*_metrics.json` và 3 file `quality_*.json` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Bảng "Chi tiết từng quality check (số dòng lỗi)" trong `data/reports/corruption_report.md`. Bảng này chiếu từng check qua cả ba trạng thái, nên chỉ đích danh được kịch bản corruption nào bị lớp giám sát nào bắt: `paper_id_unique` 0 → 1 → 0 (duplicate), `title_min_length` 0 → 1 → 0 (truncate title), `summary_min_length` 0 → 1 → 0 (blank summary), `freshness_age` 0 → 1 → 0 (stale date). Bốn check còn lại giữ nguyên PASS ở cả ba cột, cho thấy corruption có tính chọn lọc chứ không phá bừa.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline RAG không tự báo lỗi khi dữ liệu đầu vào hỏng: index vẫn build được, agent vẫn trả lời, metrics vẫn ra số. Phần của tôi là lớp chốt chặn đặt giữa cleaning và indexing, có nhiệm vụ trả lời hai câu trước khi người dùng nhận câu trả lời sai: dữ liệu có **đủ và sạch** không (quality), và có **đủ mới** không (freshness). Ngoài ra tôi phải biến các tín hiệu đó thành báo cáo đọc được, vì số liệu nằm trong JSON thì không chứng minh được điều gì cho người chấm.

### Cách triển khai

`run_data_quality_checks` chạy 9 rule độc lập trên cleaned DataFrame, mỗi rule trả về một dict thống nhất gồm `name`, `passed`, `observed`, `expected`, `failed_rows`:

1. `row_count_min` — số dòng ≥ 15
2. `paper_id_not_null` — completeness của khóa
3. `paper_id_unique` — uniqueness của khóa
4. `title_not_null` — completeness của tiêu đề
5. `title_min_length` — tiêu đề ≥ 10 ký tự
6. `published_not_null` — có ngày xuất bản
7. `summary_min_length` — summary ≥ 100 ký tự
8. `text_for_embedding_not_null` — cột đưa vào embedding không rỗng
9. `freshness_age` — không dòng nào `age_days` vượt `settings.freshness_threshold_days`

Điểm tôi cân nhắc nhiều nhất là **chọn ngưỡng**. `MIN_SUMMARY_CHARS` phải đúng bằng 100 — bằng chính rule drop của `cleaning.py`. Nếu đặt cao hơn thì baseline sẽ FAIL oan dù dữ liệu hoàn toàn hợp lệ, và C3 yêu cầu baseline PASS toàn bộ. Tương tự, ngưỡng freshness đọc từ `settings.freshness_threshold_days` chứ không hardcode 180, để nếu nhóm đổi cửa sổ lọc `from-pub-date` thì check tự đi theo.

Tôi **cố tình không đặt check nào trên `categories_joined`**. Trước khi viết, tôi kiểm tra dữ liệu thật: Crossref không còn trả trường `subject` cho các publisher trong tập này, nên `categories` rỗng ở cả 24/24 bản ghi. Một check completeness trên cột đó sẽ làm baseline FAIL vĩnh viễn vì lý do không liên quan gì tới chất lượng pipeline.

`build_freshness_report` tách riêng khỏi bộ check vì hai thứ phục vụ mục đích khác nhau: check trả về tín hiệu nhị phân PASS/FAIL để chặn, còn freshness report trả về số liệu mô tả (`latest_published`, `oldest_published`, `stale_rows`, `total_rows`, `is_fresh`) để đưa vào bảng so sánh và thấy được *mức độ* lệch, không chỉ *có lệch hay không*.

Hai hàm trong `reporting.py` thuần trình bày: không tính lại metric, không gọi LLM, không đọc DataFrame. Chúng chỉ nhận dict và dựng bảng markdown. `generate_corruption_report` thêm cột delta so với baseline để người đọc thấy ngay chiều và biên độ thay đổi thay vì phải tự trừ.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Cleaned DataFrame với 11 cột contract (`paper_id`, `title`, `summary`, `published`, `authors_joined`, `categories_joined`, `age_days`, `summary_chars`, `text_for_embedding`, `abs_url`, `pdf_url`); `Settings`; `report_name`; dict metrics từ `evaluate_pipeline`           |
| Output                         | Dict quality `{report_name, generated_at, total_rows, checks[], failed_checks[], all_passed}`; dict freshness 5 field; file JSON trong `data/quality/`; file markdown trong `data/reports/` |
| Module phụ thuộc             | `src/ingestion/cleaning.py` (TV2) cung cấp DataFrame; `src/core/config.py` cung cấp path và ngưỡng; `src/core/utils.py` cung cấp `write_json`/`write_text`                    |
| Module sử dụng output        | `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py` (TV4) gọi cả 4 hàm và truyền dict qua lại                    |
| Điều kiện lỗi cần xử lý | Cột thiếu trong DataFrame → trả về check FAIL kèm thông báo thay vì ném `KeyError` làm sập pipeline; `age_days` không parse được → tính là stale; `published` rỗng → `latest/oldest_published` trả `None` thay vì crash; `ragas` chứa key `error` hoặc `skipped` → in nguyên trạng thái thay vì cố format thành số |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** baseline PASS toàn bộ 9 check và `is_fresh: true`; corrupted FAIL đúng những check tương ứng với kịch bản TV4 gây ra và `is_fresh: false`; repaired quay lại trạng thái giống baseline.
- **Kết quả thực tế:** baseline 0/9 FAIL, `is_fresh: true`, 24 dòng. Corrupted 4/9 FAIL (`paper_id_unique`, `title_min_length`, `summary_min_length`, `freshness_age`), `is_fresh: false`, `stale_rows: 1`, 23 dòng, `oldest_published` tụt về `2000-01-01`. Repaired 0/9 FAIL, `is_fresh: true`, 24 dòng, `oldest_published` trở lại `2026-02-09`. Trùng khít kỳ vọng.
- **Artifact/log:** `data/quality/quality_baseline.json`, `data/quality/quality_corrupted.json`, `data/quality/quality_repaired.json`, `data/quality/freshness_report.json`, `data/quality/freshness_corrupted.json`, `data/quality/freshness_repaired.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`. Không file nào chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `run_data_quality_checks` được gọi 3 lần (baseline, corrupted, repaired), nhưng chữ ký `generate_corruption_report` lại **không** nhận `baseline_quality` và `baseline_freshness` — trong khi C4 đòi bảng so sánh observability đủ 3 cột. Nếu quality report ghi vào một đường dẫn cố định thì lần chạy sau đè lần trước, vừa mất minh chứng vừa không có số cho cột Baseline.
- **Các phương án đã cân nhắc:** (1) Ghi cố định một file, chấp nhận chỉ còn trạng thái cuối cùng. (2) Thêm tham số `baseline_quality`/`baseline_freshness` vào chữ ký `generate_corruption_report`. (3) Đặt tên file theo `report_name` và cho `generate_corruption_report` đọc ngược lại file baseline từ đĩa.
- **Phương án đã chọn:** Phương án 3 — ghi ra `data/quality/quality_<report_name>.json`, và `generate_corruption_report` suy ra đường dẫn baseline từ chính `report_path` để đọc lại.
- **Lý do:** Phương án 1 phá thẳng yêu cầu minh chứng của C4. Phương án 2 tuy sạch hơn về mặt thiết kế nhưng buộc phải đổi chữ ký hàm — mà chữ ký là hợp đồng đã chốt với TV4 từ đầu buổi, đổi giữa chừng thì phía TV4 phải sửa theo và dễ vỡ tích hợp khi cả nhóm đang làm song song. Phương án 3 giữ nguyên contract, đồng thời cho ra 3 file bằng chứng độc lập nộp kèm được. Đổi lại, nó tạo một phụ thuộc ngầm giữa hai hàm — tôi đã ghi rõ ràng buộc này trong docstring để người sau không đổi quy tắc đặt tên file rồi làm hỏng cột Baseline.
- **Bằng chứng quyết định phù hợp:** Cả 3 file `quality_baseline.json`, `quality_corrupted.json`, `quality_repaired.json` cùng tồn tại sau khi chạy hết 2 pipeline; mục 2 và 3 của `corruption_report.md` hiển thị đủ số liệu cột Baseline (0 check FAIL, 24 dòng, `stale_rows` 0) chứ không phải `n/a`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Pipeline chạy trót lọt, `judge_accuracy` vẫn ra số, nhưng trường `judge.reasoning` trong `data/results/baseline_answers.json` ghi `"Fallback heuristic judge used because the LLM evaluator was unavailable."` ở toàn bộ các câu.
- **Lệnh hoặc bước tái hiện:** Chạy `uv run python script/run_phase1.py`, sau đó mở `data/results/baseline_answers.json` và đọc trường `judge.reasoning`.
- **Nguyên nhân gốc:** File `.env` đặt `LLM_PROVIDER=gemini` nhưng `GOOGLE_API_KEY` để trống, trong khi key thực tế nhóm có là của OpenAI. `require_llm_credentials` ném lỗi thiếu credential, nhưng `metrics._judge_answer` bắt mọi exception và **âm thầm** rơi về heuristic tính từ token F1. Vì không có cảnh báo nào nổi lên, lỗi cấu hình trông y hệt một lần chạy thành công.
- **Cách xử lý:** Sửa `.env` thành `LLM_PROVIDER=openai` và `LLM_MODEL=gpt-4o-mini` để khớp với credential đang có. Không commit `.env` (đã nằm trong `.gitignore`).
- **Cách xác minh sau khi sửa:** Chạy lại pipeline rồi đếm số câu có chuỗi `"Fallback heuristic"` trong `baseline_answers.json` — kết quả 0/10. Các trường `judge.reasoning` giờ là văn bản do model sinh, ví dụ *"The model answer exactly matches the reference answer, listing all the authors correctly without any omissions"*.
- **Điều học được:** Fallback im lặng nguy hiểm hơn lỗi ồn ào. Một pipeline "chạy không lỗi" chưa chứng minh được là nó đã thực sự làm việc mình tưởng — đúng tinh thần data observability của bài lab: phải kiểm tra bằng artifact, không tin vào việc chương trình không báo lỗi.

Nếu chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** Không còn tồn đọng; blocker đã được xác minh là đã xử lý xong.
- **Những gì đã loại trừ:** Đã loại trừ giả thuyết lỗi mạng và lỗi hết quota bằng cách gọi thử trực tiếp `build_llm(...).invoke(...)` và nhận được phản hồi hợp lệ từ model.
- **Bước tiếp theo:** Không có; theo dõi lại trường `judge.reasoning` mỗi lần chạy lại pipeline như một bước kiểm tra thường quy.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

**(1)** `crossref.py` gọi `https://api.crossref.org/works` với query/filter/rows đọc từ `Settings`, có retry cho các mã lỗi tạm thời, rồi lưu hai dạng: response HTTP thô vào `crossref_response.json` để audit nguồn, và danh sách `PaperRecord` đã parse phẳng vào `crossref_records.json`. `cleaning.py` nhận list record đó, bỏ bản ghi thiếu tiêu đề hoặc summary quá ngắn, gỡ thẻ XML/HTML, gộp authors và categories thành chuỗi, chuẩn hóa `published` về `YYYY-MM-DD`, tính `age_days`, rồi ghép `text_for_embedding` theo mẫu `Title | Authors | Summary`. `index.py` đưa cột đó qua MiniLM để ra vector 384 chiều và nạp vào collection ChromaDB kèm metadata có `paper_id`.

**(2)** Mỗi câu hỏi trong test set mang theo `ground_truth_doc_ids` — chính là `paper_id` của tài liệu chứa đáp án. Khi evaluate, hệ thống lấy top-k tài liệu và so danh sách `paper_id` thu được với danh sách này: trùng ít nhất một là `retrieval_hit = True`. Đó là thước đo cho **khâu tìm kiếm**. Riêng chất lượng câu trả lời được đo bằng `token_f1` (so trùng từ vựng với `ground_truth`) và bằng LLM judge (so ngữ nghĩa). Hai nhóm chỉ số này tách bạch, nên đọc cùng nhau mới biết lỗi nằm ở khâu nào.

**(3)** Quality check hỏi "dữ liệu có đúng cấu trúc và đầy đủ không" — thiếu khóa, trùng khóa, tiêu đề cụt, summary rỗng. Freshness hỏi "dữ liệu có còn kịp thời không" — dù mọi trường đều hợp lệ, một corpus toàn bài từ năm 2000 vẫn là corpus hỏng đối với hệ thống cần thông tin mới. Bài lab tách hai lớp vì chúng bắt được những kịch bản khác nhau: `blank_summary` chỉ bị quality bắt, `stale_publication` chỉ bị freshness bắt.

**(4)** Vì đó là biến kiểm soát duy nhất khiến so sánh có ý nghĩa. Cả ba lần chạy đều giữ nguyên test set, model, `top_k` và toàn bộ code — chỉ dữ liệu đầu vào thay đổi. Nhờ vậy khi `retrieval_hit_rate` tụt từ 1.0 xuống 0.4 thì nguyên nhân chắc chắn là corruption, không thể đổ cho câu hỏi khác hay cấu hình khác. Nếu test set đổi giữa chừng thì con số chênh lệch không quy được về đâu cả.

**(5)** Dựa trên việc repaired **trùng khít** baseline chứ không chỉ "tốt hơn corrupted". Cụ thể: `retrieval_hit_rate` 0.4 → 1.0, `mean_token_f1` 0.310 → 1.0, `judge_accuracy` 0.4 → 1.0, `mean_judge_score` 2.8 → 5; đồng thời quality từ 4 check FAIL về 0 check FAIL, `is_fresh` từ `false` về `true`, số dòng từ 23 về 24 và `oldest_published` từ `2000-01-01` về `2026-02-09`. Cả hai lớp tín hiệu — metrics RAG và observability — cùng phục hồi thì mới kết luận được là repair thành công.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.000 |       0.400 |      1.000 | Sụt 0.600. Toàn bộ phần sụt đến từ 2 tài liệu bị xóa khỏi index, kéo theo 6/10 câu hỏi trượt.              |
| `mean_token_f1`      |      1.000 |       0.310 |      1.000 | Sụt sâu nhất (0.690) vì gánh cả hai loại hỏng: retrieval trượt và câu trả lời rỗng do mất summary.              |
| `judge_accuracy`     |      1.000 |       0.400 |      1.000 | Trùng đúng `retrieval_hit_rate`, cho thấy khi lấy sai tài liệu thì câu trả lời sai theo, không cứu được.              |
| `mean_judge_score`   |      5 |       2.800 |      5 | Judge cho điểm 1–2 ở các câu trượt và giữ 5 ở 3 câu tài liệu còn nguyên, tức là chấm có phân biệt chứ không phạt đồng loạt.              |
| Quality checks         |      0/9 FAIL |       4/9 FAIL |      0/9 FAIL | FAIL đúng 4 check ứng với 4 kịch bản: duplicate, truncate title, blank summary, stale date.              |
| Freshness status       |      `is_fresh: true`, `stale_rows: 0` |       `is_fresh: false`, `stale_rows: 1` |      `is_fresh: true`, `stale_rows: 0` | `oldest_published` tụt về `2000-01-01` rồi trở lại `2026-02-09` — tín hiệu trực quan nhất của stale injection.              |

### Kết luận từ số liệu

Hoàn thành hai chuỗi nguyên nhân–bằng chứng sau:

1. Corruption trên `papers_clean_corrupted.csv` (xóa 2 bản ghi mới nhất, xóa summary, làm cũ ngày xuất bản, nhân bản `paper_id`, cắt cụt tiêu đề) → quality từ 0/9 lên 4/9 FAIL, `is_fresh` từ `true` sang `false`, `stale_rows` 0 → 1, `total_rows` 24 → 23 → `retrieval_hit_rate` 1.0 → 0.4, `mean_token_f1` 1.0 → 0.310, `judge_accuracy` 1.0 → 0.4, `mean_judge_score` 5 → 2.8.
2. Repair dựng lại từ `data/raw/crossref_records.json` qua đúng logic `build_clean_dataframe` → quality trở lại 0/9 FAIL, `is_fresh` về `true`, `stale_rows` về 0, `total_rows` về 24 → cả 4 metrics RAG phục hồi **hoàn toàn** về đúng giá trị baseline.

Corruption nào ảnh hưởng rõ nhất và vì sao?

`drop_latest_record` — xóa bản ghi khỏi dataset. Một mình nó phá 6/10 câu hỏi (q1–q6) và chiếm toàn bộ mức sụt của `retrieval_hit_rate`. Lý do: các kịch bản khác chỉ làm hỏng **nội dung** của tài liệu, tài liệu vẫn nằm trong index nên vector search vẫn có cơ hội tìm ra; còn xóa hẳn thì không còn gì để tìm, `retrieval_hit` chắc chắn `False`, và mọi chỉ số phía sau sụp theo dây chuyền.

Đối chiếu để thấy rõ sự khác biệt về **cơ chế**: câu q9 bị `blank_summary` vẫn có `retrieval_hit = True` — retrieval tìm đúng tài liệu — nhưng `token_f1 = 0` vì tài liệu đó đã rỗng nội dung nên câu trả lời trả về chuỗi trống. Cùng kéo metrics xuống, nhưng một cái phá khâu tìm, một cái phá khâu trả lời.

Kết quả nào khác với kỳ vọng ban đầu?

Baseline đạt `mean_token_f1 = 1.000` tuyệt đối, trái với gợi ý của đề rằng Token F1 "không bao giờ đạt 1.0". Tôi đặt giả thuyết là test set bị rò rỉ đáp án hoặc metric tính sai, và kiểm tra bằng cách đọc `retrieval/qa.py`. Nguyên nhân thật: `_extract_answer` **không gọi LLM** mà trích nguyên văn từ metadata (`authors_joined`, `published`, câu đầu của summary), trong khi `ground_truth` của test set cũng lấy từ chính các trường đó — hai chuỗi giống hệt nhau nên F1 = 1.0 là đúng theo thiết kế, không phải lỗi. Mệnh đề "F1 < 1.0" chỉ đúng khi câu trả lời do LLM sinh ra: model diễn đạt lại, thêm từ nối, đổi trật tự nên tập token lệch dù nội dung đúng.

Điều bất ngờ thứ hai: `text_for_embedding_not_null` **không** bắt được kịch bản `blank_summary`, vì sau khi xóa summary thì `text_for_embedding` được dựng lại vẫn còn phần `Title:` và `Authors:` nên không rỗng. Kịch bản này được `summary_min_length` bắt thay. Đây là bằng chứng cụ thể cho thấy một check đơn lẻ không đủ và cần nhiều rule phủ chồng lên nhau.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw snapshot không phải bản backup cho vui mà là điều kiện để thí nghiệm tái lập được. Repair từ `crossref_records.json` cho ra dataset trùng khít baseline; nếu fetch lại API thì Crossref trả kết quả khác (bài mới được index, cửa sổ `from-pub-date` trượt theo ngày chạy) và mọi so sánh mất hiệu lực.
2. Ngưỡng của quality check phải bám vào rule đã dùng ở khâu trước, không đặt theo cảm tính. Đặt `MIN_SUMMARY_CHARS` cao hơn rule drop 100 ký tự của cleaning là baseline FAIL oan ngay; đặt check trên `categories_joined` trong khi Crossref không còn trả `subject` cũng vậy. Trước khi viết rule, phải đo dữ liệu thật.
3. Chất lượng dữ liệu tác động lên RAG theo **nhiều đường khác nhau**, và mỗi đường cần một chỉ số riêng để nhìn ra. Xóa tài liệu phá `retrieval_hit_rate`; xóa summary không đụng `retrieval_hit_rate` mà phá `token_f1`. Nếu chỉ theo dõi một chỉ số thì sẽ bỏ sót nguyên một lớp sự cố.

### Nếu có thêm thời gian

Tôi sẽ thêm một check phát hiện nhiễu trên `text_for_embedding` — ví dụ đo tỉ lệ ký tự không phải chữ/số trên tổng độ dài, và cảnh báo khi vượt ngưỡng thống kê so với phân phối của baseline. Lý do: kịch bản `embedding_noise` hiện là kịch bản duy nhất **không** bị bất kỳ check nào của tôi bắt, nó chỉ lộ ra gián tiếp qua metrics RAG. Cách đo cải thiện: chạy lại `corruption_flow.py` và kiểm tra `quality_corrupted.json` — thành công nếu số check FAIL tăng từ 4 lên 5 và check mới trỏ đúng vào những `paper_id` đã bị chèn nhiễu theo `corruption_log.json`, trong khi `quality_baseline.json` và `quality_repaired.json` vẫn giữ 0 FAIL.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Bế Nguyễn Hà Sơn
**Ngày xác nhận:** 2026-08-06
