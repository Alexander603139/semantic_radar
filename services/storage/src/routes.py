import hashlib
import logging
import json
import mimetypes
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session
from fastapi.responses import Response
from .database import SessionLocal
from . import crud, schemas, s3_client

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload", response_model=schemas.FileResponse)
async def upload_file(
    user_id: str = Form(...),
    file_type: schemas.FileType = Form(...),
    file_key: str = Form(...),
    file: UploadFile = File(...),
    metadata: str = Form(None),
    db: Session = Depends(get_db),
):
    # Читаем файл
    file_data = await file.read()

    # Считаем checksum (опционально)
    checksum = hashlib.md5(file_data).hexdigest()

    # Формируем ключ в S3: user_id/file_type/file_key
    s3_key = f"{user_id}/{file_type.value}/{file_key}"

    # Загружаем в S3
    try:
        s3_client.upload_file(file_data, s3_key)
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")
        raise HTTPException(status_code=500, detail="S3 upload failed")

    # Сохраняем метаданные в БД
    file_create = schemas.FileCreate(
        user_id=user_id,
        file_type=file_type,
        file_key=file_key,
        extra_metadata=metadata and json.loads(metadata) or None,
    )
    db_file = crud.create_file_record(db, file_create, s3_key, checksum)
    return schemas.FileResponse.model_validate(db_file)

@router.get("/download/{file_id}")
# @router.get("/{file_id}")
async def download_file(file_id: str, db: Session = Depends(get_db)):
    db_file = crud.get_file_record(db, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        file_data = s3_client.download_file(db_file.storage_path)
        # Определяем content-type по расширению файла
        content_type, _ = mimetypes.guess_type(db_file.file_key)
        if not content_type:
            content_type = "application/octet-stream"
        return Response(content=file_data, media_type=content_type)
    except Exception as e:
        logger.error(f"Failed to download from S3: {e}")
        raise HTTPException(status_code=500, detail="S3 download failed")

@router.get("/list", response_model=list[schemas.FileResponse])
async def list_files(
    user_id: str,
    file_type: schemas.FileType = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    files = crud.get_files(db, user_id, file_type, limit)
    return [schemas.FileResponse.model_validate(f) for f in files]

@router.delete("/{file_id}")
async def delete_file(file_id: str, db: Session = Depends(get_db)):
    db_file = crud.get_file_record(db, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    # Удаляем из S3
    try:
        s3_client.delete_file(db_file.storage_path)
    except Exception as e:
        logger.error(f"Failed to delete from S3: {e}")
        # Можно продолжить, но логируем
    # Мягкое удаление в БД
    crud.delete_file_record(db, file_id)
    return {"status": "deleted"}