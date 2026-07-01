"""LLM client — uses openai SDK for stable JSON mode support."""
from __future__ import annotations

import json
import re
from typing import Any

import config


def _get_client():
    from openai import OpenAI
    return OpenAI(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_API_BASE.rstrip("/") + "/v1",
        timeout=config.LLM_TIMEOUT,
    )


def call(messages: list[dict], temperature: float = 0.3,
         json_mode: bool = False) -> str:
    client = _get_client()

    # Do not use response_format to avoid v3.cm triggering tool_calls mode in json_mode
    # Instead, append JSON requirement at the end of the user message
    if json_mode and config.JSON_MODE:
        msgs = [m.copy() for m in messages]
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("role") == "user":
                msgs[i]["content"] = str(msgs[i]["content"]) + "\n\nOutput valid JSON only. No markdown fences."
                break
    else:
        msgs = messages

    kwargs: dict[str, Any] = {
        "model": config.LLM_MODEL,
        "messages": msgs,
        "temperature": temperature,
        "max_tokens": 16384,
    }

    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    finish = choice.finish_reason
    content = choice.message.content or ""

    # finish_reason=tool_calls: model wants to call a tool; extract JSON from tool_calls arguments
    # LLM sometimes returns JSON content inside the Write tool's content field
    if not content and finish == "tool_calls" and choice.message.tool_calls:
        for tc in choice.message.tool_calls:
            args = tc.function.arguments if tc.function else ""
            if args and args.strip():
                # If args is in Write tool format {"content": "...", "file_path": "..."}
                # then extract the actual JSON from the content field
                try:
                    parsed = json.loads(args)
                    if "content" in parsed and "file_path" in parsed:
                        content = parsed["content"]
                    else:
                        content = args
                except Exception:
                    content = args
                break

    if not content:
        raise RuntimeError(f"LLM returned empty content (finish_reason={finish})")

    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```[a-z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content.rstrip())
    return content


def load_prompt(name: str) -> str:
    path = config.PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def sp(name: str) -> str:
    return load_prompt(name)


def sp_with_dsl(name: str) -> str:
    """Load a system prompt and prepend the DSL reference.

    Use this for Stage 2 / Stage 3 calls so the model always has the full
    DSL field definitions before it sees the task-specific instructions.
    """
    dsl = load_prompt("dsl_reference")
    body = load_prompt(name)
    return dsl + "\n\n---\n\n" + body


def up(name: str, **kwargs) -> str:
    template = load_prompt(name)
    # Use str.replace per key to avoid brace-heavy JSON values breaking str.format()
    result = template
    for k, v in kwargs.items():
        result = result.replace("{" + k + "}", str(v))
    return result
