from typing import Any, Dict, List


class LLMProvider:
    def chat(self, messages: List[Dict[str, str]], *, json_mode: bool = False) -> Dict[str, Any]:
        raise NotImplementedError


class MockLLM(LLMProvider):
    def chat(self, messages: List[Dict[str, str]], *, json_mode: bool = False) -> Dict[str, Any]:
        _ = json_mode
        last = messages[-1]["content"] if messages else ""
        if "produce a plan" in last.lower() or "תכנית" in last:
            content = {
                "plan": [
                    {"step": "Collect context", "tool": "read_text", "args": {"path": "README.md"}},
                    {"step": "Draft response", "tool": None, "args": {}},
                ],
                "actions": [],
                "final_output": "Planned successfully",
            }
        else:
            content = {
                "result": "MOCK: Replace MockLLM with a real provider in agentic_runner/llm/provider.py",
                "notes": "This run proves E2E plumbing: spec → tools → logs → final.json",
                "actions": [],
                "plan": [{"step": "Collect context"}],
                "final_output": "MVP complete",
            }
        return {"content": content, "usage": {"tokens_in": None, "tokens_out": None}}
