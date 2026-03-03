import json
import os
from typing import Any, Dict, List


SYSTEM_PROMPT = """
You are an action-oriented agent. You MUST respond with valid JSON only.
Output format: {"plan": [...], "actions": [{"tool": "...", "args": {...}}], "final_output": "..."}.
Available tools: read_text(path), write_text(path, text), run_cmd(cmd: array of strings).
All file paths are relative to the workspace. Be concise. Use the minimum number of actions.
""".strip()


class LLMProvider:
    def chat(self, messages: List[Dict[str, str]], *, json_mode: bool = False) -> Dict[str, Any]:
        raise NotImplementedError


class MockLLM(LLMProvider):
    def chat(self, messages: List[Dict[str, str]], *, json_mode: bool = False) -> Dict[str, Any]:
        _ = json_mode
        last = messages[-1]["content"] if messages else ""
        if "run pytest" in last.lower() or "run tests" in last.lower():
            content = {
                "plan": [
                    {"step": "Run tests in workspace"},
                ],
                "actions": [
                    {"tool": "run_cmd", "args": {"cmd": ["pytest", "-q"]}},
                ],
                "final_output": "Test run completed",
            }
        else:
            content = {
                "plan": [
                    {"step": "Collect context"},
                    {"step": "Summarize findings"},
                ],
                "actions": [],
                "final_output": "MVP complete",
            }
        return {"content": content, "usage": {"tokens_in": None, "tokens_out": None}}


class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat(self, messages: List[Dict[str, str]], *, json_mode: bool = False) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**params)
        content = response.choices[0].message.content or "{}"
        usage = {
            "tokens_in": response.usage.prompt_tokens if response.usage else None,
            "tokens_out": response.usage.completion_tokens if response.usage else None,
        }

        parsed_content = json.loads(content)
        if not isinstance(parsed_content, dict):
            parsed_content = {"final_output": str(parsed_content), "actions": [], "plan": []}

        return {
            "content": parsed_content,
            "usage": usage,
        }


def provider_from_name(name: str) -> LLMProvider:
    if name == "mock":
        return MockLLM()
    if name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for openai provider")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return OpenAILLM(api_key=api_key, model=model)
    raise ValueError(f"Unknown LLM provider: {name}")
