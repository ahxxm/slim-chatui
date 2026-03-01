import asyncio
from typing import Dict, List, Optional
from uuid import uuid4
import logging

log = logging.getLogger(__name__)

# In-memory task tracking
tasks: Dict[str, asyncio.Task] = {}
item_tasks: Dict[Optional[str], List[str]] = {}


async def cleanup_task(task_id: str, id=None):
    tasks.pop(task_id, None)

    if id and task_id in item_tasks.get(id, []):
        item_tasks[id].remove(task_id)
        if not item_tasks[id]:
            item_tasks.pop(id, None)


async def create_task(coroutine, id=None):
    task_id = str(uuid4())
    task = asyncio.create_task(coroutine)

    task.add_done_callback(lambda t: asyncio.create_task(cleanup_task(task_id, id)))
    tasks[task_id] = task

    if item_tasks.get(id):
        item_tasks[id].append(task_id)
    else:
        item_tasks[id] = [task_id]

    return task_id, task


async def list_tasks():
    return list(tasks.keys())


async def list_task_ids_by_item_id(id):
    return item_tasks.get(id, [])


async def stop_task(task_id: str):
    task = tasks.pop(task_id, None)
    if not task:
        return {"status": False, "message": f"Task with ID {task_id} not found."}

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return {"status": True, "message": f"Task {task_id} successfully stopped."}

    if task.cancelled() or task.done():
        return {"status": True, "message": f"Task {task_id} successfully cancelled."}

    return {"status": True, "message": f"Cancellation requested for {task_id}."}


async def stop_item_tasks(item_id: str):
    task_ids = await list_task_ids_by_item_id(item_id)
    if not task_ids:
        return {"status": True, "message": f"No tasks found for item {item_id}."}

    for task_id in task_ids:
        result = await stop_task(task_id)
        if not result["status"]:
            return result

    return {"status": True, "message": f"All tasks for item {item_id} stopped."}


async def has_active_tasks(chat_id: str) -> bool:
    task_ids = await list_task_ids_by_item_id(chat_id)
    return len(task_ids) > 0


async def get_active_chat_ids(chat_ids: List[str]) -> List[str]:
    active = []
    for chat_id in chat_ids:
        if await has_active_tasks(chat_id):
            active.append(chat_id)
    return active
