# Phần 4: Tools và hợp tác agent

Các class trong `src/lab/tools/` có input schema strict, `validate_input`, `invoke`, adapter async và LangChain. Lỗi trả envelope `status=error`; BaseWorker chuyển lỗi tool thành lỗi worker, coordinator giữ trạng thái lỗi. Mỗi output có thời gian thực thi. Query/code và output được ghi trong trace tool/queue của demo, không gửi dịch vụ ngoài.

## Chạy

```bash
python -m pytest tests/test_04_tools.py tests/test_03_workers.py tests/test_02_coordinator.py tests/test_01_provided.py
python scripts/test_tool_integration.py
```

Trên Windows dùng `.venv/Scripts/python.exe`. Demo chạy local với ScriptedChatModel, không token. SQLite và tools thực thi thật; quyết định model là scripted. Artifacts ghi vào `report/tools-demo/`: biểu đồ SVG, báo cáo Markdown và trace JSON gồm toàn bộ 3 giai đoạn và 6 message.

## Các tools

- Database: QueryDatabaseTool nhận đường dẫn SQLite tồn tại, bound parameters, read-only connection, SQLite authorizer, instruction budget và tối đa 1000 dòng. Không nối thêm LIMIT vào SQL đã có LIMIT; giới hạn caller áp dụng lên kết quả được lấy có giới hạn.
- Data: CSVParserTool, AggregationTool dùng stdlib. PandasTool có triển khai aggregate có giới hạn, bật qua `DataAgent(..., use_pandas=True)` nếu môi trường đã cài pandas. Thiếu dependency sẽ báo lỗi rõ ràng, không giả thành công; pandas không được cài trong môi trường kiểm chứng hiện tại.
- Code: PythonREPLTool và RunScriptTool chạy interpreter Python giới hạn của Phần 3 trong child process; mỗi request có state riêng. Có timeout tối đa/default 30 giây, capture stdout/stderr, kill và chờ thu hồi child khi timeout/cancellation. Không dùng raw exec hoặc chặn import bằng dò chuỗi. CreateFileTool/EditFileTool giữ path trong workspace, giới hạn file và không overwrite khi create.
- VisualizationTool tạo SVG bar chart từ số liệu có kiểm tra. Máy chưa có matplotlib; demo tạo SVG thật bằng tool trusted, không tuyên bố chạy matplotlib hoặc sinh PNG.
- Evaluator: ScoringTool nhận điểm từng tiêu chí được cung cấp rõ ràng, tính weighted_score và grade A-F. Không dùng độ dài văn bản để suy ra accuracy. ValidationTool kiểm required fields, ComparisonTool so sánh JSON có phân biệt kiểu, ReportGeneratorTool tạo báo cáo từ findings đã cung cấp.

## Collaboration

Demo chạy theo phụ thuộc thực: DataAgent query SQLite → caller lấy dữ liệu từ output tool, truyền trong parameters của CodeAgent → CodeAgent tạo chart và kiểm tổng trong child process → evaluator nhận cả hai kết quả, tính rubric, so sánh và tạo report. Coordinator và MessageQueue đảm nhận routing và trao đổi mỗi giai đoạn. Luồng này không chạy song song hai bước có phụ thuộc dữ liệu.

## Review và tự phản biện

- Python là arithmetic subset, không full Python/pandas/matplotlib. Child process tăng khả năng thu hồi khi timeout; không phải container/OS sandbox. Resource bounds gồm AST/code/numeric/string/output và timeout, chưa có RAM quota toàn tiến trình trên Windows. Không đưa arbitrary Python vào interpreter này.
- Dùng standard subprocess pipes và thread chỉ để chờ `communicate`; timeout/cancellation vẫn kill child và chờ thread hoàn tất. Trên host Windows này asyncio subprocess named pipes bị WinError 5; không bỏ qua test mà dùng phương án standard pipes đã kiểm chứng. Popen startup ngắn vẫn đồng bộ trên event loop.
- SQL mở connection riêng cho mỗi call rồi đóng để không dùng connection SQLite xuyên thread; lựa chọn này ưu tiên tính đúng trong worker async hơn cache connection chưa quản lý lifecycle. Query quá 1000 dòng báo lỗi thay vì silently truncate; giới hạn caller nhỏ hơn báo `truncated`.
- Score 85.5/B trong demo là kết quả tính đúng từ ratings mẫu, không chứng minh agent đạt độ chính xác 85.5%. Comparison/validation là bằng chứng riêng.
- Tệp/log chỉ nên dùng trong workspace do ứng dụng sở hữu; không có bảo vệ khỏi tác nhân ngoài đồng thời thay symlink. Queue không persistence. Model thật/transport thật chưa được thử.
- Các module harness và bộ chấm có sẵn của lab không bị sửa; Phần 4 vẫn là extension theo văn bản, chưa giải các TODO của Deep Agents gốc.

## Kết quả kiểm chứng

- 7 test tools + 21 test workers/queue + 15 test coordinator + 12 test provided: 55 passed trên Windows/Python 3.11.9.
- Integration local: 3/3 đạt, bao gồm kết thúc/dọn thư mục SQLite thành công. Demo worker Phần 3 cũng chạy lại thành công với tools mới.
- Full suite: 56 passed, 16 failed từ các TODO của harness gốc; không tuyên bố toàn bộ lab đạt.
- Test timeout/cancellation ghi nhận child process đã kết thúc qua `poll()`, không chỉ kiểm tra message lỗi.
- Review thêm giới hạn SQLite row/SQL length và tổng kích thước output, test query blob quá lớn bị chặn. Child Python chỉ nhận một tập biến môi trường tối thiểu, không thừa kế khóa API.
- PandasTool là nhánh tùy chọn chưa kiểm chứng runtime vì máy không có pandas. SVG thay thế ví dụ matplotlib/PNG; không cài thêm dependency hoặc gọi mô hình thật.
