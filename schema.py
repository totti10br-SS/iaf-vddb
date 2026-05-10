import duckdb
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_schema(csv_path: Path) -> dict:
    con = duckdb.connect()

    # colunas e tipos
    result = con.execute(f"""
        DESCRIBE SELECT * FROM read_csv_auto('{csv_path}', header=true)
    """).fetchall()
    columns = [{"name": row[0], "type": row[1]} for row in result]

    # amostra de 3 linhas — sem pandas, dict manual
    col_names = [c["name"] for c in columns]
    sample_rows = con.execute(f"""
        SELECT * FROM read_csv_auto('{csv_path}', header=true) LIMIT 3
    """).fetchall()
    sample = [dict(zip(col_names, row)) for row in sample_rows]

    # contagem
    total_rows = con.execute(f"""
        SELECT COUNT(*) FROM read_csv_auto('{csv_path}', header=true)
    """).fetchone()[0]

    con.close()
    logger.info(f"Schema detectado: {len(columns)} colunas, {total_rows} linhas")

    return {
        "columns":    columns,
        "sample":     sample,
        "total_rows": total_rows,
    }


def build_schema_prompt(schema: dict) -> str:
    lines = ["Colunas disponíveis no CSV de vendas:"]
    for col in schema["columns"]:
        lines.append(f"  - {col['name']} ({col['type']})")
    lines.append(f"\nTotal de registros: {schema['total_rows']:,}")
    if schema["sample"]:
        lines.append("\nExemplo de 1 linha:")
        for k, v in schema["sample"][0].items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)
