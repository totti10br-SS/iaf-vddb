import duckdb
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_ROWS = 200


def execute_query(csv_path: Path, sql: str) -> dict:
    # substitui placeholder da tabela pelo caminho real do CSV
    import re
    safe_sql = re.sub(
        r'\bvendas\b',
        f"read_csv_auto('{csv_path}', header=true)",
        sql
    )
    # limita resultado direto no SQL para não trazer linhas demais
    logger.info(f"Executando query: {safe_sql[:200]}")

    con = duckdb.connect()
    try:
        rel = con.execute(safe_sql)
        # pega colunas antes de fetchmany
        columns = [desc[0] for desc in rel.description]
        raw_rows = rel.fetchmany(MAX_ROWS + 1)
        con.close()

        truncated = len(raw_rows) > MAX_ROWS
        raw_rows  = raw_rows[:MAX_ROWS]

        # converte para lista de dicts sem pandas
        rows = [dict(zip(columns, row)) for row in raw_rows]

        return {
            "success":   True,
            "rows":      rows,
            "columns":   columns,
            "row_count": len(rows),
            "truncated": truncated,
            "error":     None,
        }
    except Exception as e:
        try: con.close()
        except: pass
        logger.error(f"Erro na query: {e}")
        return {
            "success":   False,
            "rows":      [],
            "columns":   [],
            "row_count": 0,
            "truncated": False,
            "error":     str(e),
        }


def result_to_text(result: dict) -> str:
    if not result["success"]:
        return f"Erro ao executar consulta: {result['error']}"

    if not result["rows"]:
        return "Nenhum registro encontrado para essa consulta."

    cols  = result["columns"]
    lines = [" | ".join(cols), "-" * (len(cols) * 15)]

    for row in result["rows"]:
        values = [str(row.get(c, "")) for c in cols]
        lines.append(" | ".join(values))

    if result["truncated"]:
        lines.append(f"\n(limitado a {MAX_ROWS} linhas)")

    return "\n".join(lines)
