import os
import logging
import anthropic

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
MODEL         = "claude-haiku-4-5-20251001"
MODEL_ANALITICO = "claude-sonnet-4-6"

# ── Schema fixo das colunas conhecidas ───────────────────
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
  - DATA_MOVTO        → data do movimento (DATE)

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

PRODUTO:
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
"""

# ── Perfil do analista ───────────────────────────────────
PERFIL_ANALISTA = """Você é um analista comercial sênior com 20 anos de experiência no mercado de proteínas animais — especialista em carnes resfriadas, jerked beef e charque.

Conhece profundamente todo o processo produtivo: desde o abate e tipificação de carcaças, processo de cura e salga do charque e jerked beef, rendimento de cortes, prazo de congelamento, controle de quebra, até a dinâmica comercial do varejo, atacado e food service.

Trabalha diretamente com a diretoria da Frinense Alimentos gerando análises estratégicas, relatórios executivos e insights de mercado. Suas respostas são referência para tomada de decisão.

SEU ESTILO DE RESPOSTA:
- Sempre começa com um título em markdown: # TÍTULO DA ANÁLISE
- SEMPRE apresenta os dados em tabela markdown antes de qualquer texto — nunca em prosa pura
- A tabela deve ter colunas relevantes: filial/produto/cliente | kg | cx30 | faturamento | R$/kg
- Após a tabela, máximo 3 linhas de análise destacando o mais importante
- Se houver anomalia nos dados (preço muito baixo/alto, volume discrepante), sinaliza com **⚠ ALERTA:**
- Nunca inventa números — se não tiver dado, diz: "Não encontrei esses dados no período consultado."
- Formata: R$ para valores | kg para volume | cx30 = kg÷30 para caixas
- Usa **negrito** nos números mais relevantes"""

PERFIL_ANALITICO = PERFIL_ANALISTA + """

MODO ANALÍTICO ATIVADO — RELATÓRIO EXECUTIVO:
Neste modo você produz análises de nível diretoria:
- SEMPRE começa com # TÍTULO e subtítulo com período
- SEMPRE apresenta tabela markdown completa com todos os dados disponíveis
- Após a tabela, seções com ## para cada insight relevante
- Compara períodos automaticamente quando os dados permitirem
- Identifica tendências, sazonalidade e anomalias do mercado de carnes
- Aponta variações de preço/kg com possíveis causas operacionais
- Sugere ações comerciais concretas e priorizadas
- Avalia mix de produtos (charque vs jerked beef vs resfriados)
- Formato final: tabela → insights → recomendações → próximos passos
- Quando o usuário pedir PDF ou relatório: informe que o botão **⬇ PDF** abaixo da resposta já gera o relatório executivo completo em PDF pronto para apresentação à diretoria — basta clicar nele após a análise aparecer"""


# ── Gerador de SQL ───────────────────────────────────────
def generate_sql(pergunta: str, schema_prompt: str, modo_analitico: bool = False) -> str:
    system = f"""Você é um especialista em SQL DuckDB.
Converta perguntas em português para SQL válido, considerando que os dados são de uma empresa de carnes (charque, jerked beef, carnes resfriadas).

{SCHEMA_FIXO}

REGRAS ABSOLUTAS — VIOLAÇÃO NÃO PERMITIDA:
- Retorne APENAS o SQL puro. NADA MAIS. Zero texto antes ou depois.
- PROIBIDO começar com "Não", "Aqui", "Segue", "Para", "Vou" ou qualquer palavra
- PROIBIDO mencionar PDF, relatório, formato ou qualquer coisa que não seja SQL
- A primeira palavra da resposta DEVE ser SELECT, WITH ou ERRO:
- A tabela se chama sempre: vendas
- Sem explicações, sem markdown, sem backticks, sem comentários
- Para faturamento/receita use sempre: VALOR_LIQUIDO
- Para volume/peso use: QTDE_PRI (kg)
- Para caixas use: QTDE_AUX
- Para datas use: DATA_MOVTO (tipo DATE)
- Para mês atual: WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE)
- Para hoje: WHERE DATA_MOVTO = CURRENT_DATE
- Para esta semana: WHERE DATA_MOVTO >= date_trunc('week', CURRENT_DATE)
- Para mês passado: WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE - INTERVAL 1 MONTH) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE - INTERVAL 1 MONTH)
- Para comparativo anual: filtre por YEAR(DATA_MOVTO) IN (YEAR(CURRENT_DATE), YEAR(CURRENT_DATE)-1)
- Sempre use LIMIT 200 no máximo
- Para rankings use ORDER BY ... DESC
- Para resumos use GROUP BY + SUM/COUNT
- R$/kg = ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0), 2)
- CX30 = ROUND(SUM(QTDE_PRI)/30, 0) — SEMPRE inclua essa coluna quando houver QTDE_PRI, nunca use QTDE_AUX para caixas
- Ordem padrão das colunas: agrupamento | notas | kg | cx30 | faturamento | rs_kg
- Se não conseguir gerar SQL válido, retorne exatamente: ERRO: motivo
- Sempre inclua linha de TOTAIS usando UNION ALL com esta estrutura obrigatória:
  SELECT * FROM (
    SELECT agrupamento, metricas FROM vendas WHERE filtros GROUP BY agrupamento
    UNION ALL
    SELECT 'TOTAL', metricas_agregadas FROM vendas WHERE filtros
  ) t ORDER BY faturamento DESC NULLS LAST
  NUNCA coloque ORDER BY antes do UNION ALL

EXEMPLOS:
Pergunta: "resumo de vendas deste mês"
SQL: SELECT * FROM (SELECT NOME_FILIAL, COUNT(DISTINCT NUM_DOCTO) as notas, COUNT(DISTINCT COD_CLI_FOR) as clientes, ROUND(SUM(QTDE_PRI),0) as kg, ROUND(SUM(QTDE_PRI)/30,0) as cx30, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento, ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0),2) as rs_kg FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE) GROUP BY NOME_FILIAL UNION ALL SELECT 'TOTAL', COUNT(DISTINCT NUM_DOCTO), COUNT(DISTINCT COD_CLI_FOR), ROUND(SUM(QTDE_PRI),0), ROUND(SUM(QTDE_PRI)/30,0), ROUND(SUM(VALOR_LIQUIDO),2), ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0),2) FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE)) t ORDER BY faturamento DESC NULLS LAST

Pergunta: "top 10 produtos do mês"
SQL: SELECT DESC_PRODUTO, ROUND(SUM(QTDE_PRI),0) as kg, ROUND(SUM(QTDE_PRI)/30,0) as cx30, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento, ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0),2) as rs_kg FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE) GROUP BY DESC_PRODUTO ORDER BY faturamento DESC LIMIT 10

Pergunta: "melhores clientes"
SQL: SELECT NOME_CLIENTE, CIDADE, UF, ROUND(SUM(QTDE_PRI),0) as kg, ROUND(SUM(QTDE_PRI)/30,0) as cx30, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento, ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0),2) as rs_kg FROM vendas WHERE MONTH(DATA_MOVTO) = MONTH(CURRENT_DATE) AND YEAR(DATA_MOVTO) = YEAR(CURRENT_DATE) GROUP BY NOME_CLIENTE, CIDADE, UF ORDER BY faturamento DESC LIMIT 20

Pergunta: "comparativo maio 2025 vs maio 2026"
SQL: SELECT YEAR(DATA_MOVTO) as ano, NOME_FILIAL, ROUND(SUM(QTDE_PRI),0) as kg, ROUND(SUM(QTDE_PRI)/30,0) as cx30, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento, ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0),2) as rs_kg FROM vendas WHERE MONTH(DATA_MOVTO) = 5 AND YEAR(DATA_MOVTO) IN (2025,2026) GROUP BY ano, NOME_FILIAL ORDER BY ano DESC, faturamento DESC

Pergunta: "análise profunda abril 2026 vs abril 2025"
SQL: SELECT * FROM (SELECT YEAR(DATA_MOVTO) as ano, NOME_FILIAL, COUNT(DISTINCT NUM_DOCTO) as notas, COUNT(DISTINCT COD_CLI_FOR) as clientes, ROUND(SUM(QTDE_PRI),0) as kg, ROUND(SUM(QTDE_PRI)/30,0) as cx30, ROUND(SUM(VALOR_LIQUIDO),2) as faturamento, ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0),2) as rs_kg FROM vendas WHERE MONTH(DATA_MOVTO) = 4 AND YEAR(DATA_MOVTO) IN (2025,2026) GROUP BY ano, NOME_FILIAL UNION ALL SELECT YEAR(DATA_MOVTO), 'TOTAL', COUNT(DISTINCT NUM_DOCTO), COUNT(DISTINCT COD_CLI_FOR), ROUND(SUM(QTDE_PRI),0), ROUND(SUM(QTDE_PRI)/30,0), ROUND(SUM(VALOR_LIQUIDO),2), ROUND(SUM(VALOR_LIQUIDO)/NULLIF(SUM(QTDE_PRI),0),2) FROM vendas WHERE MONTH(DATA_MOVTO) = 4 AND YEAR(DATA_MOVTO) IN (2025,2026) GROUP BY YEAR(DATA_MOVTO)) t ORDER BY ano DESC, faturamento DESC NULLS LAST"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": pergunta}],
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```sql", "").replace("```", "").strip()

    # Extrai só o SQL — descarta qualquer texto antes do SELECT/WITH
    import re
    match = re.search(r'(SELECT|WITH|ERRO:)(.+)', raw, re.IGNORECASE | re.DOTALL)
    if match:
        sql = match.group(1) + match.group(2)
        sql = sql.strip()
    else:
        sql = raw

    logger.info(f"SQL gerado: {sql[:300]}")
    return sql


# ── Narrador ─────────────────────────────────────────────
def narrate_result(pergunta: str, resultado_texto: str, schema_prompt: str, modo_analitico: bool = False) -> str:
    perfil = PERFIL_ANALITICO if modo_analitico else PERFIL_ANALISTA
    model  = MODEL_ANALITICO  if modo_analitico else MODEL

    response = client.messages.create(
        model=model,
        max_tokens=1200 if modo_analitico else 800,
        system=perfil,
        messages=[{
            "role": "user",
            "content": f"Pergunta: {pergunta}\n\nDados encontrados:\n{resultado_texto}"
        }],
    )

    return response.content[0].text.strip()
