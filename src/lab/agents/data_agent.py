from .base_worker import BaseWorker
from .tools import tool, csv_parser, data_analysis, data_validation, database_tool


class DataAgent(BaseWorker):
    def __init__(self, model, database_path=None, **kwargs):
        tools = [tool(csv_parser), tool(data_analysis), tool(data_validation)]
        if database_path is not None:
            tools.append(database_tool(database_path))
        super().__init__("data_agent", model, tools, **kwargs)
        self.system_prompt = (
            "You are a Data Analysis Specialist. Inspect supplied data, validate missing values, "
            "then compute aggregates using tools. Use bound parameters with read-only SQL if available. "
            "Report verified insights and limitations; never invent data or silently drop dirty values. "
            "The analysis tool supports sum, avg, count and grouping, not arbitrary pandas expressions."
        )
