# Quy trình thí nghiệm chính thức bổ sung

Chạy trong WSL ERPNext, tại thư mục repo, với `.venv-linux/bin/python`.

- Model chọn cho mọi điều kiện: `qwen/qwen3.8-27b` trên endpoint của `.env`; temperature 0.
- `max_tokens=4096`, SDK API retry tối đa 2, timeout 120s, graph recursion 40.
- Profile hữu hiệu cho Deep Agents: `max_input_tokens=11000`; thư viện dự trữ 4096 output và 5%, còn input budget 6354. Đây là cấu hình để thích nghi giới hạn cứng 7000 input token của cổng, không phải context window thực của Qwen.
- Script thêm chỉ gọi `lab.runner.run_task`; prompt hằng số, dữ liệu và grader giữ nguyên. Cơ chế compaction có sẵn được dùng cho mọi điều kiện. `configuration.json` đi kèm mỗi lượt chạy.
- `report/official-attempts/` giữ lỗi trước khi chạy lại. Không đưa run lỗi hạ tầng vào taxonomy hoặc kết luận hiệu quả agent. Chi phí ở đó vẫn là token đã tiêu thụ; usage không bao gồm response bị provider từ chối.

Trình tự:

```bash
python scripts/run_official.py baseline data-learn code-learn logs-learn --model qwen/qwen3.8-27b
python scripts/run_official.py subagents code-learn data-learn logs-learn --model qwen/qwen3.8-27b
python scripts/curate_official.py
# Review nguyên văn skill, chỉ giữ/xóa; không sửa tay.
python scripts/run_official.py skills-auto code-learn data-learn logs-learn --model qwen/qwen3.8-27b
# Điền H1-H3, git commit hypotheses; git commit freeze skills; git tag freeze.
# Sao lưu results/skills-auto thành results/skills-auto-dev trước lượt chính thức.
python scripts/run_official.py baseline code-eval data-eval logs-eval --model qwen/qwen3.8-27b
python scripts/run_official.py subagents code-eval data-eval logs-eval --model qwen/qwen3.8-27b
python scripts/run_official.py skills-auto code-learn data-learn logs-learn code-eval data-eval logs-eval --model qwen/qwen3.8-27b
python scripts/verify_freeze.py
python -m lab.compare > report/table.md
python scripts/check_breakdown.py > report/check-breakdown.txt
```

Script bỏ qua kết quả không có error đã tồn tại, nên khi tiếp tục trên cùng cấu hình không ghi đè bằng lượt tùy ý có điểm cao hơn. Muốn đo nhiễu thêm phải dùng `--results` riêng. Nếu đổi cấu hình, phải lưu riêng kết quả trước đó và chạy lại đầy đủ điều kiện để không trộn model/cấu hình.

Trước freeze, chỉ đọc instruction/check/trace của learn. Runner nhận instruction eval sau freeze. Curator lọc role learn; raw prompt/output và usage được lưu tại `report/curator/`. Không đưa nội dung eval hoặc đáp án vào skill. Quá trình review vẫn phải kiểm tra ngữ nghĩa; validator không chặn mọi chỉ dẫn gian lận (xem bonus-redteam).

Nếu gặp 413 với `Requested > Limit`, chờ không khắc phục request quá lớn. Nếu 429 theo phút, chờ thời gian reset; nếu quota ngày, dùng key được cấp quota phù hợp hoặc đợi ngày tiếp theo. Không tự bật gói trả phí.

## Review metadata SDK

Trong lần bổ sung này phát hiện việc gán model.max_retries/model.request_timeout sau make_model không cấu hình lại SDK client đã khởi tạo: kiểm tra offline cho thấy SDK vẫn retry 2 và timeout 120s. Đã sửa configuration.json của kết quả hiện tại để phản ánh giá trị thực; điểm, tokens và trace không thay đổi. Các manifest cũ trong archive có trường 0/60 khai báo ban đầu, nhưng SDK thực tế là 2/120. Script hiện lấy thông số trực tiếp từ root_client. Một retry code-learn bị dừng khi đang đợi SDK retry sau lỗi context; log giữ nguyên, usage của phần bị dừng không có đủ trong run.json.

## Tiếp tục khi thay API/cấu hình

Script có --profile-input-limit và --max-output-tokens. Với API đã xác nhận cho ít nhất 32000 input/request, có thể chọn profile 33000/output 4096 (input budget 27254); đây là ví dụ cấu hình, chưa được kiểm chứng bằng key hiện tại. Với free API, output phải được giảm để phù hợp limit 1000, nhưng cần kiểm tra lại độ ổn định sinh tool/code và retention trước khi chọn cấu hình cuối. Khi đổi cấu hình, sao lưu toàn bộ kết quả cũ rồi chạy lại, không ghép data-learn hiện tại với điều kiện có cấu hình khác. H1–H3 đã commit d5313da dựa trên học và vẫn trước eval; không sửa auto sau khi tạo freeze.
