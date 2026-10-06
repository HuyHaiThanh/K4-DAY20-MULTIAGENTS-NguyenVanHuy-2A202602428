"""GUIDE Phần 1 - Định nghĩa subagent (tác tử con).   >>> SINH VIÊN CÀI ĐẶT <<<

Pseudo-code: guides/pseudocode/02_subagents.md
Kiểm tra:    pytest tests/test_02_agent.py
"""


def get_subagents() -> list[dict]:
    """Trả về danh sách subagent (ít nhất 2, tên khác nhau).

    Mỗi phần tử là một dict có các khóa bắt buộc:
      "name":          tên duy nhất (chữ thường, có thể có dấu gạch ngang)
      "description":   khi nào tác tử chính nên giao việc cho subagent này (viết như một hướng dẫn hành động)
      "system_prompt": chỉ dẫn cho subagent
    Gợi ý vai trò: explorer (đọc và báo cáo), implementer (thực hiện), reviewer (kiểm tra độc lập).
    """
    return [
        {"name": "explorer", "description": "Use before making changes when specifications, docstrings or data formats need inspection.",
         "system_prompt": "Inspect the supplied paths and specifications. Do not edit files. Report facts, edge cases and uncertainties with evidence."},
        {"name": "implementer", "description": "Use to implement a bounded change with explicit requirements and verify it using local tests.",
         "system_prompt": "Implement only the assigned change. Read the supplied specifications, fix root causes and run appropriate tests. Report actual changes and results."},
        {"name": "reviewer", "description": "Use after implementation for independent verification against requirements and edge cases.",
         "system_prompt": "Review outputs independently against all supplied rules. Do not edit files. Run checks where appropriate and report defects with evidence; do not assume success."},
    ]
