import time
from typing import Optional

from sqlalchemy.orm import Session, defer
from open_webui.internal.db import Base, get_db_context


from open_webui.models.chats import Chats
from open_webui.utils.validate import validate_profile_image_url


from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from sqlalchemy import BigInteger, JSON, Column, String, Text
from sqlalchemy import or_, func

####################
# User DB Schema
####################


class UserSettings(BaseModel):
    ui: Optional[dict] = {}
    model_config = ConfigDict(extra="allow")


class User(Base):
    __tablename__ = "user"

    id = Column(String, primary_key=True, unique=True)
    email = Column(String)
    username = Column(String(50), nullable=True)
    role = Column(String)

    name = Column(String)

    profile_image_url = Column(Text)
    profile_banner_image_url = Column(Text, nullable=True)

    settings = Column(JSON, nullable=True)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


class UserModel(BaseModel):
    id: str

    email: str
    username: Optional[str] = None
    role: str = "pending"

    name: str

    profile_image_url: Optional[str] = None
    profile_banner_image_url: Optional[str] = None

    settings: Optional[UserSettings] = None
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def set_profile_image_url(self):
        if not self.profile_image_url:
            self.profile_image_url = f"/api/v1/users/{self.id}/profile/image"
        return self


####################
# Forms
####################


class UpdateProfileForm(BaseModel):
    profile_image_url: str
    name: str

    @field_validator("profile_image_url")
    @classmethod
    def check_profile_image_url(cls, v: str) -> str:
        return validate_profile_image_url(v)


class UserModelResponse(UserModel):
    model_config = ConfigDict(extra="allow")


class UserListResponse(BaseModel):
    users: list[UserModelResponse]
    total: int


class UserInfoResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str


class UserInfoListResponse(BaseModel):
    users: list[UserInfoResponse]
    total: int


class UserNameResponse(BaseModel):
    id: str
    name: str
    role: str


class UserResponse(UserNameResponse):
    email: str


class UserProfileImageResponse(UserNameResponse):
    email: str
    profile_image_url: str


class UserUpdateForm(BaseModel):
    role: str
    name: str
    email: str
    profile_image_url: str
    password: Optional[str] = None

    @field_validator("profile_image_url")
    @classmethod
    def check_profile_image_url(cls, v: str) -> str:
        return validate_profile_image_url(v)


class UsersTable:
    def insert_new_user(
        self,
        id: str,
        name: str,
        email: str,
        profile_image_url: str = "/user.png",
        role: str = "pending",
        username: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Optional[UserModel]:
        with get_db_context(db) as db:
            user = UserModel(
                id=id,
                email=email,
                name=name,
                role=role,
                profile_image_url=profile_image_url,
                created_at=int(time.time()),
                updated_at=int(time.time()),
                username=username,
            )
            result = User(**user.model_dump())
            db.add(result)
            db.flush()
            db.refresh(result)
            return user

    def get_user_by_id(
        self, id: str, db: Optional[Session] = None
    ) -> Optional[UserModel]:
        try:
            with get_db_context(db) as db:
                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_email(
        self, email: str, db: Optional[Session] = None
    ) -> Optional[UserModel]:
        try:
            with get_db_context(db) as db:
                user = (
                    db.query(User)
                    .filter(func.lower(User.email) == email.lower())
                    .first()
                )
                return UserModel.model_validate(user) if user else None
        except Exception:
            return None

    def get_users(
        self,
        filter: Optional[dict] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> dict:
        with get_db_context(db) as db:
            query = db.query(User).options(defer(User.profile_image_url))

            if filter:
                query_key = filter.get("query")
                if query_key:
                    query = query.filter(
                        or_(
                            User.name.ilike(f"%{query_key}%"),
                            User.email.ilike(f"%{query_key}%"),
                        )
                    )

                user_ids = filter.get("user_ids")
                if user_ids:
                    query = query.filter(User.id.in_(user_ids))

                roles = filter.get("roles")
                if roles:
                    include_roles = [role for role in roles if not role.startswith("!")]
                    exclude_roles = [role[1:] for role in roles if role.startswith("!")]

                    if include_roles:
                        query = query.filter(User.role.in_(include_roles))
                    if exclude_roles:
                        query = query.filter(~User.role.in_(exclude_roles))

                order_by = filter.get("order_by")
                direction = filter.get("direction")

                if order_by == "name":
                    if direction == "asc":
                        query = query.order_by(User.name.asc())
                    else:
                        query = query.order_by(User.name.desc())

                elif order_by == "email":
                    if direction == "asc":
                        query = query.order_by(User.email.asc())
                    else:
                        query = query.order_by(User.email.desc())

                elif order_by == "created_at":
                    if direction == "asc":
                        query = query.order_by(User.created_at.asc())
                    else:
                        query = query.order_by(User.created_at.desc())

                elif order_by == "updated_at":
                    if direction == "asc":
                        query = query.order_by(User.updated_at.asc())
                    else:
                        query = query.order_by(User.updated_at.desc())
                elif order_by == "role":
                    if direction == "asc":
                        query = query.order_by(User.role.asc())
                    else:
                        query = query.order_by(User.role.desc())

            else:
                query = query.order_by(User.created_at.desc())

            total = query.count()

            if skip is not None:
                query = query.offset(skip)
            if limit is not None:
                query = query.limit(limit)

            users = query.all()
            return {
                "users": [UserModel.model_validate(user) for user in users],
                "total": total,
            }

    def get_users_by_user_ids(
        self, user_ids: list[str], db: Optional[Session] = None
    ) -> list[UserModel]:
        with get_db_context(db) as db:
            users = (
                db.query(User)
                .options(defer(User.profile_image_url))
                .filter(User.id.in_(user_ids))
                .all()
            )
            return [UserModel.model_validate(user) for user in users]

    def get_num_users(self, db: Optional[Session] = None) -> Optional[int]:
        with get_db_context(db) as db:
            return db.query(User).count()

    def has_users(self, db: Optional[Session] = None) -> bool:
        with get_db_context(db) as db:
            return db.query(db.query(User).exists()).scalar()

    def get_first_user(self, db: Optional[Session] = None) -> UserModel:
        try:
            with get_db_context(db) as db:
                user = db.query(User).order_by(User.created_at).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_role_by_id(
        self, id: str, role: str, db: Optional[Session] = None
    ) -> Optional[UserModel]:
        try:
            with get_db_context(db) as db:
                user = db.query(User).filter_by(id=id).first()
                if not user:
                    return None
                user.role = role
                db.flush()
                db.refresh(user)
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_profile_image_url_by_id(
        self, id: str, profile_image_url: str, db: Optional[Session] = None
    ) -> Optional[UserModel]:
        try:
            with get_db_context(db) as db:
                user = db.query(User).filter_by(id=id).first()
                if not user:
                    return None
                user.profile_image_url = profile_image_url
                db.flush()
                db.refresh(user)
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_by_id(
        self, id: str, updated: dict, db: Optional[Session] = None
    ) -> Optional[UserModel]:
        try:
            with get_db_context(db) as db:
                user = db.query(User).filter_by(id=id).first()
                if not user:
                    return None
                for key, value in updated.items():
                    setattr(user, key, value)
                db.flush()
                db.refresh(user)
                return UserModel.model_validate(user)
        except Exception as e:
            print(e)
            return None

    def update_user_settings_by_id(
        self, id: str, updated: dict, db: Optional[Session] = None
    ) -> Optional[UserModel]:
        try:
            with get_db_context(db) as db:
                user = db.query(User).filter_by(id=id).first()
                if not user:
                    return None

                user_settings = user.settings

                if user_settings is None:
                    user_settings = {}

                user_settings.update(updated)

                db.query(User).filter_by(id=id).update({"settings": user_settings})
                db.flush()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def delete_user_by_id(self, id: str, db: Optional[Session] = None) -> bool:
        try:
            result = Chats.delete_chats_by_user_id(id, db=db)
            if result:
                with get_db_context(db) as db:
                    # Delete User
                    db.query(User).filter_by(id=id).delete()
                    db.flush()

                return True
            else:
                return False
        except Exception:
            return False

    def get_valid_user_ids(
        self, user_ids: list[str], db: Optional[Session] = None
    ) -> list[str]:
        with get_db_context(db) as db:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            return [user.id for user in users]

    def get_super_admin_user(self, db: Optional[Session] = None) -> Optional[UserModel]:
        with get_db_context(db) as db:
            user = db.query(User).filter_by(role="admin").first()
            if user:
                return UserModel.model_validate(user)
            else:
                return None


Users = UsersTable()
