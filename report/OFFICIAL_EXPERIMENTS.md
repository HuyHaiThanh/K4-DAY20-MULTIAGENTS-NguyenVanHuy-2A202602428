# Thí nghiệm chính thức OpenAI

Bám theo README.md, GUIDE.md, RUBRIC.md và guides/pseudocode/. Chỉ dùng OpenAI gpt-4.1-mini, endpoint https://api.openai.com/v1, nhiệt độ 0, recursion_limit 40; Deep Agents 0.7.21 trên WSL Python 3.12.3. Configuration.json ghi tham số, không ghi key; .env không được nộp.

Thứ tự: baseline learn → subagents learn → curator → skills-auto learn development → hypotheses commit → freeze commit/tag → baseline/subagents eval → skills-auto all. Ba lượt development giữ tại results/skills-auto-dev. Hai lượt code bị lỗi kiểm tra hash do CRLF được lưu riêng tại openai-attempts/crlf-before-normalization; đã khôi phục byte LF đúng Git blob và chạy lại, không sửa grader hoặc chọn điểm bằng tay.

Curator gọi một lần; prompt/response/usage nguyên bản tại curator/. Không sửa tay skill sau sinh; giữ nguyên skills/auto từ tag freeze. Bảng chính gồm 18 lượt, không gộp development hoặc các lượt trước sửa CRLF. Các lệnh chuẩn nằm trong GUIDE.md; không cần script của phần mở rộng.

Kiểm tra: `pytest tests`, `python scripts/verify_freeze.py`, `python -m lab.compare`, `python scripts/check_breakdown.py`. Kết quả kiểm tra cuối tại acceptance/pytest-final-review.txt và acceptance/submission-audit.json. Không có benchmark Coordinator/Worker, cache hoặc bonus trong bản nộp này. Token usage không tương đương hóa đơn.
