import os
import time
import logging
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import io
import json

logger = logging.getLogger(__name__)

CSV_PATH = Path("/tmp/vendas.csv")
CACHE_TTL = int(os.getenv("CACHE_TTL_MINUTES", "30")) * 60
FILE_ID = os.getenv("GOOGLE_DRIVE_FILE_ID", "1aXJ4dzf2XzmUMvb78gUA18YrCFL8bjbe")

_last_download: float = 0


def _get_drive_service():
    creds_raw = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_raw:
        raise RuntimeError("GOOGLE_CREDENTIALS não configurado")
    info = json.loads(creds_raw)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


def _download_csv():
    global _last_download
    logger.info("Baixando CSV do Google Drive...")
    service = _get_drive_service()
    request = service.files().get_media(fileId=FILE_ID)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    CSV_PATH.write_bytes(buffer.getvalue())
    _last_download = time.time()
    size_mb = CSV_PATH.stat().st_size / 1024 / 1024
    logger.info(f"CSV baixado: {size_mb:.1f}MB")


def get_csv_path() -> Path:
    now = time.time()
    if not CSV_PATH.exists() or (now - _last_download) > CACHE_TTL:
        _download_csv()
    return CSV_PATH


def invalidate_cache():
    global _last_download
    _last_download = 0
    if CSV_PATH.exists():
        CSV_PATH.unlink()
    logger.info("Cache invalidado")
