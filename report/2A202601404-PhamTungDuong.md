# Báo cáo vai trò thành viên — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phạm Tùng Dương |
| MSSV | 2A202601404 |
| Khóa/Lớp | K4 |
| Tên nhóm | ChillGuys |
| Vai trò chính | Source Ingestion Owner |
| Repository | [K4-Day10-2A202601454-BeNguyenHaSon](https://github.com/hason0510/K4-Day10-2A202601454-BeNguyenHaSon) |
| Commit chính | `b25ab6f` — `Implement Crossref source ingestion` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Parse Crossref payload | `src/ingestion/crossref.py` — `parse_crossref_payload` | JSON response có `message.items` | Danh sách `PaperRecord` đã chuẩn hóa | Hoàn thành |
| Fetch và lưu raw data | `src/ingestion/crossref.py` — `fetch_source_records` | `Settings`: query, filter, max results và artifact paths | Raw API response và parsed raw records | Hoàn thành |
| Load raw snapshot | `src/ingestion/crossref.py` — `load_raw_records` | `data/raw/crossref_records.json` | Danh sách `PaperRecord` đã kiểm tra schema | Hoàn thành |

Phạm vi của tôi kết thúc ở raw ingestion. Cleaning, evaluation set, quality checks, corruption và pipeline orchestration thuộc các deliverable khác của nhóm.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất raw data contract | TV2 — Cleaning và Test Set | Chốt tên trường, kiểu dữ liệu, DOI làm `paper_id` ổn định và ngày dạng ISO |
| Kiểm tra dữ liệu bàn giao | TV2 — `src/ingestion/cleaning.py` | Xác định 24/24 record không có Crossref `subject`; khuyến nghị không ghi đè category nguồn và dùng `derived_category` nếu cần |
| Tích hợp Git | Cả nhóm | Đẩy commit `b25ab6f` lên `origin/TV1`; commit đã được merge vào `main` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Gọi Crossref API với retry/backoff | `fetch_source_records` | Request có timeout 30 giây, tối đa 4 lần thử; retry `429/500/502/503/504` | Mock request đầu trả `503`, request thứ hai thành công |
| Parse metadata Crossref | `parse_crossref_payload` | 24/24 items thành `PaperRecord`, không có DOI trùng hoặc record thiếu trường cốt lõi | Đếm và kiểm tra `data/raw/crossref_records.json` |
| Loại HTML/JATS và chuẩn hóa text | `_clean_text`, `_first_text` | Abstract/title sạch và khoảng trắng được chuẩn hóa | Payload mô phỏng chứa JATS lồng nhau và HTML entity |
| Chuẩn hóa tác giả, category và ngày | `_authors_from_item`, `_unique_texts`, `_normalize_date` | Authors/category được deduplicate; ngày trả về `YYYY-MM-DD` | Kiểm tra record mô phỏng và snapshot thật |
| Lưu bằng chứng nguồn | `data/raw/crossref_response.json` | Response nguyên bản từ Crossref | File tồn tại và có 24 `message.items` |
| Lưu dữ liệu raw theo contract | `data/raw/crossref_records.json` | 24 records đọc lại được thành `PaperRecord` | Round-trip `fetch → JSON → load` thành công |

Output cụ thể của phần việc là `data/raw/crossref_records.json`. Lần crawl gần nhất dùng query `artifical intelligence`, filter `from-pub-date:2026-02-07,has-abstract:true` và thu được:

| Chỉ số | Giá trị |
| --- | ---: |
| Items Crossref trả về | 24 |
| Records parse thành công | 24 |
| DOI trùng | 0 |
| Record thiếu DOI/title/summary | 0 |
| Record thiếu authors | 0 |
| Record thiếu ngày xuất bản | 0 |
| Record có PDF URL | 16 |
| Record thiếu categories | 24 |
| Ngày xuất bản cũ nhất | 2026-02-09 |
| Ngày xuất bản mới nhất | 2026-07-17 |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref trả metadata ở dạng JSON không đồng nhất giữa các paper: title là list, abstract có thể chứa JATS/HTML, tác giả có thể thiếu `given` hoặc `family`, ngày có nhiều cấu trúc và PDF URL không phải lúc nào cũng tồn tại. Pipeline cần một raw schema ổn định để cleaning, embedding, evaluation và repair không phụ thuộc trực tiếp vào cấu trúc phức tạp của Crossref.

Phần của tôi giải quyết việc lấy dữ liệu có khả năng retry, lưu response để truy vết và chuyển các item hợp lệ sang `PaperRecord` với document identity ổn định.

### Cách triển khai

1. Gọi endpoint `https://api.crossref.org/works` với query, filter và `rows` lấy từ `Settings`.
2. Đặt timeout 30 giây và retry tối đa 4 lần cho lỗi kết nối hoặc HTTP status tạm thời.
3. Dùng exponential backoff; ưu tiên header `Retry-After` nếu Crossref cung cấp.
4. Lưu nguyên JSON response vào `data/raw/crossref_response.json` để có thể audit và repair.
5. Duyệt `payload["message"]["items"]`, chuẩn hóa DOI thành lowercase và dùng DOI làm `paper_id`.
6. Giải mã HTML entity, loại thẻ JATS/HTML và chuẩn hóa khoảng trắng trong title/abstract.
7. Ghép tên tác giả, loại authors/categories trùng và parse ngày từ `date-parts`, `date-time` hoặc timestamp.
8. Bỏ record thiếu DOI, title hoặc abstract và loại DOI trùng.
9. Lưu danh sách dataclass thành JSON bằng `dataclasses.asdict`.
10. Khi load lại, kiểm tra top-level list, field thiếu/thừa và kiểu của authors/categories trước khi tạo `PaperRecord`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref JSON: `message.items`; cấu hình từ `Settings` |
| Raw schema | `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment` |
| Output | `list[PaperRecord]`, raw API response JSON và parsed raw records JSON |
| Module phụ thuộc | `core.config.Settings`; `core.utils.normalize_whitespace`, `read_json`, `write_json`; thư viện `requests` |
| Module sử dụng output | `ingestion.cleaning.build_clean_dataframe`; baseline pipeline; repair flow |
| Điều kiện lỗi cần xử lý | Timeout, HTTP `429/5xx`, JSON sai cấu trúc, DOI/title/abstract thiếu, DOI trùng, ngày không hợp lệ, snapshot sai schema |

Quy ước quan trọng:

- `paper_id` là DOI lowercase và không được thay đổi ở bước cleaning.
- Ngày hợp lệ được chuẩn hóa về `YYYY-MM-DD`; ngày thiếu một phần dùng ngày đầu tiên của kỳ, ví dụ `2026-07` thành `2026-07-01`.
- Metadata không có từ nguồn dùng chuỗi/list rỗng, không trộn `None`, `NaN` và `"N/A"`.

### Cách xác minh

Kiểm tra artifacts bằng PowerShell:

```powershell
$records = Get-Content -Raw -Encoding utf8 `
    -LiteralPath "data\raw\crossref_records.json" | ConvertFrom-Json

$records.Count
($records | Group-Object paper_id | Where-Object Count -gt 1).Count
($records | Where-Object {
    [string]::IsNullOrWhiteSpace($_.paper_id) -or
    [string]::IsNullOrWhiteSpace($_.title) -or
    [string]::IsNullOrWhiteSpace($_.summary)
}).Count
```

- **Kết quả mong đợi:** 24 records, 0 DOI trùng và 0 record thiếu DOI/title/summary.
- **Kết quả thực tế:** `24`, `0`, `0`.
- **Artifacts:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json`.

Payload mô phỏng cũng đã kiểm tra JATS, HTML entity, ngày thiếu day, tác giả/category trùng, DOI trùng, record thiếu abstract, retry `503` và round-trip save/load. Kết quả: `TV1 ingestion checks: OK`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Pipeline phải có khả năng truy vết và repair dữ liệu, trong khi Crossref là nguồn sống và response có thể thay đổi giữa các lần chạy.
- **Các phương án đã cân nhắc:**
  1. Chỉ trả danh sách records trong bộ nhớ, không lưu response.
  2. Chỉ lưu response Crossref và parse lại ở mọi bước.
  3. Lưu cả raw API response và parsed raw records theo schema ổn định.
- **Phương án đã chọn:** Lưu đồng thời `crossref_response.json` và `crossref_records.json`.
- **Lý do:** Raw response là bằng chứng nguyên bản để audit/repair; parsed records tạo contract đơn giản cho TV2 và tránh để mọi module phải hiểu schema Crossref. Chi phí lưu trữ nhỏ vì bài lab chỉ lấy 24 records.
- **Bằng chứng quyết định phù hợp:** 24 API items được parse thành 24 records; snapshot được load lại đúng toàn bộ records. Corruption flow sau này có thể repair từ raw artifacts thay vì che lỗi trên corrupted data.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ImportError: DLL load failed while importing base: An Application Control policy has blocked this file.` khi `import pandas`.
- **Lệnh tái hiện:**

  ```powershell
  .\.venv\Scripts\python.exe -c "import pandas; print(pandas.__version__)"
  ```

- **Nguyên nhân gốc:** Windows Application Control chặn native `.pyd`/DLL của Pandas. Đây không phải lỗi parser Crossref hoặc lỗi editable install; `from core.config import load_settings` vẫn chạy thành công.
- **Cách xử lý trong phạm vi TV1:** Tạo `.venv`, cài project bằng `python -m pip install -e .`, kiểm tra riêng module Crossref bằng payload mô phỏng và chạy live fetch mà không phụ thuộc vào Pandas. Dữ liệu JSON sau đó được kiểm tra thêm bằng PowerShell.
- **Cách xác minh sau khi xử lý:** Mock ingestion pass; Crossref live fetch trả 24 records; hai raw artifacts được ghi và đọc lại thành công.
- **Điều học được:** Cần phân biệt lỗi môi trường/native dependency với lỗi code nghiệp vụ, đồng thời thiết kế module ingestion đủ độc lập để có thể kiểm tra riêng.

Blocker môi trường chưa được xử lý triệt để:

- **Phạm vi bị ảnh hưởng:** Import package `ingestion` theo luồng thông thường, cleaning bằng Pandas và pipeline end-to-end.
- **Những gì đã loại trừ:** Sai thư mục cài đặt, thiếu editable install, thiếu package `core`, lỗi Crossref API và lỗi raw schema.
- **Bước tiếp theo:** Dùng môi trường Python được Application Control cho phép hoặc nhờ quản trị viên cho phép binary của Pandas, sau đó chạy lại baseline pipeline.

## 7. Hiểu biết về luồng end-to-end

1. **Từ Crossref đến vector index:** `fetch_source_records` lấy và lưu raw data. `build_clean_dataframe` chuẩn hóa thành bảng có `text_for_embedding`, `age_days` và các field hỗ trợ. `LocalEmbeddingIndex.build` dùng MiniLM tạo vector, lưu vào ChromaDB và tạo embedding manifest.
2. **Evaluation set và ground-truth IDs:** Mỗi câu hỏi có đáp án tham chiếu và danh sách DOI đúng. Retrieval hit xảy ra khi một DOI được truy xuất nằm trong `ground_truth_doc_ids`; câu trả lời được đo thêm bằng token F1 và judge score.
3. **Quality khác freshness:** Quality kiểm tra completeness, validity và uniqueness như paper ID, title, summary hoặc duplicate. Freshness tập trung vào độ mới của ngày xuất bản, latest/oldest date và số dòng vượt ngưỡng `age_days`.
4. **Dùng cùng test set:** Nếu mỗi trạng thái dùng câu hỏi khác nhau thì thay đổi metrics có thể do test set, không phải do corruption/repair. Giữ nguyên test set tạo phép so sánh công bằng.
5. **Repair thành công:** Repaired dataset phải được tái tạo từ raw source đáng tin cậy, vượt lại quality/freshness checks và làm metrics tiến gần hoặc trở về baseline. Cần đối chiếu cleaned artifacts, quality reports, freshness reports và ba bộ metrics.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.400 | 1.000 | Mất 60% retrieval hits sau corruption và phục hồi hoàn toàn |
| `mean_token_f1` | 1.000 | 0.310 | 1.000 | Context lỗi làm chất lượng câu trả lời giảm mạnh |
| `judge_accuracy` | 1.000 | 0.400 | 1.000 | Chỉ 40% câu trả lời trên corrupted data được đánh giá đúng |
| `mean_judge_score` | 5.000 | 2.800 | 5.000 | Giảm 2.2 điểm sau corruption và phục hồi hoàn toàn |
| Quality checks | PASS (0 fail) | FAIL (4 fail) | PASS (0 fail) | Phát hiện duplicate, title ngắn, summary rỗng và stale age |
| Freshness status | Fresh | Stale (1 row) | Fresh | Phát hiện một record có `age_days=9999` |

Số liệu trên được lấy từ bảng kết quả tích hợp baseline/corrupted/repaired do nhóm cung cấp. Cả ba trạng thái được đánh giá trên cùng evaluation set, vì vậy mức giảm ở corrupted data có thể được quy cho thay đổi dữ liệu thay vì thay đổi câu hỏi đánh giá.

### Kết luận từ số liệu

1. **Data corruption → quality/freshness → agent metric:** Duplicate, title ngắn, summary rỗng và record có `age_days=9999` làm quality chuyển từ `PASS` sang `FAIL` và freshness từ `Fresh` sang `Stale`. Đồng thời `retrieval_hit_rate` giảm từ `1.000` xuống `0.400`, `mean_token_f1` từ `1.000` xuống `0.310`, `judge_accuracy` từ `1.000` xuống `0.400` và `mean_judge_score` từ `5.000` xuống `2.800`.
2. **Repair → quality/freshness recovery → metric recovery:** Repair từ raw source đưa quality về `PASS (0 fail)` và freshness về `Fresh`; cả bốn agent metrics đều trở lại đúng mức baseline (`1.000`, `1.000`, `1.000`, `5.000`). Điều này cho thấy raw artifacts do TV1 lưu có thể đóng vai trò nguồn đáng tin cậy để phục hồi dữ liệu.

Xét trên toàn corrupted dataset, nhóm lỗi làm mất hoặc làm hỏng context — đặc biệt summary rỗng, title bị cắt ngắn và document liên quan bị thiếu — có tác động trực tiếp nhất đến retrieval và answer quality. Tuy nhiên, lần đánh giá này áp dụng nhiều corruption cùng lúc nên chưa đủ bằng chứng để xếp hạng riêng từng loại; cần chạy ablation test cho từng corruption để kết luận chính xác. Lỗi stale date được quan sát rõ nhất qua freshness signal (`Stale`, một dòng `age_days=9999`).

Kết quả khác kỳ vọng ở bước ingestion là 24/24 records không có Crossref `subject`. Kiểm tra raw API response xác nhận metadata nguồn thực sự không cung cấp trường này trong các items đã lấy. Vì vậy parser giữ `categories=[]` thay vì tự tạo category và làm mất tính trung thực của raw data.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Data pipeline cần lưu raw artifact bất biến để truy vết, tái hiện và repair; chỉ giữ dữ liệu đã clean là chưa đủ.
2. Data quality bắt đầu từ contract ổn định: document ID, kiểu dữ liệu, quy ước missing value và ngày phải được thống nhất trước khi các thành viên làm song song.
3. RAG phụ thuộc trực tiếp vào dữ liệu nguồn. Summary thiếu, DOI không ổn định hoặc document bị xóa có thể làm retrieval miss và khiến câu trả lời không có grounding phù hợp.

### Nếu có thêm thời gian

Tôi sẽ bổ sung test tự động bằng `pytest` cho parser và retry flow, đồng thời lưu thêm ingestion metadata như query, filter, fetch timestamp, response item count và hash của raw response. Cải thiện được đo bằng coverage cho các trường hợp thiếu field, retry và round-trip, cùng khả năng xác định chính xác cấu hình đã tạo ra mỗi snapshot.

Tôi cũng đề xuất sửa query `artifical intelligence` thành `artificial intelligence`, crawl hai tập dữ liệu với cùng filter rồi so sánh tỷ lệ title/abstract liên quan để đo tác động của lỗi chính tả lên source quality.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Tùng Dương

**Ngày xác nhận:** 2026-08-06
