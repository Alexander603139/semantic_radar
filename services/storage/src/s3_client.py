import boto3
from botocore.exceptions import ClientError
import logging
from .settings import settings

logger = logging.getLogger(__name__)

s3_client = boto3.client(
    's3',
    endpoint_url=settings.S3_ENDPOINT,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY,
)

def upload_file(file_data: bytes, key: str) -> str:
    """Загружает файл в S3 и возвращает его ключ (путь)."""
    try:
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=file_data,
        )
        return key
    except ClientError as e:
        logger.error(f"S3 upload error: {e}")
        raise

def download_file(key: str) -> bytes:
    """Скачивает файл из S3."""
    try:
        response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        return response['Body'].read()
    except ClientError as e:
        logger.error(f"S3 download error: {e}")
        raise

def delete_file(key: str) -> None:
    """Удаляет файл из S3."""
    try:
        s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
    except ClientError as e:
        logger.error(f"S3 delete error: {e}")
        raise