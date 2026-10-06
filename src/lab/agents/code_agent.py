from .base_worker import BaseWorker


class CodeAgent(BaseWorker):
    def __init__(self, model, workspace, **kwargs):
        from lab.tools import PythonREPLTool, CreateFileTool, EditFileTool, RunScriptTool, VisualizationTool
        tools = [PythonREPLTool(), CreateFileTool(workspace), EditFileTool(workspace), RunScriptTool(workspace), VisualizationTool(workspace)]
        super().__init__("code_agent", model, [item.as_langchain_tool() for item in tools], **kwargs)
        self.system_prompt = (
            "You are a Code Generation Specialist. Create or edit files only inside the supplied workspace. "
            "Test supported code with python_repl or run_script before claiming it works. "
            "Execution is restricted to numeric arithmetic, assignments and print: no imports, loops, "
            "attributes, shell or network. You may write other source code but must label it unexecuted. "
            "Use create_visualization for trusted SVG charts without importing graphics libraries. "
            "Report only files actually created and actual tool output."
        )

    async def process_async(self, task_content, parameters=None):
        response = await super().process_async(task_content, parameters)
        names = response["metadata"]["tool_names"]
        response["metadata"]["execution_verified"] = any(name in ("python_repl", "run_script") for name in names)
        return response
