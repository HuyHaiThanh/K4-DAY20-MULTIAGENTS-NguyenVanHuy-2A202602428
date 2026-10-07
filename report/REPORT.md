# Báo cáo Lab: Self evolving Agentic

Báo cáo theo README.md, GUIDE.md, RUBRIC.md và REPORT_TEMPLATE.md. Chỉ phân tích bộ thí nghiệm OpenAI hiện tại; key không được ghi trong báo cáo.

## 1. Thông tin nhóm và cấu hình

| Họ tên theo tên repo | Mã sinh viên theo tên repo | Phần đóng góp |
|---|---|---|
| Nguyễn Văn Huy | 2A202602428 | Các hàm TODO harness; thí nghiệm, review và báo cáo. Mã provided không phải đóng góp mới. |

- OpenAI `gpt-4.1-mini`, endpoint `https://api.openai.com/v1`, temperature 0, recursion_limit 40 cho mọi điều kiện.
- Deep Agents 0.7.21; Python 3.12.3 trên WSL Linux. make_model provided giữ nguyên: SDK retry 2, timeout 120s; không ép profile context.
- Kết quả chính: 6/18; development: 3/3; lượt lưu riêng: 2; curator: 1 lần. Usage ghi nhận gồm probe/curator/dev/attempts: 500,167 token.
- Commit freeze: `Chưa tạo`. Trạng thái: checkpoint đang hoàn thiện. Metadata/lệnh chạy tại OFFICIAL_EXPERIMENTS.md.

## 2. Giả thuyết (commit TRƯỚC tag freeze)

Giả thuyết dưới đây được lập trước mọi lượt eval. Căn cứ chỉ từ learn và guides/pseudocode/02_subagents.md, 04_curator.md, 05_skill_quality.md; không dùng kết quả eval để sửa dự đoán.

- H1 (subagents so với baseline): subagents không chắc cải thiện điểm eval; dự đoán token trung bình tăng. Learn code không tăng điểm, data giảm khi tác tử chính chỉ đọc output của implementer mà không kiểm chứng tính toán. Cô lập ngữ cảnh và delegation tạo thêm chi phí.
- H2 (skills-auto so với baseline): dự đoán cải thiện có giới hạn và không bảo đảm cao nhất ở eval. Skill code nhắc type hints/tests/changelog, nhưng không giữ tên file/heading cụ thể; skill data thiếu cent/meta/clean.csv và skill logs thiếu schema_version/generated_by. 04_curator.md cũng lưu ý skill tự sinh có thể không có lợi.
- H3 (tác vụ học so với tác vụ đánh giá): lợi ích của skill trên learn dự đoán lớn hơn eval vì eval thêm quy ước mới. 05_skill_quality.md giải thích skill chỉ giúp khi được đọc và thực hiện; skill hiện có khá chung chung, nên kỳ vọng transfer yếu và nhiễu một lần chạy đáng kể.

## 3. Làm quen Deep Agents

1. Công cụ mặc định: ls, read_file, write_file, edit_file, delete, glob, grep; execute chạy shell; task giao việc. Tour thật ngoại tuyến lưu tại tour.txt.
2. baseline/skills-auto có tác tử chính và general-purpose mặc định. subagents bổ sung explorer (đọc đặc tả), implementer (thực hiện), reviewer (kiểm tra): tổng 5 vai trò sẵn có, số invocation tùy quyết định agent. task nhận subagent_type và description; subagent stateless chỉ thấy prompt được giao, trả báo cáo về luồng chính. Agent chính phải truyền đủ quy tắc và kiểm chứng kết quả.
3. Trích task: “Put full detail in the prompt and state exactly what it should return”. Trích execute: “Use read_file rather than cat/head/tail.” Default system prompt của Deep Agents rỗng; harness truyền BASE_PROMPT provided. Công cụ chung là backend file/shell; custom subagent không tự thừa kế skill của tác tử chính.

## 4. Đường cơ sở và phân loại lỗi

Chỉ dùng baseline learn hợp lệ sau sửa lỗi line endings. Các lượt code có CRLF được giữ riêng, không dùng false failure tests_not_modified để quy lỗi agent.

| Tác vụ | Check thất bại | Nhóm | Bằng chứng từ detail/trace |
|---|---|---|---|
| code-learn | rule_type_hints | E | RULE: every public function (name not starting with '_') in the package has type annotations on all parameters and on the return value. |
| code-learn | rule_regression_tests | E | RULE: add tests/test_regressions.py with one test function per bug you fixed (at least 3); the file must pass. |
| code-learn | rule_changelog | E | RULE: record each fix in CHANGELOG.md under the heading '## Unreleased' as a bullet '- fix(<function name>): <short description>' (at least 3 bullets). |
| data-learn | rule_money_in_cents | E | RULE: money values in answer.json are integer cents (1606.67 USD is written 160667). |
| data-learn | rule_meta_block | E | RULE: answer.json has an object `meta` = {"source": <input file name>, "rows_in": <number of data rows in the input file, duplicates included>, "rows_used": <number of distinct orders with a known amount>}. |
| data-learn | rule_clean_csv | E | RULE: write workspace/clean.csv with the header order_id,timestamp_utc,region,amount_cents; one row per distinct order with a known amount; timestamp_utc as YYYY-MM-DDTHH:MM:SSZ (UTC); region in canonical spelling (North, South, East, West); amount in integer cents. |
| logs-learn | entry_count | D | wrong number of entries (got 19) |
| logs-learn | timestamps_utc | D | 7/25 timestamps match |
| logs-learn | exception_fields | D | 18 wrong `exception` values |
| logs-learn | repeat_counts | D | 18 wrong `repeat_count` values |
| logs-learn | counts_by_service | D | counts_by_service: wrong values |
| logs-learn | rule_service_names | E | RULE: service names in the output are lower-case with '-' replaced by '_' (payment-service -> payment_service). |
| logs-learn | rule_sorted_errors | E | RULE: `errors` is sorted by service, then by timestamp_utc, ascending. |
| logs-learn | rule_schema_header | E | RULE: the top-level object has "schema_version": 2 and "generated_by": "log-triage". |

Phân bố lỗi: {'E': 9, 'D': 5}. Check kỹ thuật baseline learn đạt 13/18. Quy ước E chiếm nhiều nhất; không coi mọi lỗi là thiếu quy ước.
Logs có bằng chứng A/B đi kèm các check D: trace không đọc README dù instruction yêu cầu và không gọi execute để parse/kiểm chứng; số entry, timestamp, exception, repeat và tổng service đều sai. Code đã đọc docstring, sửa hàm dùng chung và chạy test đạt; data dùng Python để tính. Vì vậy không quy A–D cho toàn bộ tác vụ. Không có bằng chứng F về tệp bị báo tạo nhưng không tồn tại trong baseline hợp lệ.

## 5. Điều kiện subagents

Ba subagent tự định nghĩa có scope rõ: explorer chỉ đọc, implementer chỉ sửa phần được giao và test, reviewer kiểm tra độc lập không sửa. Các role và PATHS_NOTE giữ nguyên giữa learn/eval.

| Learn | baseline token / giây | subagents token / giây | task calls |
|---|---:|---:|---:|
| code-learn | 36,247 / 24.8 | 48,097 / 23.9 | 0 |
| data-learn | 46,649 / 20.0 | 46,453 / 19.7 | 1 |
| logs-learn | 21,303 / 13.7 | 15,876 / 7.2 | 1 |

Code learn không giao việc: tác tử chính tự sửa và chạy test. Data gọi implementer, truyền yêu cầu tính toán và file đầu ra; chính agent chỉ read_file answer.json rồi kết thúc, không đối chiếu phép tính độc lập, điểm 1/8. Logs gọi general-purpose; mô tả có quy tắc parse nhưng không đầy đủ JSON schema/example. Subagent trả lời đang chuẩn bị xử lý, agent chính lại ghi dữ liệu ví dụ và không kiểm chứng, điểm 1/9. Trace không chứa nội bộ subagent: không khẳng định subagent đã chạy một lệnh nếu không thấy bằng chứng luồng chính.

## 6. Self-evolving: skill do curator sinh

Curator gọi OpenAI một lần, 3 skill được validator chấp nhận, không xóa/chạy lại hoặc sửa tay. Raw prompt/response/usage ở curator/. Review giữ các skill vì không có chỉ dẫn gây hại; ghi nhận thiếu quy tắc cụ thể thay vì chỉnh tay để tăng điểm.

| Skill | Tổng quát / đúng và hạn chế | Độ dài / tình huống đọc |
|---|---|---|
| code-style-enforcement | Tổng quát; đúng về annotation/test/changelog nhưng không chỉ rõ tests/test_regressions.py, số test hay heading/bullet cần có. | 7 dòng tổng / 3 dòng body; Use this skill when ensuring code follows organization-wide style rules such as type annotations on public functions, presence of regression tests, and changelog updates. |
| data-cleaning-and-normalization | Đúng quy trình normalize/date/dedup/giá trị thiếu; thiếu cent, meta và clean.csv. Giữ first occurrence cần kiểm tra lại ở dữ liệu mới có xung đột. | 8 dòng tổng / 4 dòng body; Use this skill when preparing raw data for analysis by normalizing fields, parsing dates, removing duplicates, and handling missing or invalid values. |
| log-file-parsing-and-aggregation | Đúng các bước severity/UTC/repeat/exception; thiếu cách đổi '-' thành '_', thứ tự sort cụ thể và schema_version/generated_by. | 10 dòng tổng / 6 dòng body; Use this skill when extracting structured error information from raw log files, including filtering by severity, normalizing timestamps, and aggregating repeated messages. |

Description theo tình huống rộng, body 3–6 bullet, không chứa đáp án hoặc định danh eval. Validator không thay thế review ngữ nghĩa; skill có thể hợp lệ nhưng quá chung chung để sửa rule_. Skill-read và hiệu quả thực tế được đối chiếu ở mục 8.

## 7. Kết quả so sánh

Chưa lập bảng chính thức khi bộ thí nghiệm chưa đủ; không dùng số minh họa thay kết quả.

## 8. Phân tích

Phân tích cuối sẽ được điền sau đủ 18 lượt và verify_freeze, không suy diễn từ development như thể đó là điểm eval.

## 9. Hạn chế và tính hợp lệ

1. Chỉ ba tác vụ mỗi role, mỗi condition một lượt: không đủ ước lượng phương sai hoặc kết luận thống kê về khả năng tổng quát.
2. Nhiệt độ 0 không bảo đảm kết quả giống nhau; điểm development/post-freeze cùng skill là kiểm tra nhiễu nhỏ, không phải nhiều lần lặp độc lập.
3. Quy ước Acme và dữ liệu do giảng viên thiết kế; lợi ích học rule_ không đại diện toàn bộ tác vụ thực tế hoặc mọi model.
4. Trace chỉ luồng chính, bị renderer cắt mỗi message 1500 ký tự; token cộng cả subagent nhưng không đủ để dựng lại mọi thao tác nội bộ.
5. CRLF Windows làm check hash sai; đã trả đúng blob LF và rerun thay vì sửa grader/điểm. Token usage không phải hóa đơn, lượt API lỗi có thể thiếu usage.

## 10. Kết luận

Chỉ kết luận cuối khi bộ thí nghiệm và review hoàn tất.

## Phụ lục

Lệnh và thứ tự: TESTING.md, OFFICIAL_EXPERIMENTS.md. Bonus GUIDE 6c ngoại tuyến ở bonus-redteam/README.md; model scripted chứng minh giới hạn validator, không đo xác suất tấn công OpenAI thành công. Extension độc lập chỉ được kiểm chứng offline và không thay điểm thí nghiệm gốc.
