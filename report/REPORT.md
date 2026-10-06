# Báo cáo Lab: Self evolving Agentic

> Sao chép tệp này thành `report/REPORT.md` (đã làm ở Phần 0) và điền dần qua các Phần của lab. Xóa các dòng hướng dẫn dạng trích dẫn (bắt đầu bằng `>`). Văn phong kỹ thuật, ngắn gọn, mọi nhận định đi kèm số liệu hoặc bằng chứng. Trong buổi học: điền mục 1 đến 7 (bản nháp). Sau buổi học: hoàn thiện mục 8 đến 10.

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| | | |

- Mô hình (tên deployment hoặc `LAB_MODEL`), nhiệt độ (`LAB_TEMPERATURE`), `recursion_limit`:
- Phiên bản Deep Agents (`pip show deepagents`), hệ điều hành, chạy trực tiếp hay trong Docker:
- Số lần chạy tác vụ đã dùng / ngân sách:
- Commit của tag `freeze`:

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

> Dự đoán điều kiện nào đạt điểm cao nhất trên **tác vụ đánh giá** và vì sao. Nêu căn cứ từ phân loại lỗi (mục 4) và từ tài liệu tham khảo. Điền cả ba dòng; `verify_freeze.py` kiểm tra điều này.

- H1 (subagents so với baseline):
- H2 (skills-auto so với baseline):
- H3 (tác vụ học so với tác vụ đánh giá):

## 3. Làm quen Deep Agents (Phần 0.3)

### Câu 1. Bài lab này có bao nhiêu agent? Mỗi agent làm gì?

Số agent phụ thuộc vào điều kiện thí nghiệm, không cố định là 3–4. Theo thiết kế được cung cấp, `baseline` có một tác tử chính và subagent `general-purpose` mặc định của Deep Agents. Tác tử chính nhận đề bài, lập kế hoạch, sử dụng công cụ và tổng hợp kết quả; `general-purpose` xử lý phần việc được giao. Có sẵn subagent không có nghĩa là subagent luôn được gọi.

Ở điều kiện `subagents`, hệ thống bổ sung ít nhất hai subagent do sinh viên định nghĩa. Tài liệu gợi ý ba vai trò: `explorer` đọc đặc tả và báo cáo thông tin, `implementer` thực hiện thay đổi và chạy kiểm tra, `reviewer` kiểm tra độc lập kết quả và trường hợp biên. Nếu chọn cả ba vai trò này, cấu hình có một tác tử chính và bốn loại subagent, gồm `general-purpose` và ba subagent tùy chỉnh. Hiện `get_subagents()` còn TODO, nên các vai trò tùy chỉnh này mới là phương án thiết kế, chưa được triển khai.

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

> Chỉ dùng tác vụ học. Mỗi dòng là một check thất bại.

| Tác vụ | Check thất bại | Nhóm lỗi (A-G) | Bằng chứng (trích ngắn từ `detail` hoặc vết) |
|---|---|---|---|
| | | | |

Nhận xét: nhóm lỗi nào chiếm đa số? Skill có thể phòng ngừa nhóm đó không?

## 5. Điều kiện `subagents` (Phần 2.3)

- Các subagent đã định nghĩa (tên, vai trò, lý do thiết kế):
- `subagent_calls` ở từng tác vụ và nhận xét (kể cả trường hợp bằng 0):
- Thông tin thiếu hoặc thừa khi giao việc (nếu có giao việc):
- Ảnh hưởng đến token và thời gian:

### Ph?n 5 b? sung: Test Results

Ph?n n?y ghi ki?m ch?ng extension theo v?n b?n Ph?n 5; gi? m?c `subagents` c?a m?u lab g?c ?? ?i?n th? nghi?m ch?nh th?c sau.

- Full suite Linux/WSL: **78/78 passed**, kh?ng s?a c?c test g?c.
- Coordinator: 15; workers/queue: 21; tools: 7; integration/e2e/benchmark: 6.
- Provided: 12; Deep Agents agent/backend: 9; runner: 6; curator: 2.
- Stress offline: 10/10 request data ??ng th?i ??t, m?i request c? workspace/model ri?ng.
- Coverage Linux: **88.11%** to?n package `lab`, v??t m?c ti?u 80%.
- Windows native v?n c? hai l?i shell Linux (`which`, `cat`); d?ng WSL ?? ki?m ch?ng harness.
- Log test/JUnit: `acceptance/pytest-linux.txt`, `acceptance/pytest-linux.xml`; coverage: `acceptance/coverage-linux.json`.

## 6. Self-evolving: skill do curator sinh (Phần 3)

- Số lần chạy curator, số skill bị xóa và lý do:

| Skill | Tổng quát hay riêng cho tác vụ học? | Đúng hay sai (nêu chỗ sai nếu có) | Độ dài, `description` và `skills_read` ở Phần 3.4 |
|---|---|---|---|
| | | | |

## 7. Kết quả so sánh (Phần 4.3, 4.4)

> Dán nội dung `report/table.md` và kết quả `python scripts/check_breakdown.py`. Nêu các lần chạy có `error` hoặc `skills_modified = true` (nếu có) và cách xử lý.

```text
(dán bảng ở đây)
```

## 8. Phân tích

> Trả lời từng câu bằng số liệu từ mục 7 và bằng chứng từ vết. Kết quả âm hoặc không có khác biệt vẫn hợp lệ nếu được phân tích tốt.

1. So với `baseline`, điều kiện nào cải thiện điểm tác vụ **học**? Điều kiện nào cải thiện điểm tác vụ **đánh giá**? Có điều kiện nào cải thiện tác vụ học nhưng không cải thiện tác vụ đánh giá? Nếu có, đó là dấu hiệu gì?
2. Tách điểm thành check kỹ thuật và check quy ước (`rule_`). Skill do curator sinh giúp nhóm check nào? Check quy ước **mới** của tác vụ đánh giá có được skill giúp không, và vì sao?
3. Dựa vào vết và `skills_read`, giải thích một check mà skill giúp đạt và một check mà skill không giúp (skill chưa được đọc, đọc nhưng không làm theo, skill thiếu hoặc sai).
4. Chi phí: so sánh số token trung bình giữa các điều kiện. Điều kiện nào có hiệu quả tốt nhất theo điểm trên mỗi token? Đa tác tử có đáng chi phí trong thí nghiệm này không?
5. Có dấu hiệu rò rỉ dữ liệu hoặc quá khớp nào trong skill sinh ra không? Nhóm đã phòng tránh như thế nào?
6. Nhiễu: so sánh điểm tác vụ học của cùng bộ skill ở Phần 3.4 (đã sao lưu) và sau đóng băng. Chênh lệch bao nhiêu? Nó cho biết điều gì về độ tin cậy của các chênh lệch trong bảng ở mục 7?

## 9. Hạn chế và tính hợp lệ

> Nêu ít nhất 3 hạn chế và ảnh hưởng của từng hạn chế đến kết luận (ví dụ: chỉ 3 tác vụ mỗi vai trò, mỗi cấu hình chạy một lần, nhiễu của mô hình, tác vụ do giảng viên thiết kế sẵn quy ước, chỉ một mô hình).

1.
2.
3.

## 10. Kết luận

> Tối đa 5 câu. Chỉ khẳng định điều số liệu hỗ trợ. Nêu một đề xuất cải tiến tiếp theo.

## Phụ lục

- Lệnh đã chạy (theo thứ tự):
- Thử thách mở rộng (nếu có): hướng chọn, kết quả, nhận xét.
- Ghi chú khác:
