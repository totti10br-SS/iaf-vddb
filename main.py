import os
import logging
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
app.mount("/static", StaticFiles(directory="static"), name="static")


class PerguntaRequest(BaseModel):
    pergunta: str
    filial: str = "TODAS"


class PerguntaResponse(BaseModel):
    resposta: str
    sql: str
    row_count: int
    success: bool


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
        schema = get_schema()
        schema_prompt = build_schema_prompt(schema)
        csv_path = get_csv_path()

        # etapa 1: IA gera o SQL
        sql = generate_sql(body.pergunta, schema_prompt)

        if sql.startswith("ERRO:"):
            return PerguntaResponse(
                resposta=f"Não consegui entender a pergunta: {sql}",
                sql=sql,
                row_count=0,
                success=False,
            )

        # etapa 2: DuckDB executa
        resultado = execute_query(csv_path, sql)

        # etapa 3: IA narra
        resultado_texto = result_to_text(resultado)
        resposta = narrate_result(body.pergunta, resultado_texto, schema_prompt)

        return PerguntaResponse(
            resposta=resposta,
            sql=sql,
            row_count=resultado["row_count"],
            success=resultado["success"],
        )

    except Exception as e:
        logger.error(f"Erro no /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema")
async def schema_info():
    schema = get_schema()
    return {
        "columns": schema["columns"],
        "total_rows": schema["total_rows"],
        "sample": schema["sample"],
    }


@app.post("/cache/clear")
async def clear_cache():
    global _schema_cache
    invalidate_cache()
    _schema_cache = {}
    return {"status": "cache invalidado"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
