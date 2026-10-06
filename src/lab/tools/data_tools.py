from pydantic import Field
from .base_tool import BaseTool, ToolInput
from lab.agents.tools import csv_parser, data_analysis


class CSVInput(ToolInput):
    text: str = Field(max_length=1_000_000)


class CSVParserTool(BaseTool):
    name = "parse_csv"
    description = "Parse bounded CSV text with unique headers"
    schema = CSVInput
    def _execute(self, values):
        return {"data": csv_parser(values["text"])}


class AggregateInput(ToolInput):
    rows: list[dict] = Field(max_length=10000)
    column: str = Field(min_length=1, max_length=100)
    operation: str = "sum"
    group_by: str = ""


class AggregationTool(BaseTool):
    name = "aggregate_data"
    description = "Compute sum, average or count, with optional grouping; reject nonfinite values"
    schema = AggregateInput
    def _execute(self, values):
        return {"data": data_analysis(**values)}


class PandasTool(AggregationTool):
    name = "pandas_analysis"
    description = "Bounded pandas numeric sum/avg/count; no arbitrary pandas expressions; requires optional pandas"
    def _execute(self, values):
        # Validate with the same contract before invoking the optional dependency.
        data_analysis(**values)
        import pandas as pd
        frame = pd.DataFrame(values["rows"])
        if frame.empty:
            return {"data": {}}
        column, operation, group = values["column"], values["operation"], values["group_by"]
        if operation == "count":
            result = frame.groupby(group, dropna=False).size().to_dict() if group else {"all": len(frame)}
        else:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
            series = frame.groupby(group, dropna=False)[column] if group else frame[column]
            value = series.mean() if operation == "avg" else series.sum()
            result = value.to_dict() if group else {"all": float(value)}
        return {"data": {str(key): float(value) for key, value in result.items()}}
