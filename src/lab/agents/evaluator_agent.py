from .base_worker import BaseWorker
from .tools import tool, scoring, validation, quality_check, feedback_generator
import json
import math


class EvaluatorAgent(BaseWorker):
    def __init__(self, model, **kwargs):
        super().__init__("evaluator_agent", model, [tool(scoring), tool(validation), tool(quality_check), tool(feedback_generator)], **kwargs)
        self.system_prompt = (
            "You are a Quality Evaluation Specialist. Evaluate supplied outputs against explicit criteria "
            "and available evidence. Accuracy and completeness weigh 30% each, clarity and performance "
            "20% each. Scoring only weights supplied ratings; literal quality checks do not prove accuracy. "
            "Return JSON with score (0-100), feedback, issues and suggestions. State missing evidence."
        )

    async def process_async(self, task_content, parameters=None):
        response = await super().process_async(task_content, parameters)
        if response["status"] == "success":
            try:
                result = json.loads(response["result"])
                score = result["score"]
                if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100:
                    raise ValueError("Invalid score")
                if not isinstance(result["feedback"], str) or any(
                    not isinstance(result[key], list) or any(not isinstance(item, str) for item in result[key])
                    for key in ("issues", "suggestions")
                ):
                    raise ValueError("Invalid feedback fields")
                response["result"] = result
            except (ValueError, KeyError, TypeError) as exc:
                response.update(status="error", error=f"Invalid evaluator output: {exc}", result=None)
        return response
