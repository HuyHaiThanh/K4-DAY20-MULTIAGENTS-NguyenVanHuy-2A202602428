import json
import math
from pydantic import Field
from .base_tool import BaseTool, ToolInput
from .code_tools import CreateFileTool


class ScoreInput(ToolInput):
    scores: dict[str, float]
    criteria: dict[str, float] = Field(default_factory=lambda: {"accuracy": 30.0, "completeness": 30.0, "clarity": 20.0, "performance": 20.0})


class ScoringTool(BaseTool):
    name = "score_result"
    description = "Compute weighted grade from explicit evidence-backed criterion scores; never infer accuracy from text length"
    schema = ScoreInput
    def _score_to_grade(self, score):
        return "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    def _execute(self, values):
        scores, criteria = values["scores"], values["criteria"]
        if not criteria or set(criteria) != set(scores) or len(criteria) > 20:
            raise ValueError("Every criterion must have exactly one supplied score")
        if any(not math.isfinite(v) or v < 0 for v in criteria.values()) or sum(criteria.values()) <= 0:
            raise ValueError("Weights must be finite, nonnegative and sum to a positive value")
        if any(not math.isfinite(v) or not 0 <= v <= 100 for v in scores.values()):
            raise ValueError("Scores must be finite and within 0-100")
        score = sum(scores[key] * weight / sum(criteria.values()) for key, weight in criteria.items())
        return {"scores": scores, "weighted_score": round(score, 2), "grade": self._score_to_grade(score), "basis": "supplied_ratings"}


class ValidateInput(ToolInput):
    result: dict
    required: list[str] = Field(max_length=100)


class ValidationTool(BaseTool):
    name = "validate_result"
    description = "Check required fields without claiming factual accuracy"
    schema = ValidateInput
    def _execute(self, values):
        missing = [key for key in values["required"] if key not in values["result"] or values["result"][key] is None]
        return {"valid": not missing, "missing": missing}


class CompareInput(ToolInput):
    actual: object
    expected: object


class ComparisonTool(BaseTool):
    name = "compare_results"
    description = "Compare actual and explicit expected JSON values for exact equality"
    schema = CompareInput
    def _execute(self, values):
        # JSON type-sensitive equality: bool True must not equal numeric 1.
        actual = json.dumps(values["actual"], sort_keys=True, allow_nan=False)
        expected = json.dumps(values["expected"], sort_keys=True, allow_nan=False)
        return {"matches": actual == expected}


class ReportInput(ToolInput):
    path: str = Field(min_length=1, max_length=240)
    title: str = Field(max_length=200)
    findings: list[str] = Field(max_length=100)
    evaluation: dict


class ReportGeneratorTool(CreateFileTool):
    name = "generate_report"
    description = "Write a new Markdown report with supplied findings and evaluation; no fabricated claims"
    schema = ReportInput
    def _execute(self, values):
        if not values["path"].endswith(".md"):
            raise ValueError("Report requires .md extension")
        content = "# " + values["title"] + "\n\n" + "\n".join("- " + item for item in values["findings"])
        content += "\n\n```json\n" + json.dumps(values["evaluation"], ensure_ascii=False, indent=2, allow_nan=False) + "\n```\n"
        return self._tool.invoke({"path": values["path"], "content": content})


class EvaluationInput(ToolInput):
    score: float = Field(ge=0, le=100, allow_inf_nan=False)
    feedback: str = Field(max_length=2000)
    issues: list[str] = Field(max_length=30)
    suggestions: list[str] = Field(max_length=30)


class SubmitEvaluationTool(BaseTool):
    name = "submit_evaluation"
    description = "Submit the final validated evaluation after score_result; use this tool rather than an invented json tool"
    schema = EvaluationInput
    def _execute(self, values):
        return {"result": values}
