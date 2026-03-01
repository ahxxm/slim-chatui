import logging
import time
from typing import Optional

from sqlalchemy.orm import Session
from open_webui.internal.db import Base, get_db_context
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import BigInteger, Column, String, Text, JSON

log = logging.getLogger(__name__)

####################
# Files DB Schema
####################


class File(Base):
    __tablename__ = "file"
    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String)

    filename = Column(Text)
    path = Column(Text, nullable=True)

    meta = Column(JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class FileModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str

    filename: str
    path: Optional[str] = None

    meta: Optional[dict] = None

    created_at: Optional[int]  # timestamp in epoch
    updated_at: Optional[int]  # timestamp in epoch


####################
# Forms
####################


class FileMeta(BaseModel):
    name: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def sanitize_meta(cls, data):
        """Sanitize metadata fields to handle malformed legacy data."""
        if not isinstance(data, dict):
            return data

        # Handle content_type that may be a list like ['application/pdf', None]
        content_type = data.get("content_type")
        if isinstance(content_type, list):
            # Extract first non-None string value
            data["content_type"] = next(
                (item for item in content_type if isinstance(item, str)), None
            )
        elif content_type is not None and not isinstance(content_type, str):
            data["content_type"] = None

        return data


class FileModelResponse(BaseModel):
    id: str
    user_id: str

    filename: str
    meta: FileMeta

    created_at: int  # timestamp in epoch
    updated_at: Optional[int] = None  # timestamp in epoch, optional for legacy files

    model_config = ConfigDict(extra="allow")


class FileForm(BaseModel):
    id: str
    filename: str
    path: str
    meta: dict = {}


class FilesTable:
    def insert_new_file(
        self, user_id: str, form_data: FileForm, db: Optional[Session] = None
    ) -> Optional[FileModel]:
        with get_db_context(db) as db:
            file = FileModel(
                **{
                    **form_data.model_dump(),
                    "user_id": user_id,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            try:
                result = File(**file.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return FileModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception(f"Error inserting a new file: {e}")
                return None

    def get_file_by_id(
        self, id: str, db: Optional[Session] = None
    ) -> Optional[FileModel]:
        try:
            with get_db_context(db) as db:
                try:
                    file = db.get(File, id)
                    return FileModel.model_validate(file)
                except Exception:
                    return None
        except Exception:
            return None

    def get_files(self, db: Optional[Session] = None) -> list[FileModel]:
        with get_db_context(db) as db:
            return [FileModel.model_validate(file) for file in db.query(File).all()]

    def check_access_by_user_id(
        self, id, user_id, permission="write", db: Optional[Session] = None
    ) -> bool:
        file = self.get_file_by_id(id, db=db)
        if not file:
            return False
        return file.user_id == user_id

    def get_files_by_user_id(
        self, user_id: str, db: Optional[Session] = None
    ) -> list[FileModel]:
        with get_db_context(db) as db:
            return [
                FileModel.model_validate(file)
                for file in db.query(File).filter_by(user_id=user_id).all()
            ]

    @staticmethod
    def _glob_to_like_pattern(glob: str) -> str:
        """
        Convert a glob/fnmatch pattern to a SQL LIKE pattern.

        Escapes SQL special characters and converts glob wildcards:
        - `*` becomes `%` (match any sequence of characters)
        - `?` becomes `_` (match exactly one character)

        Args:
            glob: A glob pattern (e.g., "*.txt", "file?.doc")

        Returns:
            A SQL LIKE compatible pattern with proper escaping.
        """
        # Escape SQL special characters first, then convert glob wildcards
        pattern = glob.replace("\\", "\\\\")
        pattern = pattern.replace("%", "\\%")
        pattern = pattern.replace("_", "\\_")
        pattern = pattern.replace("*", "%")
        pattern = pattern.replace("?", "_")
        return pattern

    def search_files(
        self,
        user_id: Optional[str] = None,
        filename: str = "*",
        skip: int = 0,
        limit: int = 100,
        db: Optional[Session] = None,
    ) -> list[FileModel]:
        with get_db_context(db) as db:
            query = db.query(File)

            if user_id:
                query = query.filter_by(user_id=user_id)

            pattern = self._glob_to_like_pattern(filename)
            if pattern != "%":
                query = query.filter(File.filename.ilike(pattern, escape="\\"))

            return [
                FileModel.model_validate(file)
                for file in query.order_by(File.updated_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            ]

    def delete_file_by_id(self, id: str, db: Optional[Session] = None) -> bool:
        with get_db_context(db) as db:
            try:
                db.query(File).filter_by(id=id).delete()
                db.commit()
                return True
            except Exception:
                return False

    def delete_all_files(self, db: Optional[Session] = None) -> bool:
        with get_db_context(db) as db:
            try:
                db.query(File).delete()
                db.commit()
                return True
            except Exception:
                return False


Files = FilesTable()
