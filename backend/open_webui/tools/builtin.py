"""
Built-in tools for Open WebUI.

These tools are automatically available when native function calling is enabled.

IMPORTANT: DO NOT IMPORT THIS MODULE DIRECTLY IN OTHER PARTS OF THE CODEBASE.
"""

import json
import logging
from typing import Optional

from fastapi import Request

from open_webui.models.users import UserModel
from open_webui.models.chats import Chats
from open_webui.models.groups import Groups
from open_webui.utils.sanitize import sanitize_code

log = logging.getLogger(__name__)

# =============================================================================
# TIME UTILITIES
# =============================================================================


async def get_current_timestamp(
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the current Unix timestamp in seconds.

    :return: JSON with current_timestamp (seconds) and current_iso (ISO format)
    """
    try:
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        return json.dumps(
            {
                "current_timestamp": int(now.timestamp()),
                "current_iso": now.isoformat(),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f"get_current_timestamp error: {e}")
        return json.dumps({"error": str(e)})


async def calculate_timestamp(
    days_ago: int = 0,
    weeks_ago: int = 0,
    months_ago: int = 0,
    years_ago: int = 0,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the current Unix timestamp, optionally adjusted by days, weeks, months, or years.
    Use this to calculate timestamps for date filtering in search functions.
    Examples: "last week" = weeks_ago=1, "3 days ago" = days_ago=3, "a year ago" = years_ago=1

    :param days_ago: Number of days to subtract from current time (default: 0)
    :param weeks_ago: Number of weeks to subtract from current time (default: 0)
    :param months_ago: Number of months to subtract from current time (default: 0)
    :param years_ago: Number of years to subtract from current time (default: 0)
    :return: JSON with current_timestamp and calculated_timestamp (both in seconds)
    """
    try:
        import datetime
        from dateutil.relativedelta import relativedelta

        now = datetime.datetime.now(datetime.timezone.utc)
        current_ts = int(now.timestamp())

        # Calculate the adjusted time
        total_days = days_ago + (weeks_ago * 7)
        adjusted = now - datetime.timedelta(days=total_days)

        # Handle months and years separately (variable length)
        if months_ago > 0 or years_ago > 0:
            adjusted = adjusted - relativedelta(months=months_ago, years=years_ago)

        adjusted_ts = int(adjusted.timestamp())

        return json.dumps(
            {
                "current_timestamp": current_ts,
                "current_iso": now.isoformat(),
                "calculated_timestamp": adjusted_ts,
                "calculated_iso": adjusted.isoformat(),
            },
            ensure_ascii=False,
        )
    except ImportError:
        # Fallback without dateutil
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        current_ts = int(now.timestamp())
        total_days = days_ago + (weeks_ago * 7) + (months_ago * 30) + (years_ago * 365)
        adjusted = now - datetime.timedelta(days=total_days)
        adjusted_ts = int(adjusted.timestamp())
        return json.dumps(
            {
                "current_timestamp": current_ts,
                "current_iso": now.isoformat(),
                "calculated_timestamp": adjusted_ts,
                "calculated_iso": adjusted.isoformat(),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f"calculate_timestamp error: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# CODE INTERPRETER TOOLS
# =============================================================================


async def execute_code(
    code: str,
    __request__: Request = None,
    __user__: dict = None,
    __event_emitter__: callable = None,
    __event_call__: callable = None,
    __chat_id__: str = None,
    __message_id__: str = None,
    __metadata__: dict = None,
) -> str:
    """
    Execute Python code in a sandboxed environment and return the output.
    Use this to perform calculations, data analysis, generate visualizations,
    or run any Python code that would help answer the user's question.

    :param code: The Python code to execute
    :return: JSON with stdout, stderr, and result from execution
    """

    if __request__ is None:
        return json.dumps({"error": "Request context not available"})

    try:
        # Sanitize code (strips ANSI codes and markdown fences)
        code = sanitize_code(code)

        # Import blocked modules from config (same as middleware)
        from open_webui.config import CODE_INTERPRETER_BLOCKED_MODULES

        # Add import blocking code if there are blocked modules
        if CODE_INTERPRETER_BLOCKED_MODULES:
            import textwrap

            blocking_code = textwrap.dedent(f"""
                import builtins

                BLOCKED_MODULES = {CODE_INTERPRETER_BLOCKED_MODULES}

                _real_import = builtins.__import__
                def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
                    if name.split('.')[0] in BLOCKED_MODULES:
                        importer_name = globals.get('__name__') if globals else None
                        if importer_name == '__main__':
                            raise ImportError(
                                f"Direct import of module {{name}} is restricted."
                            )
                    return _real_import(name, globals, locals, fromlist, level)

                builtins.__import__ = restricted_import
                """)
            code = blocking_code + "\n" + code

        from open_webui.utils.code_interpreter import execute_code_jupyter

        output = await execute_code_jupyter(
            __request__.app.state.config.CODE_INTERPRETER_JUPYTER_URL,
            code,
            (
                __request__.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN
                if __request__.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH == "token"
                else None
            ),
            (
                __request__.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD
                if __request__.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH
                == "password"
                else None
            ),
            __request__.app.state.config.CODE_INTERPRETER_JUPYTER_TIMEOUT,
        )

        stdout = output.get("stdout", "")
        stderr = output.get("stderr", "")
        result = output.get("result", "")

        # Handle image outputs (base64 encoded) - replace with uploaded URLs
        # Get actual user object for image upload (upload_image requires user.id attribute)
        if __user__ and __user__.get("id"):
            from open_webui.models.users import Users
            from open_webui.utils.files import get_image_url_from_base64

            user = Users.get_user_by_id(__user__["id"])

            # Extract and upload images from stdout
            if stdout and isinstance(stdout, str):
                stdout_lines = stdout.split("\n")
                for idx, line in enumerate(stdout_lines):
                    if "data:image/png;base64" in line:
                        image_url = get_image_url_from_base64(
                            __request__,
                            line,
                            __metadata__ or {},
                            user,
                        )
                        if image_url:
                            stdout_lines[idx] = f"![Output Image]({image_url})"
                stdout = "\n".join(stdout_lines)

            # Extract and upload images from result
            if result and isinstance(result, str):
                result_lines = result.split("\n")
                for idx, line in enumerate(result_lines):
                    if "data:image/png;base64" in line:
                        image_url = get_image_url_from_base64(
                            __request__,
                            line,
                            __metadata__ or {},
                            user,
                        )
                        if image_url:
                            result_lines[idx] = f"![Output Image]({image_url})"
                result = "\n".join(result_lines)

        response = {
            "status": "success",
            "stdout": stdout,
            "stderr": stderr,
            "result": result,
        }

        return json.dumps(response, ensure_ascii=False)
    except Exception as e:
        log.exception(f"execute_code error: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# CHATS TOOLS
# =============================================================================


async def search_chats(
    query: str,
    count: int = 5,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    __request__: Request = None,
    __user__: dict = None,
    __chat_id__: str = None,
) -> str:
    """
    Search the user's previous chat conversations by title and message content.

    :param query: The search query to find matching chats
    :param count: Maximum number of results to return (default: 5)
    :param start_timestamp: Only include chats updated after this Unix timestamp (seconds)
    :param end_timestamp: Only include chats updated before this Unix timestamp (seconds)
    :return: JSON with matching chats containing id, title, updated_at, and content snippet
    """
    if __request__ is None:
        return json.dumps({"error": "Request context not available"})

    if not __user__:
        return json.dumps({"error": "User context not available"})

    try:
        user_id = __user__.get("id")

        chats = Chats.get_chats_by_user_id_and_search_text(
            user_id=user_id,
            search_text=query,
            include_archived=False,
            skip=0,
            limit=count * 3,  # Fetch more for filtering
        )

        results = []
        for chat in chats:
            # Skip the current chat to avoid showing it in search results
            if __chat_id__ and chat.id == __chat_id__:
                continue

            # Apply date filters (updated_at is in seconds)
            if start_timestamp and chat.updated_at < start_timestamp:
                continue
            if end_timestamp and chat.updated_at > end_timestamp:
                continue

            # Find a matching message snippet
            snippet = ""
            messages = chat.chat.get("history", {}).get("messages", {})
            lower_query = query.lower()

            for msg_id, msg in messages.items():
                content = msg.get("content", "")
                if isinstance(content, str) and lower_query in content.lower():
                    idx = content.lower().find(lower_query)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 100)
                    snippet = (
                        ("..." if start > 0 else "")
                        + content[start:end]
                        + ("..." if end < len(content) else "")
                    )
                    break

            if not snippet and lower_query in chat.title.lower():
                snippet = f"Title match: {chat.title}"

            results.append(
                {
                    "id": chat.id,
                    "title": chat.title,
                    "snippet": snippet,
                    "updated_at": chat.updated_at,
                }
            )

            if len(results) >= count:
                break

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        log.exception(f"search_chats error: {e}")
        return json.dumps({"error": str(e)})


async def view_chat(
    chat_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the full conversation history of a chat by its ID.

    :param chat_id: The ID of the chat to retrieve
    :return: JSON with the chat's id, title, and messages
    """
    if __request__ is None:
        return json.dumps({"error": "Request context not available"})

    if not __user__:
        return json.dumps({"error": "User context not available"})

    try:
        user_id = __user__.get("id")

        chat = Chats.get_chat_by_id_and_user_id(chat_id, user_id)

        if not chat:
            return json.dumps({"error": "Chat not found or access denied"})

        # Extract messages from history
        messages = []
        history = chat.chat.get("history", {})
        msg_dict = history.get("messages", {})

        # Build message chain from currentId
        current_id = history.get("currentId")
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            msg = msg_dict.get(current_id)
            if msg:
                messages.append(
                    {
                        "role": msg.get("role", ""),
                        "content": msg.get("content", ""),
                    }
                )
            current_id = msg.get("parentId") if msg else None

        # Reverse to get chronological order
        messages.reverse()

        return json.dumps(
            {
                "id": chat.id,
                "title": chat.title,
                "messages": messages,
                "updated_at": chat.updated_at,
                "created_at": chat.created_at,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f"view_chat error: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# FILE TOOLS
# =============================================================================


async def view_file(
    file_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the full content of a file by its ID.

    :param file_id: The ID of the file to retrieve
    :return: JSON with the file's id, filename, and full text content
    """
    if __request__ is None:
        return json.dumps({"error": "Request context not available"})

    if not __user__:
        return json.dumps({"error": "User context not available"})

    try:
        from open_webui.models.files import Files
        from open_webui.routers.files import has_access_to_file

        user_id = __user__.get("id")
        user_role = __user__.get("role", "user")

        file = Files.get_file_by_id(file_id)
        if not file:
            return json.dumps({"error": "File not found"})

        if (
            file.user_id != user_id
            and user_role != "admin"
            and not has_access_to_file(
                file_id=file_id,
                access_type="read",
                user=UserModel(**__user__),
            )
        ):
            return json.dumps({"error": "File not found"})

        content = ""
        if file.data:
            content = file.data.get("content", "")

        return json.dumps(
            {
                "id": file.id,
                "filename": file.filename,
                "content": content,
                "updated_at": file.updated_at,
                "created_at": file.created_at,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f"view_file error: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# SKILLS TOOLS
# =============================================================================


async def view_skill(
    name: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Load the full instructions of a skill by its name from the available skills manifest.
    Use this when you need detailed instructions for a skill listed in <available_skills>.

    :param name: The name of the skill to load (as shown in the manifest)
    :return: The full skill instructions as markdown content
    """
    if __request__ is None:
        return json.dumps({"error": "Request context not available"})

    if not __user__:
        return json.dumps({"error": "User context not available"})

    try:
        from open_webui.models.skills import Skills
        from open_webui.models.access_grants import AccessGrants

        user_id = __user__.get("id")

        # Direct DB lookup by unique name
        skill = Skills.get_skill_by_name(name)

        if not skill or not skill.is_active:
            return json.dumps({"error": f"Skill '{name}' not found"})

        # Check user access
        user_role = __user__.get("role", "user")
        if user_role != "admin" and skill.user_id != user_id:
            user_group_ids = [
                group.id for group in Groups.get_groups_by_member_id(user_id)
            ]
            if not AccessGrants.has_access(
                user_id=user_id,
                resource_type="skill",
                resource_id=skill.id,
                permission="read",
                user_group_ids=set(user_group_ids),
            ):
                return json.dumps({"error": "Access denied"})

        return json.dumps(
            {
                "name": skill.name,
                "content": skill.content,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f"view_skill error: {e}")
        return json.dumps({"error": str(e)})
