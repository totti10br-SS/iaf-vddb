import duckdb
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_ROWS = 200  # máximo de linhas que vai para a IA


def execute_query(csv_path: Path, sql: str) -> dict:
    # substitui placeholder da tabela pelo caminho real do CSV
    safe_sql = sql.replace(
        "vendas",
        f"read_csv_auto('{csv_path}', header=true)"
    )

    logger.info(f"Executando query: {safe_sql[:200]}")

    con = duckdb.connect()
    try:
        df = con.execute(safe_sql).fetchdf()
        con.close()

        if len(df) > MAX_ROWS:
            df = df.head(MAX_ROWS)
            truncated = True
        else:
            truncated = False

        return {
            "success": True,
            "rows": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "row_count": len(df),
            "truncated": truncated,
            "error": None,
        }
    except Exception as e:
        con.close()
        logger.error(f"Erro na query: {e}")
        return {
            "success": False,
            "rows": [],
            "columns": [],
            "row_count": 0,
            "truncated": False,
            "error": str(e),
        }


def result_to_text(result: dict) -> str:
    if not result["success"]:
        return f"Erro ao executar consulta: {result['error']}"

    if not result["rows"]:
        return "Nenhum registro encontrado para essa consulta."

    lines = []
    cols = result["columns"]

    # cabeçalho
    lines.append(" | ".join(cols))
    lines.append("-" * (len(cols) * 15))

    # linhas
    for row in result["rows"]:
        values = [str(row.get(c, "")) for c in cols]
        lines.append(" | ".join(values))

    if result["truncated"]:
        lines.append(f"\n(limitado a {MAX_ROWS} linhas)")

    return "\n".join(lines)
