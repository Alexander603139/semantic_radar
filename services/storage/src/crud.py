from sqlalchemy.orm import Session
from .models import AIModel
import uuid
from . import models, schemas
from datetime import datetime, timedelta
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

def get_files(db: Session, user_id: str, file_type: str = None, limit: int = 100, model_slug: str = None) -> list:
    query = db.query(models.FileRecord).filter(
        models.FileRecord.user_id == user_id,
        models.FileRecord.deleted_at.is_(None)
    )
    if file_type:
        query = query.filter(models.FileRecord.file_type == file_type)
    
    files = query.order_by(models.FileRecord.created_at.desc()).limit(limit).all()
    
    # Этап 10: фильтрация по model_slug в extra_metadata
    if model_slug:
        files = [
            f for f in files
            if f.extra_metadata and f.extra_metadata.get("model_slug") == model_slug
        ]
    
    return files

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
    return db_model\

def count_vectors(db: Session, user_id: str, model_slug: str = None) -> int:
    """Подсчитывает количество неудалённых векторов пользователя (опционально — по модели)."""
    query = db.query(models.FileRecord).filter(
        models.FileRecord.user_id == user_id,
        models.FileRecord.file_type == "vectors",
        models.FileRecord.deleted_at.is_(None),
    )
    files = query.all()
    if model_slug:
        files = [
            f for f in files
            if f.extra_metadata and f.extra_metadata.get("model_slug") == model_slug
        ]
    return len(files)

def create_source_stats(db: Session, stats_dict: dict):
    """Сохраняет статистику по источникам после парсинга."""
    for source_name, data in stats_dict.items():
        status = "ok"
        if data.get("error"):
            status = "error"
        elif data.get("articles_parsed", 0) == 0:
            status = "empty"

        stat = models.SourceStat(
            source_name=source_name,
            links_found=data.get("links_total", 0),
            articles_parsed=data.get("articles_parsed", 0),
            articles_skipped=data.get("articles_skipped", 0),
            articles_error=data.get("articles_error", 0),
            status=status
        )
        db.add(stat)
    db.commit()

def get_source_stats(db: Session, days: int = 7):
    """Возвращает агрегированную статистику по источникам за N дней."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    results = db.query(
        models.SourceStat.source_name,
        func.sum(models.SourceStat.articles_parsed).label("total_parsed"),
        func.sum(models.SourceStat.articles_skipped).label("total_skipped"),
        func.sum(models.SourceStat.articles_error).label("total_errors"),
        func.max(models.SourceStat.timestamp).label("last_run")
    ).filter(
        models.SourceStat.timestamp >= cutoff
    ).group_by(
        models.SourceStat.source_name
    ).all()
    return results