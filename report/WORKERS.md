# Phần 3: Worker Agents và Communication

Phần 4 bổ sung class tools, child-process Python, chart/report và async tool invocation; xem `TOOLS.md` cho hành vi hiện tại. Các mô tả Phần 3 dưới đây ghi nhận triển khai/checkpoint ban đầu; trace standalone được chạy lại với tools mới.

Phần bổ sung nằm trong package `lab`, nối với coordinator của Phần 2. Các module gốc được cung cấp của bài Deep Agents, bộ chấm và task không bị thay đổi. Phần này chưa triển khai các TODO của harness gốc.

## Chạy offline

```bash
python -m pytest tests/test_03_workers.py tests/test_02_coordinator.py tests/test_01_provided.py
python scripts/test_workers_standalone.py
```

Windows trong workspace hiện tại: dùng `.venv/Scripts/python.exe`. Standalone dùng `ScriptedChatModel`, không gọi API; CSV/aggregate/Python/scoring là tool thực chạy tại máy. Trace JSON in ra có kết quả tool, request, response, ID, correlation ID và timestamp UTC. Điểm evaluator trong demo là quyết định mô hình giả, không phải chứng cứ chất lượng độc lập.

## Cấu trúc và sử dụng

`src/lab/agents/base_worker.py`: bind tools, tạo system/human messages, xử lý toàn bộ tool calls bằng AIMessage/ToolMessage giữ lịch sử đầy đủ, giới hạn số lượt model và tool. State đếm tool và trace được tạo riêng cho mỗi request. `process` dùng cho chương trình đồng bộ, `process_async` dùng trong async. Không gọi `asyncio.run` trong event loop đang chạy. Worker lỗi trả `status=error`; cancellation truyền ra ngoài.

| Worker | Tools | Phạm vi |
|---|---|---|
| DataAgent | csv_parser, data_validation, data_analysis; query_database nếu có database_path | CSV, validation, sum/avg/count/group; SQLite read-only |
| CodeAgent | python_repl, create_file, edit_file, run_script | Tệp trong workspace và bộ thực thi Python giới hạn |
| EvaluatorAgent | scoring, validation, quality_check, feedback_generator | Rubric 30/30/20/20 và kiểm tra cấu trúc JSON kết quả |

Không thêm pandas hoặc SQL server giả: các aggregate dùng thư viện chuẩn; SQL tùy chọn nhận đường dẫn SQLite và mở connection riêng cho mỗi lần gọi. Các công cụ hiện tại chạy đồng bộ trong lượt xử lý async nhưng có giới hạn kích thước/độ phức tạp; không đưa arbitrary code vào thread pool rồi tuyên bố timeout đã dừng nó.

Ví dụ tích hợp với model có hỗ trợ async và tool calling:

```python
from pathlib import Path
from lab.agents import DataAgent, CodeAgent, EvaluatorAgent
from lab.communication import MessageQueue
from lab.coordinator import Coordinator

# model được truyền từ bên ngoài; dùng fake model để kiểm thử không tốn token.
coordinator = Coordinator(worker_agents=[
    DataAgent(model), CodeAgent(model, Path("workspace")), EvaluatorAgent(model)
], message_queue=MessageQueue())
result = await coordinator.process_async({
    "task_type": "data_analysis", "content": "Tính tổng doanh thu",
    "parameters": {"rows": [{"sales": 10}, {"sales": 20}]}
})
evaluation = await coordinator.process_async({"task_type": "evaluation", "content": result})
```

Workspace phải tồn tại. Với model giả có state, dùng model riêng cho mỗi worker như demo. Với model thật, cần kiểm thử thêm cancellation của transport/provider.

## MessageQueue và tích hợp

Queue là mailbox in-memory trong một tiến trình/event loop, không phải broker bền vững. Đăng ký lại agent không xóa inbox. Send sao chép payload, thêm UUID và timestamp; nhận có thể lọc correlation ID. Mailbox, kích thước message và lịch sử đều có giới hạn. `get_message_log` trả bản sao, có thể serialize JSON; log đầy đủ chứa dữ liệu request nên chỉ dùng dữ liệu phù hợp để lưu/chia sẻ.

Coordinator dùng queue khi được truyền `message_queue`, giữ đường gọi trực tiếp để tương thích Phần 2. Mỗi attempt có correlation ID mới. Request đi coordinator → worker; handler nhận đúng request, gọi worker, gửi result worker → coordinator. Handler tạm thời được chờ và hủy/dọn khi timeout hoặc cancellation, không có daemon chạy sót. Kết quả lỗi worker được nâng thành lỗi của task, không báo success vì chỉ nhận được một dict.

## Review, cải thiện và giới hạn

- Sửa lỗi trong ví dụ: listener chỉ lấy message kế tiếp có thể nhận nhầm phản hồi của worker khác. Test dùng một worker với nhiều task hoàn thành đảo thứ tự để kiểm tra correlation.
- Sửa lỗi vòng tool chỉ xử lý tool đầu tiên và mất lịch sử: xử lý mọi call, giữ ToolMessage đúng ID và ghi actual output vào metadata.
- Sửa state `_executed_tools` dùng chung: state local cho từng request, kiểm tra chạy nhiều request không cộng dồn sai.
- Không cho SQL write/DDL/extension: connection read-only, authorizer và instruction budget, giới hạn 1000 dòng kết quả.
- Code dùng interpreter AST giới hạn 500 node/10000 ký tự; không hỗ trợ import, loop, attribute, hàm tùy ý hay shell. Đây không phải full Python REPL, không chạy pandas/matplotlib. Có giới hạn số và chuỗi thay cho việc chạy code tùy ý rồi khó dừng trên Windows.
- Tệp giới hạn kích thước, đường dẫn tương đối trong workspace, không overwrite khi create; edit phải khớp đúng một lần. Không dùng chung workspace với tác nhân ngoài không tin cậy vì kiểm tra đường dẫn không bảo vệ được race symlink của tiến trình bên ngoài.
- `execution_verified` chỉ nói có tool thực thi code thành công trong request, không chứng minh mọi tệp sinh ra đã được test. Tool events là bằng chứng để đối chiếu câu trả lời model.
- Evaluator kiểm tra JSON và miền score, nhưng scoring chỉ tính trọng số; quality_check chỉ dò từ khóa. Cần checker độc lập hoặc chuyên gia để kết luận accuracy thật.
- Không tự chuyển kết quả DataAgent sang CodeAgent trong route complex: hai worker nhận cùng request và chạy song song. Nếu code cần dữ liệu tính toán trước, caller phải chạy theo giai đoạn rồi gửi kết quả data trong request code, như evaluation trong demo.
- Queue/log không persistence; priority chỉ metadata. Retry chỉ nên bật khi worker idempotent. Giới hạn trong module là giới hạn đầu vào/thao tác, không phải sandbox OS hoặc quota RAM tổng của tiến trình.

Các kiểm thử gồm worker tools thực, call nhiều tool, lỗi tool, budget, path traversal, SQL read-only, code không an toàn, JSON evaluator sai, mailbox đầy, timeout, payload isolation, correlation và cleanup khi timeout.

## Kết quả kiểm chứng cuối

- Python 3.11.9/Windows: 21 test worker/communication + 15 test coordinator + 12 test provided đạt, tổng 48 passed.
- Standalone worker/queue đạt; trace thật lưu tại `report/workers-standalone.txt`, có 6 message và output tool thực (aggregate = 30, stdout = 30).
- Standalone coordinator Phần 2 vẫn đạt 3/3.
- Full suite: 49 passed, 16 failed. Các lỗi đều là NotImplementedError từ TODO của harness gốc (`agent.py`, `subagents.py`, `runner.py`, `curator.py`); không báo toàn bộ lab đã hoàn thành.
- Review tìm thấy nguy cơ cancellation ở các `wait_for` lồng nhau. Queue đổi sang scope `asyncio.timeout` để truyền cancellation rõ ràng; test timeout và lỗi worker kiểm tra riêng, dùng deadline đủ lớn cho case lỗi để tránh phụ thuộc độ phân giải timer Windows.
