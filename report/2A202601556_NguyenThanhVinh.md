# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Thành Vinh |
| MSSV | 2A202601556 |
| Khóa/Lớp | K4 |
| Tên nhóm | ChillGuys |
| Vai trò chính | Corruption & Integration Owner (Role 4) |
| Repository | https://github.com/hason0510/K4-Day10-2A202601454-BeNguyenHaSon |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Data corruption | src/ingestion/corruption.py — corrupt_clean_dataframe | Clean DataFrame | Corrupted DataFrame, corruption_log.json | Hoàn thành |
| Baseline orchestration | src/pipelines/phase1.py — main | Raw records và settings | Clean data, index, test set, baseline metrics/report | Hoàn thành |
| Corruption/repair orchestration | src/pipelines/corruption_flow.py — main | Baseline artifacts, frozen test set | Corrupted/repaired metrics, quality và comparison report | Hoàn thành |
| Bằng chứng tích hợp | data/results, data/quality, data/reports | Output các module | Bộ artifact PASS → FAIL → PASS | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Đồng bộ test set với QA | evaluation/testset.py | Câu hỏi tiếng Anh, đúng 10 samples, summary ground truth khớp QA; baseline F1 từ 0.111 lên 1.000 |
| Cấu hình API embedding | retrieval/embeddings.py, retrieval/index.py, core/config.py | Dùng OpenAI text-embedding-3-small thay cho model local |
| Reproducibility và bảo mật | .gitignore, embedding manifests | Không commit .env/Chroma DB; manifest dùng đường dẫn tương đối |

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/artifact | Kết quả | Cách xác minh |
| --- | --- | --- | --- |
| Ghép baseline | src/pipelines/phase1.py | 24 clean records, 10 samples, quality PASS | python script/run_phase1.py |
| Tạo corruption xác định | src/ingestion/corruption.py | 12 log entries; corrupted còn 23 rows | data/results/corruption_log.json |
| Đánh giá và repair | src/pipelines/corruption_flow.py | Metrics giảm ở corrupted và phục hồi ở repaired | python script/run_corruption_flow.py |
| Sinh báo cáo | data/reports/corruption_report.md | So sánh ba trạng thái bằng metrics và observability | Đối chiếu JSON artifacts |
| Bàn giao | Commit 0c4c7da | Đã push lên origin/main | git show 0c4c7da |

Output tiêu biểu là data/reports/corruption_report.md: retrieval hit rate giảm 1.000 → 0.400 và phục hồi về 1.000; quality chuyển PASS → FAIL → PASS.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Tôi chịu trách nhiệm biến các module riêng lẻ thành hai pipeline chạy được: baseline và corruption/repair. Thí nghiệm phải giữ nguyên test set, model và top_k để chênh lệch metrics chỉ đến từ thay đổi dữ liệu.

### Cách triển khai

Baseline ưu tiên raw snapshot để tái lập kết quả; chỉ fetch lại khi REFRESH_SOURCE được bật. Sau cleaning, pipeline lưu CSV/JSON, tạo OpenAI embeddings, build Chroma index, tạo hoặc load test set, chạy evaluation, quality/freshness và sinh report.

Corruption không dùng random và không mutate input. Do test set lấy các paper đầu bảng, hàm tác động có chủ đích vào nhóm này: drop hai latest records, blank summary, stale publication date, embedding noise, truncate title và duplicate DOI. Log lưu paper_id, scenario, field, before và after. Các trường dẫn xuất summary_chars, age_days và text_for_embedding cũng được cập nhật.

Repair không gọi Crossref lại mà clean đúng raw snapshot đã dùng cho baseline. Cách này giữ nguyên population và chứng minh khả năng phục hồi từ nguồn tin cậy.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | list[PaperRecord], clean DataFrame theo schema chung, frozen test_set.json |
| Output | Clean/corrupted/repaired CSV/JSON, embedding manifests, metrics/answers, quality/freshness và Markdown reports |
| Module phụ thuộc | crossref, cleaning, testset, metrics, quality, reporting, retrieval.index |
| Module sử dụng output | Chroma index, evaluator và report generator |
| Điều kiện lỗi | Thiếu artifact baseline, DataFrame rỗng/thiếu cột, dưới 6 rows, thiếu OpenAI credential |

### Cách xác minh

    python -m pip install -e .
    python script/run_phase1.py
    python script/run_corruption_flow.py
    python -m compileall -q src script
    git diff --check

- **Mong đợi:** Baseline PASS, corrupted FAIL và metrics giảm, repaired phục hồi.
- **Thực tế:** Hai flow exit code 0; baseline và repaired đạt hit/F1/judge accuracy 1.000, corrupted còn 0.400/0.310/0.400.
- **Artifact:** data/results/*.json, data/quality/*.json, data/reports/*.md; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần repair nhưng vẫn bảo đảm so sánh công bằng.
- **Phương án cân nhắc:** Fetch Crossref lại; sửa trực tiếp corrupted rows; hoặc clean lại raw snapshot.
- **Phương án chọn:** Clean lại data/raw/crossref_records.json.
- **Lý do:** Crossref có thể thay đổi theo thời gian; sửa trực tiếp dễ bỏ sót lỗi. Raw snapshot bảo đảm data lineage và reproducibility.
- **Bằng chứng:** Repaired trở lại 24 rows, mọi quality check PASS và bốn metrics bằng baseline: 1.000, 1.000, 1.000, 5.000.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Baseline ban đầu có retrieval_hit_rate 1.0 nhưng mean_token_f1 0.1106 và judge_accuracy 0.3333; câu hỏi tác giả/ngày nhận summary.
- **Tái hiện:** Chạy phase1 rồi kiểm tra data/results/baseline_answers.json.
- **Nguyên nhân gốc:** Test set dùng tiếng Việt trong khi qa.py nhận diện intent bằng mẫu tiếng Anh.
- **Cách xử lý:** Chuyển câu hỏi sang tiếng Anh, giới hạn 10 samples và dùng first_sentence(summary) làm ground truth.
- **Xác minh:** Tạo lại test set với REFRESH_TEST_SET=true; retrieval hit rate, F1 và judge accuracy đều đạt 1.000.
- **Điều học được:** Retrieval đúng không đồng nghĩa answer đúng; evaluation contract phải khớp intent parser và ground truth.

## 7. Hiểu biết về luồng end-to-end

1. Crossref response được parse thành PaperRecord và lưu raw snapshot. Cleaning chuẩn hóa dữ liệu, tính age_days và tạo text_for_embedding; OpenAI embedding sinh vector cho ChromaDB.
2. Evaluation set chứa question, ground truth và DOI trong ground_truth_doc_ids. DOI retrieved dùng tính hit rate; answer dùng token F1 và LLM judge.
3. Quality checks đo completeness, uniqueness và validity; freshness đo tuổi dữ liệu, latest/oldest date và stale rows.
4. Dùng cùng test set giữ nguyên độ khó, giúp quy thay đổi metrics cho corruption/repair.
5. Repair thành công khi dữ liệu tái tạo từ raw có quality/freshness PASS và metrics trở về baseline. Lần chạy này phục hồi hoàn toàn.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| retrieval_hit_rate | 1.000 | 0.400 | 1.000 | Mất 60% retrieval hits rồi phục hồi |
| mean_token_f1 | 1.000 | 0.310 | 1.000 | Context lỗi làm answer giảm mạnh |
| judge_accuracy | 1.000 | 0.400 | 1.000 | Chỉ 40% answers corrupted đúng |
| mean_judge_score | 5.000 | 2.800 | 5.000 | Giảm 2.2 điểm rồi phục hồi |
| Quality checks | PASS (0 fail) | FAIL (4 fail) | PASS (0 fail) | Bắt duplicate, title ngắn, summary rỗng, stale age |
| Freshness | Fresh | Stale (1 row) | Fresh | age_days 9999 được phát hiện |

### Kết luận từ số liệu

1. Drop records, blank summary, stale date và duplicate DOI → bốn quality checks FAIL và freshness Stale → hit rate 1.000 → 0.400, F1 1.000 → 0.310, judge accuracy 1.000 → 0.400.
2. Clean lại raw snapshot → 24 rows, quality PASS và Fresh → toàn bộ metrics phục hồi về baseline.

Drop hai paper thuộc ground_truth_doc_ids ảnh hưởng rõ nhất vì source documents không còn trong index. Kết quả khác kỳ vọng là baseline đầu tiên có answer metrics thấp dù retrieval hoàn hảo; answer artifact xác nhận nguyên nhân là mismatch ngôn ngữ, không phải embedding.

## 9. Điều học được và hướng cải thiện

1. Raw snapshot và orchestration xác định là nền tảng của reproducibility.
2. Observability cần kết hợp quality, freshness và RAG metrics.
3. Một số data corruption nhắm đúng evaluated documents có thể làm retrieval và answer accuracy giảm 60%.

Nếu có thêm thời gian, tôi sẽ thêm unit/integration tests với fixture nhỏ và mock OpenAI API; kiểm tra input không mutate, hash test set không đổi, corrupted metrics phải giảm và repaired phải phục hồi ít nhất 95%.

## 10. Cam kết của thành viên

- [x] Nội dung phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end.
- [x] Mọi kết luận đều có artifact hoặc metric đối chiếu.
- [x] Tôi không ghi thành công cho phần chưa kiểm chứng.
- [x] Báo cáo không chứa .env, API key, token hoặc secret.
- [x] Báo cáo không sao chép nguyên văn báo cáo nhóm/thành viên khác.

**Họ và tên:** Nguyễn Thành Vinh
**Ngày xác nhận:** 2026-08-06
