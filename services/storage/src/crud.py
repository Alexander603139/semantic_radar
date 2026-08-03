from sqlalchemy.orm import Session
import uuid
from . import models, schemas
from sqlalchemy import func

def create_file_record(db: Session, file_data: schemas.FileCreate, storage_path: str, checksum: str = None) -> models.FileRecord:
    db_file = models.FileRecord(
        id=str(uuid.uuid4()),
        user_id=file_data.user_id,
        file_type=file_data.file_type,
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