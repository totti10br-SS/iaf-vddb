import os
from datetime import datetime
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from loader import get_csv_path, invalidate_cache
from schema import detect_schema, build_schema_prompt
from engine import execute_query, result_to_text
from ai import generate_sql, narrate_result

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
MEUDANFE_API_KEY   = os.getenv("MEUDANFE_API_KEY", "0c1588f4-f90e-4711-8b39-87be9a1581da")

_schema_cache: dict = {}


def get_schema():
    global _schema_cache
    if not _schema_cache:
        csv_path = get_csv_path()
        _schema_cache = detect_schema(csv_path)
    return _schema_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("IAF VDDB iniciando...")
    try:
        get_schema()
        logger.info("CSV carregado e schema detectado com sucesso")
    except Exception as e:
        logger.error(f"Erro no startup: {e}")
    yield
    logger.info("IAF VDDB encerrando")


app = FastAPI(title="IAF VDDB", version="1.0.0", lifespan=lifespan)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


class PerguntaRequest(BaseModel):
    pergunta: str
    filial: str = "TODAS"

class PerguntaResponse(BaseModel):
    resposta: str
    sql: str
    row_count: int
    success: bool

class TTSRequest(BaseModel):
    texto: str
    voice_id: str = "4za2kOXGgUd57HRSQ1fn"

class DanfeRequest(BaseModel):
    chave: str


@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "iaf-vddb"}


@app.post("/ask", response_model=PerguntaResponse)
async def ask(body: PerguntaRequest):
    if not body.pergunta.strip():
        raise HTTPException(status_code=400, detail="Pergunta vazia")
    try:
        schema        = get_schema()
        schema_prompt = build_schema_prompt(schema)
        csv_path      = get_csv_path()

        sql = generate_sql(body.pergunta, schema_prompt)

        if sql.startswith("ERRO:"):
            return PerguntaResponse(
                resposta=f"Nao consegui entender a pergunta: {sql}",
                sql=sql, row_count=0, success=False,
            )

        resultado       = execute_query(csv_path, sql)
        resultado_texto = result_to_text(resultado)
        resposta        = narrate_result(body.pergunta, resultado_texto, schema_prompt)

        return PerguntaResponse(
            resposta=resposta,
            sql=sql,
            row_count=resultado["row_count"],
            success=resultado["success"],
        )
    except Exception as e:
        logger.error(f"Erro no /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts")
async def tts(body: TTSRequest):
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY nao configurado")
    if not body.texto.strip():
        raise HTTPException(status_code=400, detail="Texto vazio")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{body.voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": body.texto[:1200],
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"ElevenLabs erro {resp.status_code}")

    import base64
    audio_b64 = base64.b64encode(resp.content).decode()
    return {"audio_b64": audio_b64}


@app.get("/danfe/{chave}")
async def danfe(chave: str):
    chave = chave.strip().replace(" ", "")
    if len(chave) != 44 or not chave.isdigit():
        raise HTTPException(status_code=400, detail="Chave de acesso invalida (44 digitos)")

    url = f"https://meudanfe.com.br/api/danfe/{chave}"
    headers = {"Authorization": f"Bearer {MEUDANFE_API_KEY}"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="NF-e nao encontrada")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"MeuDanfe erro {resp.status_code}")

    import base64
    pdf_b64 = base64.b64encode(resp.content).decode()
    return {"pdf_b64": pdf_b64, "chave": chave}


@app.get("/schema")
async def schema_info():
    schema = get_schema()
    return {
        "columns":    schema["columns"],
        "total_rows": schema["total_rows"],
        "sample":     schema["sample"],
    }

@app.post("/cache/clear")
@app.get("/cache/invalidar")
async def clear_cache():
    global _schema_cache
    invalidate_cache()
    _schema_cache = {}
    return {"status": "cache invalidado"}


@app.get("/info")
async def info():
    from loader import _last_download, CSV_PATH
    import time
    ultima = datetime.fromtimestamp(_last_download).strftime("%d/%m/%Y %H:%M") if _last_download else "—"
    schema = _schema_cache
    return {
        "total_registros": schema.get("total_rows", 0) if schema else 0,
        "ultima_atualizacao": ultima,
        "csv_mb": round(CSV_PATH.stat().st_size / 1024 / 1024, 1) if CSV_PATH.exists() else 0,
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)


# ─── PDF ──────────────────────────────────────────────────

from fastapi.responses import Response as FastAPIResponse
from pdf_gen import gerar_pdf

@app.post("/ask/pdf")
async def ask_pdf(body: PerguntaRequest):
    if not body.pergunta.strip():
        raise HTTPException(status_code=400, detail="Pergunta vazia")
    try:
        schema        = get_schema()
        schema_prompt = build_schema_prompt(schema)
        csv_path      = get_csv_path()

        sql = generate_sql(body.pergunta, schema_prompt)
        if sql.startswith("ERRO:"):
            raise HTTPException(status_code=400, detail=sql)

        resultado       = execute_query(csv_path, sql)
        resultado_texto = result_to_text(resultado)
        resposta        = narrate_result(body.pergunta, resultado_texto, schema_prompt)

        pdf_bytes = gerar_pdf(
            pergunta  = body.pergunta,
            resposta  = resposta,
            rows      = resultado["rows"],
            columns   = resultado["columns"],
            row_count = resultado["row_count"],
            sql       = sql,
        )

        nome = f"IAF_VDDB_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return FastAPIResponse(
            content     = pdf_bytes,
            media_type  = "application/pdf",
            headers     = {"Content-Disposition": f'attachment; filename="{nome}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no /ask/pdf: {e}")
        raise HTTPException(status_code=500, detail=str(e))
