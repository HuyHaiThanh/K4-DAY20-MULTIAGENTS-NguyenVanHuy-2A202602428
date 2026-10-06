"""Small bounded tools: no arbitrary eval, shell, or unrestricted SQL."""
import ast
import csv
from io import StringIO
import json
import math
from pathlib import Path
import sqlite3
from langchain_core.tools import StructuredTool


def tool(function, name=None):
    return StructuredTool.from_function(function, name=name or function.__name__)


def csv_parser(text: str) -> list[dict]:
    """Parse CSV text with a header into records (up to 10000 rows)."""
    if len(text) > 1_000_000:
        raise ValueError("CSV is too large")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("CSV needs unique headers")
    rows = list(reader)
    if len(rows) > 10000 or any(None in row or None in row.values() for row in rows):
        raise ValueError("CSV row limit or inconsistent columns")
    return rows


def data_validation(rows: list[dict], required: list[str]) -> dict:
    """Check required fields for missing or empty values in records."""
    if len(rows) > 10000:
        raise ValueError("Too many records")
    issues = [{"row": index, "field": field} for index, row in enumerate(rows)
              for field in required if row.get(field) is None or row.get(field) == ""]
    return {"valid": not issues, "issues": issues}


def data_analysis(rows: list[dict], column: str, operation: str = "sum", group_by: str = "") -> dict:
    """Compute sum, average, or count, optionally grouped by a field; reject dirty numbers."""
    if operation not in ("sum", "avg", "count") or len(rows) > 10000:
        raise ValueError("Unsupported operation or too many rows")
    groups = {}
    for row in rows:
        if group_by and group_by not in row:
            raise ValueError("Missing group column")
        key = str(row[group_by]) if group_by else "all"
        value = 1.0 if operation == "count" else float(row[column])
        if not math.isfinite(value):
            raise ValueError("Nonfinite value")
        groups.setdefault(key, []).append(value)
    return {key: len(values) if operation == "count" else sum(values) / len(values) if operation == "avg" else sum(values)
            for key, values in groups.items()}


def database_tool(database_path):
    path = Path(database_path).resolve(strict=True)
    def query_database(query: str, parameters: list = []) -> list[dict]:
        """Execute a read-only SQLite SELECT with bound parameters; max 1000 result rows."""
        if len(query) > 10000 or not query.lstrip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT is supported")
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 10000)
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
        connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        # Abort after a bounded number of virtual-machine instructions.
        ticks = 0
        def progress():
            nonlocal ticks
            ticks += 1
            return ticks > 1000
        connection.set_progress_handler(progress, 1000)
        try:
            cursor = connection.execute(query, parameters)
            names = [item[0] for item in cursor.description]
            if len(set(names)) != len(names):
                raise ValueError("Use unique column aliases")
            rows, output_bytes = [], 0
            for row in cursor:
                record = dict(zip(names, row))
                output_bytes += len(json.dumps(record, ensure_ascii=False).encode("utf-8"))
                if len(rows) >= 1000 or output_bytes > 1_000_000:
                    raise ValueError("Query result size limit exceeded")
                rows.append(record)
            return rows
        finally:
            connection.close()
    return tool(query_database)


def restricted_python(code: str) -> dict:
    """Execute a limited Python arithmetic subset: assignments, expressions and print; no imports or loops."""
    if len(code) > 10000:
        raise ValueError("Code is too large")
    tree = ast.parse(code)
    if sum(1 for _ in ast.walk(tree)) > 500:
        raise ValueError("Code exceeds node budget")
    variables, output = {}, []
    def expression(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float, str):
            value = node.value
        elif isinstance(node, ast.Name) and node.id in variables:
            value = variables[node.id]
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = expression(node.operand)
            value = operand if isinstance(node.op, ast.UAdd) else -operand
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = expression(node.left), expression(node.right)
            if type(left) not in (int, float) or type(right) not in (int, float):
                raise ValueError("Arithmetic requires numbers")
            if isinstance(node.op, ast.Add): value = left + right
            elif isinstance(node.op, ast.Sub): value = left - right
            elif isinstance(node.op, ast.Mult): value = left * right
            else: value = left / right
        else:
            raise ValueError("Unsupported Python expression")
        if isinstance(value, str) and len(value) > 2000:
            raise ValueError("String limit exceeded")
        if type(value) in (int, float) and (not math.isfinite(value) or abs(value) > 1e100):
            raise ValueError("Numeric limit exceeded")
        return value
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            variables[statement.targets[0].id] = expression(statement.value)
        elif isinstance(statement, ast.Expr):
            call = statement.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print" and not call.keywords:
                output.append(" ".join(str(expression(arg)) for arg in call.args))
            else:
                output.append(str(expression(call)))
        else:
            raise ValueError("Unsupported Python statement")
    return {"stdout": "\n".join(output), "variables": variables, "restricted": True}


def file_tools(workspace):
    root = Path(workspace).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Workspace must be a directory")
    def safe_path(path):
        relative = Path(path)
        if relative.is_absolute() or relative.drive:
            raise ValueError("Use a relative path")
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or target == root:
            raise ValueError("Path escapes workspace")
        return target
    def create_file(path: str, content: str) -> dict:
        """Create a new UTF-8 file within the supplied workspace, without overwriting."""
        if len(content.encode("utf-8")) > 100000:
            raise ValueError("File size limit exceeded")
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            stream.write(content)
        return {"path": str(target.relative_to(root)), "bytes": target.stat().st_size}
    def edit_file(path: str, old: str, new: str) -> dict:
        """Replace exactly one text occurrence in an existing workspace file."""
        target = safe_path(path)
        if target.stat().st_size > 100000 or not old:
            raise ValueError("File too large or empty search")
        text = target.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise ValueError("Search must match exactly once")
        updated = text.replace(old, new, 1)
        if len(updated.encode("utf-8")) > 100000:
            raise ValueError("File size limit exceeded")
        target.write_text(updated, encoding="utf-8")
        return {"path": str(target.relative_to(root)), "edited": True}
    def run_script(path: str) -> dict:
        """Run a workspace script using the restricted arithmetic Python interpreter."""
        target = safe_path(path)
        if target.stat().st_size > 10000:
            raise ValueError("Script size limit exceeded")
        return restricted_python(target.read_text(encoding="utf-8"))
    return [tool(create_file), tool(edit_file), tool(run_script)]


def scoring(accuracy: float, completeness: float, clarity: float, performance: float) -> dict:
    """Weight supplied rubric ratings (0-100) as 30/30/20/20; does not prove factual correctness."""
    scores = [accuracy, completeness, clarity, performance]
    if any(not math.isfinite(v) or not 0 <= v <= 100 for v in scores):
        raise ValueError("Ratings must be finite and between 0 and 100")
    return {"score": round(sum(v * weight for v, weight in zip(scores, (0.3, 0.3, 0.2, 0.2))), 2)}


def validation(result: dict, required: list[str]) -> dict:
    """Validate presence of required output fields."""
    missing = [name for name in required if name not in result or result[name] is None]
    return {"valid": not missing, "missing": missing}


def quality_check(text: str, requirements: list[str]) -> dict:
    """Check literal requirement mentions; this is a heuristic, not a factual evaluator."""
    missing = [word for word in requirements if word.casefold() not in text.casefold()]
    return {"complete": not missing, "missing": missing}


def feedback_generator(issues: list[str], suggestions: list[str]) -> dict:
    """Format explicit issues and improvement suggestions without inventing findings."""
    return {"feedback": "Issues found" if issues else "No supplied issues", "issues": issues, "suggestions": suggestions}
