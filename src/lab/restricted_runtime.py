"""Bounded stdlib-only Python interpreter used by isolated child processes."""
import ast
import math


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
