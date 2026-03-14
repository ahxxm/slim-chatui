import json


def extract_task_text(res: dict) -> str:
    """Extract text (skip reasoning) from Completions and Responses.
    LiteLLM proxies may convert extended thinking (e.g. Claude) into
    reasoning_content (Chat Completions) or reasoning output items (Responses API).
    We skip those and return only the actual text output.
    """
    # Chat Completions: choices[0].message.content (not reasoning_content)
    choices = res.get("choices") or []
    if len(choices) == 1:
        msg = choices[0].get("message") or {}
        return msg.get("content", "")
    # Responses API: first non-reasoning output_text
    for item in res.get("output") or []:
        if item.get("type") == "reasoning":
            continue
        for block in item.get("content") or []:
            if block.get("type") == "output_text":
                return block.get("text", "")
    return ""


def parse_task_json(res, key, default):
    """Extract task text from LLM response, parse JSON, return value for key."""
    if not isinstance(res, dict):
        return default
    text = extract_task_text(res)
    text = text[text.find("{") : text.rfind("}") + 1]
    if not text:
        return default
    return json.loads(text).get(key, default)


def normalize_usage(usage: dict) -> dict:
    """
    Normalize usage statistics to standard format.
    Handles OpenAI Chat Completions and Responses API formats.

    Adds standardized token fields to the original data:
    - input_tokens: Number of tokens in the prompt
    - output_tokens: Number of tokens generated
    - total_tokens: Sum of input and output tokens
    """
    if not usage:
        return {}

    input_tokens = (
        usage.get("input_tokens")  # Responses API
        or usage.get("prompt_tokens")  # OpenAI Chat Completions
        or 0
    )

    output_tokens = (
        usage.get("output_tokens")  # Responses API
        or usage.get("completion_tokens")  # OpenAI Chat Completions
        or 0
    )

    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)

    result = dict(usage)
    result["input_tokens"] = int(input_tokens)
    result["output_tokens"] = int(output_tokens)
    result["total_tokens"] = int(total_tokens)

    return result
