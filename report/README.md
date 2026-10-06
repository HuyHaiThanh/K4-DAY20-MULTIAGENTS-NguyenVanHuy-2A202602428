# Hồ sơ bàn giao

- [FINAL_REPORT.md](FINAL_REPORT.md): 10 mục theo checklist Phần 6 gửi thêm, có kiến trúc, test, metrics thật và bonus.
- [REPORT.md](REPORT.md): mẫu báo cáo repo gốc, giữ các mục chưa có thí nghiệm chính thức và bổ sung kết quả extension.
- [TESTING.md](TESTING.md): tái lập test/debug/profile/benchmark; [TOOLS.md](TOOLS.md), [WORKERS.md](WORKERS.md), [COORDINATOR.md](COORDINATOR.md): thiết kế và giới hạn.
- [acceptance/summary.json](acceptance/summary.json): checkpoint Phần 5; full gate Phần 6 ở [pytest-linux.txt](acceptance/pytest-linux.txt), [coverage-linux.txt](acceptance/coverage-linux.txt).
- [bonus-cache/benchmark.json](bonus-cache/benchmark.json): số đo bonus riêng, không trộn benchmark chính thức.

Repo gốc yêu cầu thêm learning/curator/freeze/evaluation; các file bàn giao này không chứng minh đã hoàn thành bước đó. Không dùng số liệu ví dụ trong văn bản hoặc score rubric cung cấp để thay điểm `check.py`.

- [OFFICIAL_EXPERIMENTS.md](OFFICIAL_EXPERIMENTS.md): quy trình bổ sung thí nghiệm gốc, cấu hình SDK thực và trở ngại context.
- [bonus-redteam/README.md](bonus-redteam/README.md): bonus GUIDE 6c, bốn probe offline và giới hạn ngữ nghĩa validator.
- Gate cuối: log/XML/summary-final.json đồng nhất 85 pass, coverage 89,22%; summary-phase6.json giữ snapshot 83 pass ban đầu.
