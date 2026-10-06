from pydantic import Field
from .base_tool import BaseTool, ToolInput
from lab.agents.tools import database_tool


class QueryInput(ToolInput):
    query: str = Field(min_length=1, max_length=10000)
    parameters: list = Field(default_factory=list, max_length=100)
    limit: int = Field(default=1000, ge=1, le=1000)


class QueryDatabaseTool(BaseTool):
    name = "query_database"
    description = "Read-only SQLite SELECT with bound parameters, instruction budget and at most 1000 rows"
    schema = QueryInput

    def __init__(self, connection_string):
        self._query = database_tool(connection_string)

    def _execute(self, values):
        rows = self._query.invoke({"query": values["query"], "parameters": values["parameters"]})
        selected = rows[:values["limit"]]
        return {"rows": len(selected), "data": selected,
                "columns": list(selected[0]) if selected else [], "truncated": len(rows) > len(selected)}
