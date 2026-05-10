"""
Previsão de faturamento mensal baseada em média diária × dias úteis restantes.
Dias úteis = segunda a sábado, excluindo feriados nacionais fixos.
"""
from datetime import date, timedelta
import duckdb
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Feriados nacionais fixos (MM-DD)
FERIADOS_FIXOS = {
    "01-01",  # Confraternização Universal
    "04-21",  # Tiradentes
    "05-01",  # Dia do Trabalho
    "09-07",  # Independência
    "10-12",  # Nossa Senhora Aparecida
    "11-02",  # Finados
    "11-15",  # Proclamação da República
    "11-20",  # Consciência Negra
    "12-25",  # Natal
}


def is_dia_util(d: date) -> bool:
    """Segunda(0) a Sábado(5), excluindo feriados fixos."""
    if d.weekday() == 6:  # domingo
        return False
    if f"{d.month:02d}-{d.day:02d}" in FERIADOS_FIXOS:
        return False
    return True


def dias_uteis_mes(ano: int, mes: int) -> list[date]:
    """Retorna todos os dias úteis do mês."""
    d = date(ano, mes, 1)
    dias = []
    while d.month == mes:
        if is_dia_util(d):
            dias.append(d)
        d += timedelta(days=1)
    return dias


def calcular_previsao(csv_path: Path) -> dict:
    """
    Calcula previsão de faturamento do mês corrente.
    Retorna dict com dados para exibição.
    """
    hoje = date.today()
    ano, mes = hoje.year, hoje.month

    con = duckdb.connect()
    try:
        # Dias que já têm vendas no mês
        rows = con.execute(f"""
            SELECT
                CAST(DATA_MOVTO AS DATE) as dia,
                ROUND(SUM(VALOR_LIQUIDO), 2) as fat_dia,
                ROUND(SUM(QTDE_PRI), 2) as kg_dia
            FROM read_csv_auto('{csv_path}', header=true)
            WHERE MONTH(DATA_MOVTO) = {mes}
              AND YEAR(DATA_MOVTO) = {ano}
            GROUP BY dia
            ORDER BY dia
        """).fetchall()
        con.close()
    except Exception as e:
        con.close()
        logger.error(f"Erro no forecast: {e}")
        return {}

    if not rows:
        return {}

    dias_com_dados = [r[0] for r in rows]
    fat_total_realizado = sum(r[1] for r in rows)
    kg_total_realizado  = sum(r[2] for r in rows)
    n_dias_realizados   = len(dias_com_dados)

    # Média por dia realizado
    media_fat_dia = fat_total_realizado / n_dias_realizados
    media_kg_dia  = kg_total_realizado  / n_dias_realizados

    # Todos os dias úteis do mês
    todos_uteis = dias_uteis_mes(ano, mes)
    total_uteis_mes = len(todos_uteis)

    # Dias úteis restantes (após hoje, inclusive hoje se ainda não fechou)
    uteis_restantes = [d for d in todos_uteis if d > hoje]
    n_restantes = len(uteis_restantes)

    # Projeção
    fat_projetado = fat_total_realizado + (media_fat_dia * n_restantes)
    kg_projetado  = kg_total_realizado  + (media_kg_dia  * n_restantes)

    # % do mês executado
    uteis_ate_hoje = [d for d in todos_uteis if d <= hoje]
    pct_mes = round(len(uteis_ate_hoje) / total_uteis_mes * 100, 1)

    return {
        "mes_ano":              f"{mes:02d}/{ano}",
        "fat_realizado":        round(fat_total_realizado, 2),
        "kg_realizado":         round(kg_total_realizado, 2),
        "n_dias_realizados":    n_dias_realizados,
        "media_fat_dia":        round(media_fat_dia, 2),
        "media_kg_dia":         round(media_kg_dia, 2),
        "total_uteis_mes":      total_uteis_mes,
        "uteis_restantes":      n_restantes,
        "fat_projetado":        round(fat_projetado, 2),
        "kg_projetado":         round(kg_projetado, 2),
        "pct_mes_executado":    pct_mes,
    }
