# Phần 2: Coordinator Agent

Văn bản được cung cấp mô tả một coordinator riêng; repo gốc dùng Deep Agents và không có `src/coordinator.py`, `base_agent.py` hay `test_02_coordinator.py`. Phần bổ sung đặt tại `src/lab/coordinator.py` để phù hợp package hiện có. Không thay đổi các test, task, script hoặc module có sẵn của lab. Đây là phần mở rộng độc lập, chưa thay thế các TODO của harness và chưa tích hợp với runner Deep Agents.

## Cách chạy

Trong môi trường đã cài `pip install -e .`:

```bash
python -m pytest tests/test_02_coordinator.py -v
python scripts/test_coordinator_standalone.py
```

Trên Windows với môi trường hiện tại, dùng `.venv/Scripts/python.exe` thay cho `python`.

## Luồng xử lý

`process_async` nhận request → `parse_request` kiểm tra cấu trúc hoặc phân loại từ khóa → `route_task` chọn worker → `execute_tasks` chạy đồng thời → `aggregate_results` giữ kết quả từng task và tổng hợp trạng thái. Dùng `process` nếu chương trình đồng bộ; trong event loop phải dùng `await process_async`.

Worker có tên duy nhất và phương thức async `process_async(content)`. Request có thể là chuỗi hoặc dict gồm `task_type`, `content`, `parameters`, `priority`. Các loại hỗ trợ: `data_analysis`, `code_generation`, `evaluation`, `complex`. Priority là metadata, chưa có scheduler ưu tiên. Coordinator truyền cả request đã phân tích cho worker. Phần 3 đã bổ sung queue và worker chuyên biệt; xem `WORKERS.md`.

Không gọi model để parse request. Phân loại bằng từ khóa chỉ là cách minh họa; câu không nhận diện được phải dùng request có `task_type` rõ ràng. Không âm thầm chuyển câu lạ cho data worker. Model của coordinator chưa sử dụng để parse. Khi truyền message_queue, coordinator thực thi qua mailbox in-memory có correlation; nếu không truyền, vẫn gọi worker trực tiếp.

## Xử lý lỗi và tự phản biện

- Kiểm tra input, worker thiếu/trùng tên, ID task trùng, timeout không hợp lệ và giới hạn số task đang chạy trước khi thực thi.
- Async timeout theo từng lần thử; hủy worker quá hạn, giữ kết quả thành công của worker khác. Tổng thời gian worker có thể đạt `(max_retries + 1) * timeout`.
- Retry mặc định tắt; khi bật chỉ retry task thất bại, không chạy lại task đã thành công. Worker có tác dụng phụ phải bảo đảm idempotency trước khi bật retry.
- Tổng hợp dùng danh sách theo loại để không ghi đè nhiều kết quả cùng loại. Status là `success`, `partial` hoặc `error`; lỗi không bị báo thành thành công.
- Hủy request từ phía gọi cũng hủy và thu hồi task con. Logging ghi ID, worker, lần thử, trạng thái và thời gian; không ghi nội dung request/kết quả để tránh lộ dữ liệu.
- Timeout asyncio cần worker hợp tác: không chặn event loop bằng tác vụ đồng bộ hoặc nuốt CancelledError. Chưa có cơ chế chấm chất lượng nội dung worker; `success` chỉ xác nhận thực thi không lỗi.
- Standalone chỉ dùng mock, không phải bằng chứng chấp nhận với model thật hoặc kết quả thí nghiệm chính thức của lab.

Các kiểm tra bổ sung bao gồm parse, route, lỗi input, timeout/cancellation, retry cạn, capacity, tổng hợp không mất output và cả hai entry point sync/async.

## Kết quả kiểm chứng

Review bổ sung kiểm tra đồng thời bằng barrier thay vì dựa vào thời gian chạy, và kiểm tra timeout NaN/infinity/boolean bị từ chối trước khi gọi worker. Task ID dùng UUID; đường thu hồi task dọn cả task chưa kịp bắt đầu.

Trên Windows/Python 3.11.9: test coordinator ban đầu đạt 9/9; standalone đạt 3/3. Toàn bộ suite ở thời điểm review đạt 22 và thất bại 16: các lỗi đều đến từ TODO có sẵn trong `agent.py`, `subagents.py`, `runner.py`, `curator.py`. Phần coordinator không hoàn thành thay các TODO đó. Kết quả test coordinator cuối cùng được ghi trong bàn giao.
