from litellm.integrations.custom_logger import CustomLogger


class QwenThinkingCallback(CustomLogger):
    """Inject chat_template_kwargs for Qwen models via dict mutation.

    LiteLLM's get_optional_params silently drops unknown params before
    the request is serialized. This callback runs after that filter
    (inside logging_obj.pre_call) but before json.dumps(data), so
    mutating the data dict in-place reaches the upstream provider.
    """

    def log_pre_api_call(self, model, messages, kwargs):
        if "qwen" not in model.lower():  # you can be more specific
            return
        data = kwargs.get("additional_args", {}).get("complete_input_dict")
        if not isinstance(data, dict):
            return
        data["chat_template_kwargs"] = {"enable_thinking": True}


proxy_handler_instance = QwenThinkingCallback()
