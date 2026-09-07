from sqlalchemy.orm import Session
from .models import AIModel
import uuid
from . import models, schemas
from sqlalchemy import func

def create_file_record(db: Session, file_data: schemas.FileCreate, storage_path: str, checksum: str = None) -> models.FileRecord:
    db_file = models.FileRecord(
        id=str(uuid.uuid4()),
        user_id=file_data.user_id,
        file_type=file_data.file_type.value,
        file_key=file_data.file_key,
        version=1,
        storage_path=storage_path,
        checksum=checksum,
        extra_metadata=file_data.extra_metadata,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def get_file_record(db: Session, file_id: str) -> models.FileRecord:
    return db.query(models.FileRecord).filter(models.FileRecord.id == file_id, models.FileRecord.deleted_at.is_(None)).first()

def get_files(db: Session, user_id: str, file_type: str = None, limit: int = 100) -> list:
    query = db.query(models.FileRecord).filter(models.FileRecord.user_id == user_id, models.FileRecord.deleted_at.is_(None))
    if file_type:
        query = query.filter(models.FileRecord.file_type == file_type)
    return query.order_by(models.FileRecord.created_at.desc()).limit(limit).all()

def delete_file_record(db: Session, file_id: str) -> bool:
    db_file = get_file_record(db, file_id)
    if not db_file:
        return False
    db_file.deleted_at = func.now()
    db.commit()
    return True

def get_ai_models(db: Session, is_active: bool = None) -> list:
    query = db.query(AIModel)
    if is_active is not None:
        query = query.filter(AIModel.is_active == is_active)
    return query.all()

def get_ai_model_by_slug(db: Session, slug: str) -> AIModel:
    return db.query(AIModel).filter(AIModel.slug == slug).first()

def create_ai_model(db: Session, model_data) -> AIModel:
    db_model = AIModel(
        id=str(uuid.uuid4()),
        slug=model_data.slug,
        name=model_data.name,
        provider_type=model_data.provider_type,
        base_url=model_data.base_url,
        api_key=model_data.api_key,
        model_name=model_data.model_name,
        model_path=model_data.model_path,
        dimension=model_data.dimension,
        requires_prefix=model_data.requires_prefix,
        is_active=model_data.is_active,
    )
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model