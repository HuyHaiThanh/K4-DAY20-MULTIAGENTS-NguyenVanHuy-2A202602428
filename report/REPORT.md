# Báo cáo Lab: Self evolving Agentic

**Trạng thái:** mã và kiểm chứng extension đã hoàn thành; thí nghiệm học → curator → hypotheses → freeze → eval của repo gốc chưa chạy. Báo cáo 10 mục theo checklist gửi thêm nằm tại [FINAL_REPORT.md](FINAL_REPORT.md). Không dùng số liệu extension thay cho điểm sáu tác vụ chính thức.

## 1. Thông tin nhóm và cấu hình

| Định danh theo tên repo | Mã theo tên repo | Phần triển khai |
|---|---|---|
| Nguyễn Văn Huy (người nộp cần xác nhận) | 2A202602428 | TODO harness và extension coordinator/worker/tools/test; mã provided giữ nguyên |

- Model kiểm chứng extension: `openai/gpt-oss-120b`, `LAB_TEMPERATURE=0`; worker tối đa 4 lượt model trong pipeline acceptance.
- Deep Agents: 0.7.21. Python Windows 3.11.9; Python WSL ERPNext 3.12.3. Harness shell kiểm chứng bằng Linux.
- Tác vụ chính thức đã chạy: 0; chưa có skill sinh thật hoặc tag `freeze`.
- Benchmark API cuối extension: 9 request / 27.343 token; các probe và lần lỗi trước đó có usage riêng, không nằm trong tổng này.

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

Chưa viết giả thuyết cho thí nghiệm gốc vì chưa có kết quả học. Các dòng dưới đây cố ý để trống; không tạo commit/tag giả để vượt verify_freeze.

- H1 (subagents so với baseline):
- H2 (skills-auto so với baseline):
- H3 (tác vụ học so với tác vụ đánh giá):

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

Căn cứ: `src/lab/agent.py`, `src/lab/subagents.py`, `scripts/tour.py` và `guides/pseudocode/01_agent.md`, `02_subagents.md`, `03_runner.md`. Nội dung này mô tả thiết kế từ mã nguồn và tài liệu; chưa phải kết quả quan sát từ một lần chạy `tour.py`.

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

Chưa chạy baseline của code-learn/data-learn/logs-learn, nên chưa có bảng taxonomy dựa trên check thất bại chính thức. Các lỗi extension (network, evaluator json tool, timeout) được phân tích riêng trong FINAL_REPORT mục 6, không thay lỗi tác vụ học.

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
