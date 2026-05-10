import os
import logging
import anthropic

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
MODEL  = "claude-haiku-4-5-20251001"

# Mapeamento fixo das colunas conhecidas
SCHEMA_FIXO = """
COLUNAS DO CSV (separador ponto-e-vírgula):

IDENTIFICAÇÃO:
  - cod_filial        → código da filial (numérico)
  - NOME_FILIAL       → nome da filial: ITAP, BJESUS, PORC
  - COD_PRODUTO       → código do produto
  - DESC_PRODUTO      → descrição/nome do produto
  - COD_CLI_FOR       → código do cliente/fornecedor
  - NOME_CLIENTE      → nome do cliente
  - COD_VENDEDOR      → código do vendedor
  - NOM_VENDEDOR      → nome do vendedor

DOCUMENTO FISCAL:
  - NUM_DOCTO         → número da nota fiscal
  - SERIE_SEQ         → série da NF
  - CHAVE_ACESSO      → chave de acesso NF-e (44 dígitos)
  - COD_DOCTO         → código do tipo de documento
  - COD_TIPO_MV       → código do tipo de movimento
  - DESC_TIPO_MV      → descrição do tipo de movimento (ex: VENDA, DEVOLUÇÃO)
  - TIPO_OPERACAO     → tipo de operação

DATA:
  - DATA_MOVTO        → data do movimento (DATE) — usar para filtros de período

VALORES:
  - VALOR_LIQUIDO     → valor líquido da venda em R$ — principal coluna de faturamento
  - VALOR_UNITARIO    → valor unitário do produto em R$
  - PERC_DESCONTO     → percentual de desconto aplicado
  - PERC_COMISSAO     → percentual de comissão do vendedor

QUANTIDADES:
  - QTDE_PRI          → quantidade na unidade primária (kg)
  - QTDE_AUX          → quantidade na unidade auxiliar (caixas)
  - COD_UNIDADE_PRI   → unidade primária (ex: KG)
  - COD_UNIDADE_AUX   → unidade auxiliar (ex: CX)

LOCALIZAÇÃO:
  - UF                → estado do cliente
  - CIDADE            → cidade do cliente
  - COD_MUNICIPIO     → código do município

PRODUTO EXTRA:
  - MARCA             → marca do produto
  - MARCA_PROD        → marca específica do produto
  - DESC_DIVISAO2     → divisão/categoria nível 2
  - DESC_DIVISAO3     → divisão/categoria nível 3
  - QUEBRA            → indicador de quebra
  - PRAZO_CONGELAMENTO→ prazo de congelamento

LOGÍSTICA:
  - NOME_MOTORISTA    → nome do motorista
  - PLACA1            → placa do veículo
  - CPF_CGC           → CPF ou CNPJ do cliente

ITENS:
  - ITEM / NUM_ITEM / NUM_SUBITEM → identificadores de item na nota
  - CHAVE_FATO        → chave única do fato
  - NUM_DOCTO_AUX     → número de documento auxiliar
  - cod_vend_comp     → código do vendedor complementar
"""


def generate_sql(pergunta: str, schema_prompt: str) -> str:
    system = f"""Você é um analista de dados especialista em SQL DuckDB.
Converta perguntas em português para SQL válido.

{SCHEMA_FIXO}

REGRAS OBRIGATÓRIAS:
- A tabela se chama sempre: vendas
- Retorne APENAS o SQL puro, sem explicações, sem markdown, sem backticks
- Para faturamento/receita use sempre: VALOR_LIQUIDO
- Para volume/peso use: QTDE_PRI (kg)
- Para caixas use: QTDE_AUX
- Para datas use: DATA_MOVTO (tipo DATE)
- Para mês atual: WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE)
- Para hoje: WHERE DATA_MOVTO = CURRENT_DATE
- Para esta semana: WHERE DATA_MOVTO >= date_trunc('week', CURRENT_DATE)
- Sempre inclua LIMIT 200 no máximo
- Para rankings use ORDER BY ... DESC
- Para resumos use GROUP BY + SUM/COUNT
- Se não conseguir gerar SQL válido, retorne exatamente: ERRO: motivo

EXEMPLOS:
Pergunta: "resumo de vendas deste mês"
SQL: SELECT NOME_FILIAL, COUNT(DISTINCT NUM_DOCTO) as notas, ROUND(SUM(QTDE_PRI),2) as kg, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE) GROUP BY NOME_FILIAL ORDER BY faturamento DESC

Pergunta: "top 10 produtos do mês"
SQL: SELECT DESC_PRODUTO, ROUND(SUM(QTDE_PRI),2) as kg, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE) GROUP BY DESC_PRODUTO ORDER BY faturamento DESC LIMIT 10

Pergunta: "melhores clientes"
SQL: SELECT NOME_CLIENTE, CIDADE, UF, ROUND(SUM(QTDE_PRI),2) as kg, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE) GROUP BY NOME_CLIENTE, CIDADE, UF ORDER BY faturamento DESC LIMIT 20

Pergunta: "vendas por vendedor"
SQL: SELECT NOM_VENDEDOR, COUNT(DISTINCT NUM_DOCTO) as notas, ROUND(SUM(QTDE_PRI),2) as kg, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE) GROUP BY NOM_VENDEDOR ORDER BY faturamento DESC"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": pergunta}],
    )

    sql = response.content[0].text.strip()
    # remove backticks se a IA insistir
    sql = sql.replace("```sql", "").replace("```", "").strip()
    logger.info(f"SQL gerado: {sql[:300]}")
    return sql


def narrate_result(pergunta: str, resultado_texto: str, schema_prompt: str) -> str:
    system = """Você é um assistente de análise de vendas da Frinense Alimentos.
Recebeu dados em formato de tabela e deve responder de forma clara e objetiva em português.

REGRAS:
- Seja direto e objetivo
- Destaque os números mais importantes em negrito com **valor**
- Use R$ para valores monetários
- Use kg para volumes
- Máximo 4 parágrafos curtos
- Se os dados estiverem vazios, diga que não encontrou registros para o período
- ⛔ NUNCA invente dados que não estejam na tabela recebida"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Pergunta: {pergunta}\n\nDados:\n{resultado_texto}"
        }],
    )

    return response.content[0].text.strip()
