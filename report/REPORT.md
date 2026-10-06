# Báo cáo Lab: Self evolving Agentic

**Trạng thái:** mã và kiểm chứng extension đã hoàn thành; thí nghiệm gốc đang thực hiện theo thứ tự học → curator → hypotheses → freeze → eval. Báo cáo 10 mục theo checklist gửi thêm nằm tại [FINAL_REPORT.md](FINAL_REPORT.md). Không dùng số liệu extension thay cho điểm sáu tác vụ chính thức.

## 1. Thông tin nhóm và cấu hình

| Định danh theo tên repo | Mã theo tên repo | Phần triển khai |
|---|---|---|
| Nguyễn Văn Huy (người nộp cần xác nhận) | 2A202602428 | TODO harness và extension coordinator/worker/tools/test; mã provided giữ nguyên |

- Model kiểm chứng extension: `openai/gpt-oss-120b`, `LAB_TEMPERATURE=0`; worker tối đa 4 lượt model trong pipeline acceptance.
- Deep Agents: 0.7.21. Python Windows 3.11.9; Python WSL ERPNext 3.12.3. Harness shell kiểm chứng bằng Linux.
- Lượt chính thức hợp lệ đã có: baseline/data-learn; các lượt tiếp theo đang chạy. Chưa có skill sinh thật hoặc tag `freeze`.
- Benchmark API cuối extension: 9 request / 27.343 token; các probe và lần lỗi trước đó có usage riêng, không nằm trong tổng này.

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

Các dự đoán dưới đây được viết khi chưa chạy hoặc xem điểm eval. Căn cứ ban đầu: baseline/data-learn đạt 5/5 check kỹ thuật nhưng thiếu cả ba quy ước Acme; đây là thông tin từ tập học, không phải đáp án eval.

- H1 (subagents so với baseline): subagents khó tăng đáng kể điểm kỹ thuật nếu baseline đã xử lý tốt đặc tả; cả hai vẫn có thể thiếu quy ước ẩn. Delegation và kiểm chứng có thể giúp task code nhưng dự đoán token trung bình cao hơn baseline, do nhiều ngữ cảnh riêng và giao việc lặp.
- H2 (skills-auto so với baseline): skills-auto sẽ có điểm eval trung bình cao nhất trong ba điều kiện nhờ chuyển các quy ước Acme từ feedback học thành checklist được đọc trước khi giải task. Dự đoán lợi ích chủ yếu ở rule_, với điều kiện agent thực sự đọc và làm theo skill; không kỳ vọng luôn đạt 100%.
- H3 (tác vụ học so với tác vụ đánh giá): cải thiện rule_ trên learn sẽ lớn hơn trên eval, vì eval thêm quy ước mới không có trong feedback học. Kỹ thuật và quy ước mới có thể vẫn thất bại; không dùng chênh lệch một lần chạy làm bằng chứng nhân quả chắc chắn.

Căn cứ cơ chế: [SkillsMiddleware — LangChain](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware) mô tả metadata được nạp trước, nội dung đầy đủ được đọc khi cần; [SubAgent — LangChain](https://reference.langchain.com/python/deepagents/middleware/subagents/SubAgent) mô tả ngữ cảnh subagent isolated. Báo cáo căn cứ hành vi cụ thể trên tour và Deep Agents 0.7.21 đang cài, không suy ra mọi API trong tài liệu mới đều giống phiên bản này.

## 3. Làm quen Deep Agents (Phần 0.3)

### Câu 1. Bài lab này có bao nhiêu agent? Mỗi agent làm gì?

Số agent phụ thuộc vào điều kiện thí nghiệm, không cố định là 3–4. Theo thiết kế được cung cấp, `baseline` có một tác tử chính và subagent `general-purpose` mặc định của Deep Agents. Tác tử chính nhận đề bài, lập kế hoạch, sử dụng công cụ và tổng hợp kết quả; `general-purpose` xử lý phần việc được giao. Có sẵn subagent không có nghĩa là subagent luôn được gọi.

Ở điều kiện `subagents`, hệ thống bổ sung ít nhất hai subagent do sinh viên định nghĩa. Tài liệu gợi ý ba vai trò: `explorer` đọc đặc tả và báo cáo thông tin, `implementer` thực hiện thay đổi và chạy kiểm tra, `reviewer` kiểm tra độc lập kết quả và trường hợp biên. Nếu chọn cả ba vai trò này, cấu hình có một tác tử chính và bốn loại subagent, gồm `general-purpose` và ba subagent tùy chỉnh. Ở Phần 5, `get_subagents()` đã được triển khai với explorer, implementer và reviewer; các test Linux đã xác nhận cấu hình này.

Điều kiện `skills-auto` dùng tác tử mặc định có nạp skill do curator sinh. Curator là bước gọi mô hình riêng để rút kinh nghiệm từ phản hồi và trace của tác vụ học, không phải worker được coordinator gọi trong lúc giải tác vụ. Bộ chấm `check.py` là chương trình kiểm tra tự động, không phải một AI evaluator agent.

### Câu 2. Coordinator giao tiếp với worker agents bằng cách nào?

Tác tử chính đóng vai trò coordinator và giao việc bằng công cụ `task` của Deep Agents. Khi gọi công cụ, nó chọn loại subagent và gửi mô tả công việc, đầy đủ quy tắc và đường dẫn cần dùng. Theo hướng dẫn của lab, mỗi lần giao việc tạo một phiên subagent có ngữ cảnh riêng; subagent chỉ nhận nội dung được gửi, không tự nhìn thấy toàn bộ lịch sử hội thoại của tác tử chính.

Subagent sử dụng công cụ để xử lý công việc rồi trả về một báo cáo cuối qua kết quả của công cụ `task`. Tác tử chính phải kiểm tra báo cáo trước khi sử dụng, sau đó tiếp tục xử lý hoặc giao phần việc tiếp theo. Các thay đổi trong workspace chung của sandbox cũng là cách chuyển giao sản phẩm giữa các tác tử. Repo không yêu cầu xây message queue hoặc API giao tiếp riêng.

### Câu 3. Có những công cụ (tools) nào được chia sẻ giữa các agent?

Theo `scripts/tour.py` và hướng dẫn backend, nhóm công cụ làm việc trên tệp gồm `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`; công cụ `execute` chạy shell, Python và test. Tác tử chính và subagent sử dụng các công cụ được cấu hình cho mình để làm việc trên workspace trong cùng sandbox; subagent có thể được giới hạn công cụ bằng cấu hình `tools`. Công cụ `task` là cơ chế để tác tử chính giao việc cho subagent.

Công cụ tệp dùng đường dẫn ảo theo gốc sandbox, còn shell dùng đường dẫn thật tương đối như `workspace/...`. Các tác tử chia sẻ sản phẩm trong workspace nhưng có ngữ cảnh hội thoại riêng. Subagent tùy chỉnh không tự kế thừa skill của tác tử chính; phải cấu hình `skills` riêng nếu muốn nạp skill cho chúng.

Việc đo token, thời gian, đếm lời gọi công cụ, chấm điểm và ghi `run.json`/`trace.md` do runner thực hiện ở bên ngoài vòng làm việc của agent. Đây không phải các công cụ logging hoặc monitoring riêng mà mọi agent gọi. Trace và số đếm công cụ chỉ phản ánh luồng chính; token được cộng dồn cả các lần gọi mô hình của subagent.

### Ba câu hỏi theo GUIDE 0.3

1. Tour thực tế liệt kê `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`, `execute`, `task`; `execute` cho phép chạy shell.
2. `general-purpose` có cùng công cụ với tác tử chính và dùng cho tác vụ nhiều bước. Mỗi invocation mặc định stateless: chỉ thấy prompt được giao, trả một báo cáo cuối.
3. Trích từ `task`: “Put full detail in the prompt and state exactly what it should return”. Trích từ `execute`: “Use read_file rather than cat/head/tail.” Tour cho thấy system prompt mặc định rỗng; harness lab truyền BASE_PROMPT riêng.

Bằng chứng ngoại tuyến: [tour.txt](tour.txt), chạy bằng Deep Agents 0.7.21. Mô tả tool execute có quy ước đường dẫn tuyệt đối; BASE_PROMPT/ PATHS_NOTE của lab quy định đường dẫn tương đối workspace/ cho backend này, vì vậy giữ nguyên hằng số được cung cấp.

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

Kết quả hợp lệ đầu tiên: baseline/data-learn đạt 5/8, 56.057 token, 405,7 giây, error=null. Những lần API lỗi được lưu riêng, không tính là lỗi agent.

| Tác vụ | Check thất bại | Nhóm | Bằng chứng từ detail |
|---|---|---|---|
| data-learn | rule_money_in_cents | E | money values in answer.json are integer cents |
| data-learn | rule_meta_block | E | answer.json has an object `meta`, gồm source, rows_in, rows_used |
| data-learn | rule_clean_csv | E | write workspace/clean.csv with the header order_id,timestamp_utc,region,amount_cents |

Ở data-learn, check kỹ thuật đạt 5/5 và check quy ước đạt 0/3. Trace có đọc dữ liệu, chạy analyze.py và đọc lại answer.json; chưa có bằng chứng lỗi A–D hoặc F ở lượt này. Ba lỗi đều thuộc E vì quy ước Acme không được trình bày đầy đủ trong đề. Skill từ feedback có thể truyền lại những quy tắc còn thiếu. Bảng sẽ được bổ sung sau các lượt học còn lại.

## 5. Điều kiện `subagents` (Phần 2.3)

Đã triển khai explorer (đọc đặc tả), implementer (thực hiện và kiểm tra), reviewer (review độc lập). Deep Agents còn có general-purpose mặc định. Test gốc xác nhận trường bắt buộc, delegation note và PATHS_NOTE. Chưa có số đo subagent_calls/token trên tác vụ chính thức; queue extension là cơ chế khác với task của Deep Agents.

### Phần 5 bổ sung: Test Results

- Checkpoint trước bonus: Linux 78/78 passed, coverage 88,11%.
- Coordinator 15; workers/queue 21; tools 7; integration/e2e/benchmark 6.
- Provided 12; agent/backend 9; runner 6; curator 2.
- Stress data offline 10/10 request đạt. Đo tài nguyên bổ sung chạy 10/10 complex offline đạt.
- Gate cuối có bonus: **83/83 passed, coverage 88.54%**; xem [pytest-linux.txt](acceptance/pytest-linux.txt), [coverage-linux.txt](acceptance/coverage-linux.txt).
- Windows native có hai lỗi shell Linux; không dùng kết quả Windows để tuyên bố harness toàn bộ đạt.

## 6. Self-evolving: skill do curator sinh (Phần 3)

curate_skills đã được cài đặt, test offline kiểm tra chỉ đọc learn, bỏ tên/path không an toàn và không gọi model nếu không có failed check. Chưa chạy curator thật vào skills/auto; các skill trong test chỉ nằm ở thư mục tạm. Không có kết quả skills_read chính thức để phân tích.

### Phần 5 bổ sung: Performance Analysis

Các số đo dưới đây thuộc extension fixture local; mỗi nhóm chạy 3 lần, không phải baseline/subagents/skills-auto của sáu tác vụ gốc.

| Chế độ | Test case | Min (s) | Max (s) | Avg (s) | Median (s) | P99 mẫu (s) | Đạt | Req/min | Token provider |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Offline scripted | Simple data query | 0.016 | 0.047 | 0.031 | 0.031 | 0.047 | 3/3 | 1914.89 | 0 |
| Offline scripted | Code generation | 0.062 | 0.094 | 0.078 | 0.078 | 0.094 | 3/3 | 769.23 | 0 |
| Offline scripted | Complex workflow | 0.109 | 0.125 | 0.115 | 0.110 | 0.125 | 3/3 | 523.26 | 0 |
| API thật | Simple data query | 1.484 | 3.297 | 2.135 | 1.625 | 3.264 | 3/3 | 8.40 | 3825 |
| API thật | Code generation | 2.078 | 2.406 | 2.266 | 2.313 | 2.404 | 3/3 | 8.24 | 7420 |
| API thật | Complex workflow | 8.079 | 21.313 | 15.422 | 16.875 | 21.224 | 3/3 | 2.94 | 16098 |

API thật có pacing 5 giây: không tính trong latency, có tính trong throughput. Complex median 16,875 giây và P99 mẫu 21,224 giây chưa đạt mục tiêu latency; throughput live chưa đạt >10 req/min. Fake token là synthetic. Worker busy fraction là thời gian chiếm slot, không phải CPU utilization; token timeout có thể thiếu.

Sau review, tách interpreter stdlib-only/cache adapter giảm median code offline 0,937 → 0,078 giây. Terminal submit_evaluation và giảm context khắc phục lỗi tool json không tồn tại; benchmark live cuối đạt 9/9. Giữ riêng các lần lỗi mạng/timeout trước đó. Số đo CPU/RAM và phân tích giới hạn ở FINAL_REPORT mục 5, TESTING.md và acceptance/resources.json.

## 7. Kết quả so sánh (Phần 4.3, 4.4)

Chưa có report/table.md chính thức vì chưa chạy đủ ba điều kiện/sáu tác vụ sau freeze. Bảng extension mục 6 không thay kết quả lab.compare.

## 8. Phân tích

Chưa kết luận về lợi ích subagents/skills-auto, check rule_, overfitting hoặc transfer sang eval vì chưa có thí nghiệm gốc. Phân tích extension có bằng chứng trong FINAL_REPORT mục 5–8; benchmark offline/live và bonus được ghi riêng.

## 9. Hạn chế và tính hợp lệ

1. Fixture nhỏ, ba mẫu/nhóm, một model: chưa đủ suy rộng P99/accuracy/error rate production.
2. Ratings evaluator được cung cấp: weighted score không phải chứng minh accuracy thật.
3. Linux/Windows khác nhau, quota/pacing và network ảnh hưởng thời gian; lỗi/timeout có thể thiếu usage.
4. Python subset và queue/cache single-process; chưa có OS sandbox, distributed recovery hoặc RAM quota Windows.
5. Các tác vụ chính thức, curator thật, hypotheses/freeze chưa chạy; repo chưa đầy đủ theo RUBRIC gốc.

## 10. Kết luận

Mã harness và extension đã được kiểm chứng bằng test Linux và API thật trên fixture. Benchmark cuối đạt 9/9 nhưng complex latency còn vượt mục tiêu. Bonus cache giảm tính lặp trên workload offline, không chứng minh hiệu năng production. Muốn nộp theo RUBRIC gốc cần thực hiện learning/curator/hypotheses/freeze/eval đúng thứ tự.

## Phụ lục

- Lệnh test/debug/profile/benchmark: TESTING.md.
- Bonus: FINAL_REPORT phụ lục Result Caching; scripts/benchmark_cache.py và report/bonus-cache/benchmark.json.
- Mã và module theo từng pha: COORDINATOR.md, WORKERS.md, TOOLS.md.
