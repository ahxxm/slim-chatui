import os
import shutil
import logging
from typing import BinaryIO, Tuple

from open_webui.config import UPLOAD_DIR
from open_webui.constants import ERROR_MESSAGES

log = logging.getLogger(__name__)


class LocalStorageProvider:
    @staticmethod
    def upload_file(file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        contents = file.read()
        if not contents:
            raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)
        file_path = f"{UPLOAD_DIR}/{filename}"
        with open(file_path, "wb") as f:
            f.write(contents)
        return contents, file_path

    @staticmethod
    def delete_file(file_path: str) -> None:
        filename = file_path.split("/")[-1]
        file_path = f"{UPLOAD_DIR}/{filename}"
        if os.path.isfile(file_path):
            os.remove(file_path)
        else:
            log.warning(f"File {file_path} not found in local storage.")

    @staticmethod
    def delete_all_files() -> None:
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    log.exception(f"Failed to delete {file_path}. Reason: {e}")
        else:
            log.warning(f"Directory {UPLOAD_DIR} not found in local storage.")


Storage = LocalStorageProvider()
