import logging
import time
from typing import Optional

from sqlalchemy.orm import Session
from open_webui.internal.db import Base, JSONField, get_db, get_db_context

from open_webui.models.users import User, UserModel, Users, UserResponse


from pydantic import BaseModel, ConfigDict

from sqlalchemy import String, cast, or_, func
from sqlalchemy import BigInteger, Column, Text, Boolean

log = logging.getLogger(__name__)


####################
# Models DB Schema
####################


# ModelParams is a model for the data stored in the params field of the Model table
class ModelParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    pass


# ModelMeta is a model for the data stored in the meta field of the Model table
class ModelMeta(BaseModel):
    profile_image_url: Optional[str] = "/static/favicon.png"

    description: Optional[str] = None
    """
        User-facing description of the model.
    """

    capabilities: Optional[dict] = None

    model_config = ConfigDict(extra="allow")

    pass


class Model(Base):
    __tablename__ = "model"

    id = Column(Text, primary_key=True, unique=True)
    """
        The model's id as used in the API. If set to an existing model, it will override the model.
    """
    user_id = Column(Text)

    base_model_id = Column(Text, nullable=True)
    """
        An optional pointer to the actual model that should be used when proxying requests.
    """

    name = Column(Text)
    """
        The human-readable display name of the model.
    """

    params = Column(JSONField)
    """
        Holds a JSON encoded blob of parameters, see `ModelParams`.
    """

    meta = Column(JSONField)
    """
        Holds a JSON encoded blob of metadata, see `ModelMeta`.
    """

    is_active = Column(Boolean, default=True)

    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


class ModelModel(BaseModel):
    id: str
    user_id: str
    base_model_id: Optional[str] = None

    name: str
    params: ModelParams
    meta: ModelMeta

    is_active: bool
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class ModelUserResponse(ModelModel):
    user: Optional[UserResponse] = None


class ModelResponse(ModelModel):
    pass


class ModelListResponse(BaseModel):
    items: list[ModelUserResponse]
    total: int


class ModelForm(BaseModel):
    id: str
    base_model_id: Optional[str] = None
    name: str
    meta: ModelMeta
    params: ModelParams
    is_active: bool = True


class ModelsTable:
    def insert_new_model(
        self, form_data: ModelForm, user_id: str, db: Optional[Session] = None
    ) -> Optional[ModelModel]:
        try:
            with get_db_context(db) as db:
                result = Model(
                    **{
                        **form_data.model_dump(),
                        "user_id": user_id,
                        "created_at": int(time.time()),
                        "updated_at": int(time.time()),
                    }
                )
                db.add(result)
                db.commit()
                db.refresh(result)

                if result:
                    return ModelModel.model_validate(result)
                else:
                    return None
        except Exception as e:
            log.exception(f"Failed to insert a new model: {e}")
            return None

    def get_all_models(self, db: Optional[Session] = None) -> list[ModelModel]:
        with get_db_context(db) as db:
            return [
                ModelModel.model_validate(model)
                for model in db.query(Model).all()
            ]

    def get_models(self, db: Optional[Session] = None) -> list[ModelUserResponse]:
        with get_db_context(db) as db:
            all_models = db.query(Model).filter(Model.base_model_id != None).all()

            user_ids = list(set(model.user_id for model in all_models))
            users = Users.get_users_by_user_ids(user_ids, db=db) if user_ids else []
            users_dict = {user.id: user for user in users}

            models = []
            for model in all_models:
                user = users_dict.get(model.user_id)
                models.append(
                    ModelUserResponse.model_validate(
                        {
                            **ModelModel.model_validate(model).model_dump(),
                            "user": user.model_dump() if user else None,
                        }
                    )
                )
            return models

    def get_base_models(self, db: Optional[Session] = None) -> list[ModelModel]:
        with get_db_context(db) as db:
            return [
                ModelModel.model_validate(model)
                for model in db.query(Model).filter(Model.base_model_id == None).all()
            ]

    def search_models(
        self,
        user_id: str,
        filter: dict = {},
        skip: int = 0,
        limit: int = 30,
        db: Optional[Session] = None,
    ) -> ModelListResponse:
        with get_db_context(db) as db:
            query = db.query(Model, User).outerjoin(User, User.id == Model.user_id)
            query = query.filter(Model.base_model_id != None)

            if filter:
                query_key = filter.get("query")
                if query_key:
                    query = query.filter(
                        or_(
                            Model.name.ilike(f"%{query_key}%"),
                            Model.base_model_id.ilike(f"%{query_key}%"),
                            User.name.ilike(f"%{query_key}%"),
                            User.email.ilike(f"%{query_key}%"),
                            User.username.ilike(f"%{query_key}%"),
                        )
                    )

                view_option = filter.get("view_option")
                if view_option == "created":
                    query = query.filter(Model.user_id == user_id)
                elif view_option == "shared":
                    query = query.filter(Model.user_id != user_id)

                tag = filter.get("tag")
                if tag:
                    like_pattern = f'%"{tag.lower()}"%'
                    meta_text = func.lower(cast(Model.meta, String))
                    query = query.filter(meta_text.like(like_pattern))

                order_by = filter.get("order_by")
                direction = filter.get("direction")

                if order_by == "name":
                    if direction == "asc":
                        query = query.order_by(Model.name.asc())
                    else:
                        query = query.order_by(Model.name.desc())
                elif order_by == "created_at":
                    if direction == "asc":
                        query = query.order_by(Model.created_at.asc())
                    else:
                        query = query.order_by(Model.created_at.desc())
                elif order_by == "updated_at":
                    if direction == "asc":
                        query = query.order_by(Model.updated_at.asc())
                    else:
                        query = query.order_by(Model.updated_at.desc())

            else:
                query = query.order_by(Model.created_at.desc())

            total = query.count()

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            items = query.all()

            models = []
            for model, user in items:
                models.append(
                    ModelUserResponse(
                        **ModelModel.model_validate(model).model_dump(),
                        user=(
                            UserResponse(**UserModel.model_validate(user).model_dump())
                            if user
                            else None
                        ),
                    )
                )

            return ModelListResponse(items=models, total=total)

    def get_model_by_id(
        self, id: str, db: Optional[Session] = None
    ) -> Optional[ModelModel]:
        try:
            with get_db_context(db) as db:
                model = db.get(Model, id)
                return ModelModel.model_validate(model) if model else None
        except Exception:
            return None

    def get_models_by_ids(
        self, ids: list[str], db: Optional[Session] = None
    ) -> list[ModelModel]:
        try:
            with get_db_context(db) as db:
                models = db.query(Model).filter(Model.id.in_(ids)).all()
                return [ModelModel.model_validate(model) for model in models]
        except Exception:
            return []

    def toggle_model_by_id(
        self, id: str, db: Optional[Session] = None
    ) -> Optional[ModelModel]:
        with get_db_context(db) as db:
            try:
                model = db.query(Model).filter_by(id=id).first()
                if not model:
                    return None

                model.is_active = not model.is_active
                model.updated_at = int(time.time())
                db.commit()
                db.refresh(model)

                return ModelModel.model_validate(model)
            except Exception:
                return None

    def update_model_by_id(
        self, id: str, model: ModelForm, db: Optional[Session] = None
    ) -> Optional[ModelModel]:
        try:
            with get_db_context(db) as db:
                data = model.model_dump(exclude={"id"})
                db.query(Model).filter_by(id=id).update(data)
                db.commit()

                return self.get_model_by_id(id, db=db)
        except Exception as e:
            log.exception(f"Failed to update the model by id {id}: {e}")
            return None

    def delete_model_by_id(self, id: str, db: Optional[Session] = None) -> bool:
        try:
            with get_db_context(db) as db:
                db.query(Model).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False

    def delete_all_models(self, db: Optional[Session] = None) -> bool:
        try:
            with get_db_context(db) as db:
                db.query(Model).delete()
                db.commit()
                return True
        except Exception:
            return False

    def sync_models(
        self, user_id: str, models: list[ModelModel], db: Optional[Session] = None
    ) -> list[ModelModel]:
        try:
            with get_db_context(db) as db:
                existing_models = db.query(Model).all()
                existing_ids = {model.id for model in existing_models}
                new_model_ids = {model.id for model in models}

                for model in models:
                    if model.id in existing_ids:
                        db.query(Model).filter_by(id=model.id).update(
                            {
                                **model.model_dump(),
                                "user_id": user_id,
                                "updated_at": int(time.time()),
                            }
                        )
                    else:
                        new_model = Model(
                            **{
                                **model.model_dump(),
                                "user_id": user_id,
                                "updated_at": int(time.time()),
                            }
                        )
                        db.add(new_model)

                for model in existing_models:
                    if model.id not in new_model_ids:
                        db.delete(model)

                db.commit()

                return [
                    ModelModel.model_validate(model)
                    for model in db.query(Model).all()
                ]
        except Exception as e:
            log.exception(f"Error syncing models for user {user_id}: {e}")
            return []


Models = ModelsTable()
