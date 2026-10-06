"""An API failure after a successful tool must preserve the completed trace."""
from langchain_core.messages import AIMessage
from lab.runner import run_task
from lab.testing import ScriptedChatModel


def test_partial_run_retains_tool_and_trace(tmp_path):
    class FailAfterWrite(ScriptedChatModel):
        def _generate(self, *args, **kwargs):
            if self.calls:
                raise RuntimeError("provider unavailable after write")
            return super()._generate(*args, **kwargs)

    model = FailAfterWrite(script=[AIMessage(content="", tool_calls=[{
        "name": "write_file", "args": {"file_path": "workspace/answer.json",
                                       "content": '{"duplicate_rows_removed": 7}'}, "id": "partial-1"}])])
    record = run_task("data-learn", "baseline", results_dir=tmp_path, model=model)
    assert "provider unavailable" in record["error"]
    assert record["passed"] == 1 and record["tool_calls"] == 1
    trace = (tmp_path / "baseline/data-learn/trace.md").read_text(encoding="utf-8")
    assert "write_file" in trace and "Tool result" in trace
    assert record["tokens"]["total"] == 120


def test_live_model_limits_reach_actual_sdk_clients(monkeypatch, tmp_path):
    from langchain_openai import ChatOpenAI
    from lab.system import MultiAgentSystem
    from lab import model as model_module
    chat = ChatOpenAI(model="test", api_key="dummy-not-a-real-key",
                      base_url="http://127.0.0.1:1/v1", timeout=120)
    monkeypatch.setattr(model_module, "make_model", lambda: chat)
    configured = MultiAgentSystem(tmp_path, live=True)._model([], "")
    assert configured.max_tokens == 700 and configured.request_timeout == 20
    for client in (configured.root_client, configured.root_async_client):
        assert client.max_retries == 0 and client.timeout == 20
