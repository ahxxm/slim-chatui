import asyncio
from typing import Dict, List, Optional
from uuid import uuid4
import logging

from sqlalchemy import select

from open_webui.internal.db import get_db_context
from open_webui.models.chats import ChatFile
from open_webui.models.files import File
from open_webui.storage.provider import Storage

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


def list_tasks():
    return list(tasks.keys())


def list_task_ids_by_item_id(id):
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


def has_active_tasks(chat_id: str) -> bool:
    return len(list_task_ids_by_item_id(chat_id)) > 0


def get_active_chat_ids(chat_ids: List[str]) -> List[str]:
    return [cid for cid in chat_ids if has_active_tasks(cid)]


# --- Orphan file cleanup ---
# When a chat is deleted, CASCADE removes chat_file rows but file records
# and disk blobs remain.  This deletes filesystem first, then DB row.

ORPHAN_CLEANUP_INTERVAL = 30 * 60  # 30 minutes


def delete_orphaned_files() -> int:
    # Collect orphan IDs in a short read
    referenced = select(ChatFile.file_id).distinct().scalar_subquery()
    with get_db_context() as db:
        orphans = db.query(File.id, File.path).filter(File.id.notin_(referenced)).all()

    # TOCTOU: a file re-linked between query and delete would have its
    # chat_file row cascade-deleted. Acceptable.
    deleted = 0
    for file_id, file_path in orphans:
        try:
            if file_path and "/" in file_path and ".." not in file_path:
                Storage.delete_file(file_path)
            else:
                log.warning(f"skip file path: {file_path}")
            with get_db_context() as db:
                deleted += db.query(File).filter(File.id == file_id).delete()
        except Exception:
            log.exception("Failed to delete orphaned file %s", file_id)
    return deleted


async def periodic_orphan_file_cleanup():
    while True:
        await asyncio.sleep(ORPHAN_CLEANUP_INTERVAL)
        try:
            if deleted := delete_orphaned_files():
                log.info("Orphan cleanup: removed %d file(s)", deleted)
        except Exception:
            log.exception("Orphan cleanup failed")
