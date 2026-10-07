"""Assemble the report from actual run records. Never reads evaluation before freeze."""
import json
import subprocess
from pathlib import Path
from statistics import mean

root = Path.cwd()
frozen = subprocess.run(["git", "rev-parse", "--verify", "refs/tags/freeze"], capture_output=True).returncode == 0
conditions = ("baseline", "subagents", "skills-auto")
runs = {}
for condition in conditions:
    for path in (root / "results" / condition).glob("*/run.json"):
        if path.parent.name.endswith("-eval") and not frozen:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        runs[condition, record["task"]] = record
dev = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
       for p in (root / "results/skills-auto-dev").glob("*/run.json")}
freeze = subprocess.check_output(["git", "rev-parse", "freeze"], text=True).strip() if frozen else "Chưa tạo"
complete = len(runs) == 18 and all(r["error"] is None and r["tokens"]["total"] > 0 for r in runs.values())
skills = sorted((root / "skills/auto").glob("*/SKILL.md"))
total_tokens = sum(r["tokens"]["total"] for r in runs.values()) + sum(r["tokens"]["total"] for r in dev.values())
attempts = [json.loads(p.read_text(encoding="utf-8")) for p in (root / "report/openai-attempts").rglob("run.json")]
curator = json.loads((root / "report/curator/run.json").read_text())
curator_tokens = sum(v["total_tokens"] for v in curator["usage"].values())
all_tokens = total_tokens + sum(r["tokens"]["total"] for r in attempts) + curator_tokens + 11
lines = ["# Báo cáo Lab: Self evolving Agentic", "",
    "Báo cáo theo README.md, GUIDE.md, RUBRIC.md và REPORT_TEMPLATE.md. Chỉ phân tích bộ thí nghiệm OpenAI hiện tại; key không được ghi trong báo cáo.", "",
    "## 1. Thông tin nhóm và cấu hình", "",
    "| Họ tên theo tên repo | Mã sinh viên theo tên repo | Phần đóng góp |",
    "|---|---|---|", "| Nguyễn Văn Huy | 2A202602428 | Các hàm TODO harness; thí nghiệm, review và báo cáo. Mã provided không phải đóng góp mới. |", "",
    "- OpenAI `gpt-4.1-mini`, endpoint `https://api.openai.com/v1`, temperature 0, recursion_limit 40 cho mọi điều kiện.",
    "- Deep Agents 0.7.21; Python 3.12.3 trên WSL Linux. make_model provided giữ nguyên: SDK retry 2, timeout 120s; không ép profile context.",
    f"- Kết quả chính: {len(runs)}/18; development: {len(dev)}/3; lượt lưu riêng: {len(attempts)}; curator: 1 lần. Usage ghi nhận gồm probe/curator/dev/attempts: {all_tokens:,} token.",
    f"- Commit freeze: `{freeze}`. Trạng thái: {'đủ 18 lượt không lỗi' if complete else 'checkpoint đang hoàn thiện'}. Metadata/lệnh chạy tại OFFICIAL_EXPERIMENTS.md.", "",
    "## 2. Giả thuyết (commit TRƯỚC tag freeze)", "",
    "Giả thuyết dưới đây được lập trước mọi lượt eval. Căn cứ chỉ từ learn và guides/pseudocode/02_subagents.md, 04_curator.md, 05_skill_quality.md; không dùng kết quả eval để sửa dự đoán.", "",
    "- H1 (subagents so với baseline): subagents không chắc cải thiện điểm eval; dự đoán token trung bình tăng. Learn code không tăng điểm, data giảm khi tác tử chính chỉ đọc output của implementer mà không kiểm chứng tính toán. Cô lập ngữ cảnh và delegation tạo thêm chi phí.",
    "- H2 (skills-auto so với baseline): dự đoán cải thiện có giới hạn và không bảo đảm cao nhất ở eval. Skill code nhắc type hints/tests/changelog, nhưng không giữ tên file/heading cụ thể; skill data thiếu cent/meta/clean.csv và skill logs thiếu schema_version/generated_by. 04_curator.md cũng lưu ý skill tự sinh có thể không có lợi.",
    "- H3 (tác vụ học so với tác vụ đánh giá): lợi ích của skill trên learn dự đoán lớn hơn eval vì eval thêm quy ước mới. 05_skill_quality.md giải thích skill chỉ giúp khi được đọc và thực hiện; skill hiện có khá chung chung, nên kỳ vọng transfer yếu và nhiễu một lần chạy đáng kể.", "",
    "## 3. Làm quen Deep Agents", "",
    "1. Công cụ mặc định: ls, read_file, write_file, edit_file, delete, glob, grep; execute chạy shell; task giao việc. Tour thật ngoại tuyến lưu tại tour.txt.",
    "2. baseline/skills-auto có tác tử chính và general-purpose mặc định. subagents bổ sung explorer (đọc đặc tả), implementer (thực hiện), reviewer (kiểm tra): tổng 5 vai trò sẵn có, số invocation tùy quyết định agent. task nhận subagent_type và description; subagent stateless chỉ thấy prompt được giao, trả báo cáo về luồng chính. Agent chính phải truyền đủ quy tắc và kiểm chứng kết quả.",
    "3. Trích task: “Put full detail in the prompt and state exactly what it should return”. Trích execute: “Use read_file rather than cat/head/tail.” Default system prompt của Deep Agents rỗng; harness truyền BASE_PROMPT provided. Công cụ chung là backend file/shell; custom subagent không tự thừa kế skill của tác tử chính.", "",
    "## 4. Đường cơ sở và phân loại lỗi", "",
    "Chỉ dùng baseline learn hợp lệ sau sửa lỗi line endings. Các lượt code có CRLF được giữ riêng, không dùng false failure tests_not_modified để quy lỗi agent.", "",
    "| Tác vụ | Check thất bại | Nhóm | Bằng chứng từ detail/trace |", "|---|---|---|---|"]
groups = {}
for (condition, task), record in sorted(runs.items()):
    if condition != "baseline" or record["role"] != "learn":
        continue
    for check in record["checks"]:
        if check["passed"]:
            continue
        group = "E" if check["name"].startswith("rule_") else "D" if task == "logs-learn" else "G"
        groups[group] = groups.get(group, 0) + 1
        detail = str(check["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {task} | {check['name']} | {group} | {detail} |")
base_learn = [r for (c, _), r in runs.items() if c == "baseline" and r["role"] == "learn"]
tech = [k for r in base_learn for k in r["checks"] if not k["name"].startswith("rule_")]
lines += ["", f"Phân bố lỗi: {groups}. Check kỹ thuật baseline learn đạt {sum(k['passed'] for k in tech)}/{len(tech)}. Quy ước E chiếm nhiều nhất; không coi mọi lỗi là thiếu quy ước.",
    "Logs có bằng chứng A/B đi kèm các check D: trace không đọc README dù instruction yêu cầu và không gọi execute để parse/kiểm chứng; số entry, timestamp, exception, repeat và tổng service đều sai. Code đã đọc docstring, sửa hàm dùng chung và chạy test đạt; data dùng Python để tính. Vì vậy không quy A–D cho toàn bộ tác vụ. Không có bằng chứng F về tệp bị báo tạo nhưng không tồn tại trong baseline hợp lệ.", "",
    "## 5. Điều kiện subagents", "",
    "Ba subagent tự định nghĩa có scope rõ: explorer chỉ đọc, implementer chỉ sửa phần được giao và test, reviewer kiểm tra độc lập không sửa. Các role và PATHS_NOTE giữ nguyên giữa learn/eval.", "",
    "| Learn | baseline token / giây | subagents token / giây | task calls |", "|---|---:|---:|---:|"]
for task in ("code-learn", "data-learn", "logs-learn"):
    b, s = runs.get(("baseline", task)), runs.get(("subagents", task))
    if b and s:
        lines.append(f"| {task} | {b['tokens']['total']:,} / {b['seconds']} | {s['tokens']['total']:,} / {s['seconds']} | {s['subagent_calls']} |")
lines += ["", "Code learn không giao việc: tác tử chính tự sửa và chạy test. Data gọi implementer, truyền yêu cầu tính toán và file đầu ra; chính agent chỉ read_file answer.json rồi kết thúc, không đối chiếu phép tính độc lập, điểm 1/8. Logs gọi general-purpose; mô tả có quy tắc parse nhưng không đầy đủ JSON schema/example. Subagent trả lời đang chuẩn bị xử lý, agent chính lại ghi dữ liệu ví dụ và không kiểm chứng, điểm 1/9. Trace không chứa nội bộ subagent: không khẳng định subagent đã chạy một lệnh nếu không thấy bằng chứng luồng chính.", "",
    "## 6. Self-evolving: skill do curator sinh", "",
    "Curator gọi OpenAI một lần, 3 skill được validator chấp nhận, không xóa/chạy lại hoặc sửa tay. Raw prompt/response/usage ở curator/. Review giữ các skill vì không có chỉ dẫn gây hại; ghi nhận thiếu quy tắc cụ thể thay vì chỉnh tay để tăng điểm.", "",
    "| Skill | Tổng quát / đúng và hạn chế | Độ dài / tình huống đọc |", "|---|---|---|"]
notes = {"code-style-enforcement": "Tổng quát; đúng về annotation/test/changelog nhưng không chỉ rõ tests/test_regressions.py, số test hay heading/bullet cần có.",
    "data-cleaning-and-normalization": "Đúng quy trình normalize/date/dedup/giá trị thiếu; thiếu cent, meta và clean.csv. Giữ first occurrence cần kiểm tra lại ở dữ liệu mới có xung đột.",
    "log-file-parsing-and-aggregation": "Đúng các bước severity/UTC/repeat/exception; thiếu cách đổi '-' thành '_', thứ tự sort cụ thể và schema_version/generated_by."}
for path in skills:
    text = path.read_text(encoding="utf-8")
    body = text.split("---", 2)[2].strip().splitlines()
    desc = next(x.split(":", 1)[1].strip() for x in text.splitlines() if x.startswith("description:"))
    lines.append(f"| {path.parent.name} | {notes[path.parent.name]} | {len(text.splitlines())} dòng tổng / {len(body)} dòng body; {desc} |")
lines += ["", "Description theo tình huống rộng, body 3–6 bullet, không chứa đáp án hoặc định danh eval. Validator không thay thế review ngữ nghĩa; skill có thể hợp lệ nhưng quá chung chung để sửa rule_. Skill-read và hiệu quả thực tế được đối chiếu ở mục 8.", "",
    "## 7. Kết quả so sánh", ""]
if complete:
    lines += [(root / "report/table.md").read_text(encoding="utf-8"), "", "```text", (root / "report/check-breakdown.txt").read_text(), "```", "",
        "18 run cuối không lỗi API/graph và skills_modified=false. Hai lượt code trước sửa CRLF chỉ thuộc attempts, không nằm trong bảng. Nếu có lượt graph/API lỗi sau freeze, xem openai-attempts và OFFICIAL_EXPERIMENTS.md; bảng chỉ dùng lượt hoàn tất."]
else:
    lines += ["Chưa lập bảng chính thức khi bộ thí nghiệm chưa đủ; không dùng số minh họa thay kết quả."]
lines += ["", "## 8. Phân tích", "", "Phân tích cuối sẽ được điền sau đủ 18 lượt và verify_freeze, không suy diễn từ development như thể đó là điểm eval.", "",
    "## 9. Hạn chế và tính hợp lệ", "",
    "1. Chỉ ba tác vụ mỗi role, mỗi condition một lượt: không đủ ước lượng phương sai hoặc kết luận thống kê về khả năng tổng quát.",
    "2. Nhiệt độ 0 không bảo đảm kết quả giống nhau; điểm development/post-freeze cùng skill là kiểm tra nhiễu nhỏ, không phải nhiều lần lặp độc lập.",
    "3. Quy ước Acme và dữ liệu do giảng viên thiết kế; lợi ích học rule_ không đại diện toàn bộ tác vụ thực tế hoặc mọi model.",
    "4. Trace chỉ luồng chính, bị renderer cắt mỗi message 1500 ký tự; token cộng cả subagent nhưng không đủ để dựng lại mọi thao tác nội bộ.",
    "5. CRLF Windows làm check hash sai; đã trả đúng blob LF và rerun thay vì sửa grader/điểm. Token usage không phải hóa đơn, lượt API lỗi có thể thiếu usage.", "",
    "## 10. Kết luận", "", "Chỉ kết luận cuối khi bộ thí nghiệm và review hoàn tất.", "",
    "## Phụ lục", "", "Lệnh và thứ tự: TESTING.md, OFFICIAL_EXPERIMENTS.md. Bonus GUIDE 6c ngoại tuyến ở bonus-redteam/README.md; model scripted chứng minh giới hạn validator, không đo xác suất tấn công OpenAI thành công. Extension độc lập chỉ được kiểm chứng offline và không thay điểm thí nghiệm gốc.", ""]
(root / "report/REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("Report assembled; complete:", complete, "runs:", len(runs), flush=True)
