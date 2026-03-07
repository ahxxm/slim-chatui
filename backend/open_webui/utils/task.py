import math
import re
from typing import Optional

from open_webui.utils.misc import get_last_user_message, get_messages_content


def get_task_model_id(default_model_id: str, task_model: str, models) -> str:
    if task_model and task_model in models:
        return task_model
    return default_model_id


def replace_prompt_variable(template: str, prompt: str) -> str:
    def replacement_function(match):
        full_match = match.group(
            0
        ).lower()  # Normalize to lowercase for consistent handling
        start_length = match.group(1)
        end_length = match.group(2)
        middle_length = match.group(3)

        if full_match == "{{prompt}}":
            return prompt
        elif start_length is not None:
            return prompt[: int(start_length)]
        elif end_length is not None:
            return prompt[-int(end_length) :]
        elif middle_length is not None:
            middle_length = int(middle_length)
            if len(prompt) <= middle_length:
                return prompt
            start = prompt[: math.ceil(middle_length / 2)]
            end = prompt[-math.floor(middle_length / 2) :]
            return f"{start}...{end}"
        return ""

    # Updated regex pattern to make it case-insensitive with the `(?i)` flag
    pattern = r"(?i){{prompt}}|{{prompt:start:(\d+)}}|{{prompt:end:(\d+)}}|{{prompt:middletruncate:(\d+)}}"
    template = re.sub(pattern, replacement_function, template)
    return template


def replace_messages_variable(
    template: str, messages: Optional[list[dict]] = None
) -> str:
    def replacement_function(match):
        full_match = match.group(0)
        start_length = match.group(1)
        end_length = match.group(2)
        middle_length = match.group(3)
        # If messages is None, handle it as an empty list
        if messages is None:
            return ""

        # Process messages based on the number of messages required
        if full_match == "{{MESSAGES}}":
            return get_messages_content(messages)
        elif start_length is not None:
            return get_messages_content(messages[: int(start_length)])
        elif end_length is not None:
            return get_messages_content(messages[-int(end_length) :])
        elif middle_length is not None:
            mid = int(middle_length)

            if len(messages) <= mid:
                return get_messages_content(messages)
            # Handle middle truncation: split to get start and end portions of the messages list
            half = mid // 2
            start_msgs = messages[:half]
            end_msgs = messages[-half:] if mid % 2 == 0 else messages[-(half + 1) :]
            formatted_start = get_messages_content(start_msgs)
            formatted_end = get_messages_content(end_msgs)
            return f"{formatted_start}\n{formatted_end}"
        return ""

    template = re.sub(
        r"{{MESSAGES}}|{{MESSAGES:START:(\d+)}}|{{MESSAGES:END:(\d+)}}|{{MESSAGES:MIDDLETRUNCATE:(\d+)}}",
        replacement_function,
        template,
    )

    return template


def title_generation_template(template: str, messages: list[dict]) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)
    return template


def follow_up_generation_template(template: str, messages: list[dict]) -> str:
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)
    return template


def emoji_generation_template(template: str, prompt: str) -> str:
    template = replace_prompt_variable(template, prompt)
    return template
