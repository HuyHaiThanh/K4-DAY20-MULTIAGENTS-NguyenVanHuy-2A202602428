# Phần 5: Test, debug và hiệu suất

## Phạm vi

Hoàn thiện các TODO được phép của harness gốc: `make_backend`, `build_agent`, `get_subagents`, `run_task`, `curate_skills`. Giữ nguyên prompt constants, renderer, CLI và các test/bộ chấm được cung cấp. Đồng thời bổ sung `MultiAgentSystem` nối extension Phần 2–4, test integration/e2e/concurrency, benchmark, debug và profiling. Không chạy tác vụ đánh giá thật trước freeze, không sinh skill từ benchmark extension.

`MultiAgentSystem` dùng fixture local Jan=10, Feb=20 và rubric được cung cấp. Model quyết định tool calls; kết quả SQL, tổng stdout, SVG và score được đối chiếu độc lập. Không nhận diện mọi yêu cầu tự nhiên hoặc truy vấn dữ liệu doanh nghiệp ngoài fixture. Complex chạy theo thứ tự phụ thuộc data → code → evaluation; mỗi request có model/worker/DB/workspace riêng.

## Lệnh tái lập

```bash
python -m pytest --durations=10
python scripts/debug_system.py
python scripts/debug_agent.py --agent data_agent --task 'Query supplied sales rows'
python scripts/profile_system.py
python scripts/benchmark.py --output report/acceptance/benchmark-offline-final.json
# Opt-in API thật, tốn quota:
python scripts/benchmark.py --live --pace-seconds 5 --output report/acceptance/benchmark-live-final.json
```

Harness gốc có shell Linux: dùng WSL/Docker. Venv `.venv-linux` đã được tạo trong workspace trên WSL ERPNext; không sửa Python hệ thống. Windows dùng `.venv/Scripts/python.exe` cho extension. Coverage là công cụ kiểm chứng cài riêng vào venv, không phải dependency runtime:

```bash
python -m coverage run --source=lab -m pytest
python -m coverage report
```

## Debug và các lỗi đã xử lý

1. 16 lỗi TODO ban đầu: hoàn thiện đúng pseudo-code; test gốc vẫn giữ nguyên.
2. Hai lỗi `which`/`cat` trên Windows: chạy suite Linux nguyên bản trong WSL; không thêm fake shell hoặc sửa test để báo pass.
3. API `OpenAIConnectionError` trong sandbox: probe ngoài sandbox bằng `.env` được người dùng cho phép đã thành công. Benchmark các lỗi mạng giữ riêng ở `benchmark-live.json`; benchmark có quyền mạng ở `benchmark-live-network.json`.
4. Evaluator live gọi tool `json` không tồn tại và có timeout: thêm tool cuối `submit_evaluation` với schema strict, prompt chỉ rõ score_result → submit_evaluation; terminal tool kết thúc vòng model. Giảm context evaluator xuống dữ liệu/bằng chứng tóm tắt thay vì toàn bộ trace lồng nhau. Giữ các lần lỗi làm bằng chứng.
5. Child Python chậm vì import package agent/LangChain: tách interpreter thành module stdlib-only; vẫn giữ AST/input/output budget và kill/reap trên timeout. Cache adapter cho hàm tool để giảm dựng schema lặp lại, không chia sẻ state request/model.

Logs debug ở `report/acceptance/debug.log` và `logs/`; mỗi run lưu `run.json`, `communication.jsonl` và artifacts. Profiling lưu `profile.txt`; cumulative time của event loop chứa thời gian chờ, không được diễn giải là CPU đang bận. Các input/tool output trong trace có thể chứa dữ liệu tác vụ; không chứa API key và không lưu `.env`.

## Cách đọc metrics

- Latency đo bằng monotonic từ request bắt đầu đến kết quả; P50/median dùng đúng median cả số mẫu chẵn; percentile nội suy.
- Throughput dựa trên toàn bộ cửa sổ đo, có cả pacing nếu bật; báo cả attempted và successful requests/minute.
- Worker busy fraction = tổng thời gian từng worker / (wall time × concurrency cấu hình). Đây là phần thời gian chiếm slot bao gồm chờ LLM, không phải CPU utilization hoặc xác nhận target 70–90%.
- Token lấy UsageMetadataCallbackHandler. Offline là synthetic token do fake model, không tính chi phí API. Lỗi/timeout có thể thiếu usage provider; có cờ `token_usage_complete`, không coi số 0 là chắc chắn không bị tính phí.
- Ba mẫu/nhóm chỉ mô tả lần đo nhỏ, không đủ suy rộng P99, error rate <1%, hoặc độ ổn định production. Live latency/throughput chịu quota và pacing; không extrapolate token/100 request như con số đã đo.
- Score evaluator là weighted supplied ratings; không phải xác suất accuracy hoặc điểm chính thức của sáu tác vụ lab.

Các số liệu cuối nằm trong mục 5–6 của `REPORT.md` và JSON/log đi kèm. Benchmark trước tối ưu, sau tối ưu và live được giữ riêng để tránh ghi đè lịch sử.
