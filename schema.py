import duckdb
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_schema(csv_path: Path) -> dict:
    con = duckdb.connect()
    result = con.execute(f"""
        DESCRIBE SELECT * FROM read_csv_auto('{csv_path}', header=true)
    """).fetchall()
    con.close()

    columns = []
    for row in result:
        columns.append({"name": row[0], "type": row[1]})

    # pega amostra de 3 linhas para exemplos
    con = duckdb.connect()
    sample = con.execute(f"""
        SELECT * FROM read_csv_auto('{csv_path}', header=true) LIMIT 3
    """).fetchdf()
    con.close()

    logger.info(f"Schema detectado: {len(columns)} colunas")
    return {
        "columns": columns,
        "sample": sample.to_dict(orient="records"),
        "total_rows": _count_rows(csv_path),
    }


def _count_rows(csv_path: Path) -> int:
    con = duckdb.connect()
    result = con.execute(f"""
        SELECT COUNT(*) FROM read_csv_auto('{csv_path}', header=true)
    """).fetchone()
    con.close()
    return result[0]


def build_schema_prompt(schema: dict) -> str:
    lines = ["Colunas disponíveis no CSV de vendas:"]
    for col in schema["columns"]:
        lines.append(f"  - {col['name']} ({col['type']})")
    lines.append(f"\nTotal de registros: {schema['total_rows']:,}")
    if schema["sample"]:
        lines.append("\nExemplo de 1 linha:")
        sample = schema["sample"][0]
        for k, v in sample.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)
