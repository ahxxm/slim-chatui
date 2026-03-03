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
