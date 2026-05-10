import os
import time
import logging
import pickle
import base64
import io
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

CSV_PATH = Path("/tmp/vendas.csv")
CACHE_TTL = int(os.getenv("CACHE_TTL_MINUTES", "30")) * 60
FILE_ID = os.getenv("DRIVE_FILE_ID", "1aXJ4dzf2XzmUMvb78gUA18YrCFL8bjbe")

_last_download: float = 0


def _get_drive_service():
    token_pickle_b64 = os.getenv("GOOGLE_TOKEN_PICKLE")
    if not token_pickle_b64:
        raise RuntimeError("GOOGLE_TOKEN_PICKLE não configurado")
    token_bytes = base64.b64decode(token_pickle_b64)
    creds = pickle.loads(token_bytes)
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
