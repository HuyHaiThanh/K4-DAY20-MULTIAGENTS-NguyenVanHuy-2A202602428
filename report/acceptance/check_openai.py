"""Connection check from GUIDE 0.2; never prints credentials."""
import json
from lab.model import make_model

model = make_model()
print(json.dumps({"model": model.model_name, "endpoint": str(model.openai_api_base)}), flush=True)
reply = model.invoke("Reply with OK")
print(json.dumps({"content": reply.content, "usage": reply.usage_metadata}), flush=True)
