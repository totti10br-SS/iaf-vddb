import os
import logging
import anthropic

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"


def generate_sql(pergunta: str, schema_prompt: str) -> str:
    system = f"""Você é um analista de dados. Sua tarefa é converter perguntas em português para SQL válido do DuckDB.

{schema_prompt}

REGRAS OBRIGATÓRIAS:
- A tabela se chama sempre: vendas
- Retorne APENAS o SQL, sem explicações, sem markdown, sem backticks
- Use apenas colunas que existem no schema acima
- Para datas, use funções do DuckDB: date_trunc, strftime, YEAR(), MONTH()
- Sempre use LIMIT 200 no máximo
- Se a pergunta for sobre totais/rankings, use GROUP BY + ORDER BY
- Se não conseguir gerar SQL válido, retorne exatamente: ERRO: motivo"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": pergunta}],
    )

    sql = response.content[0].text.strip()
    logger.info(f"SQL gerado: {sql[:200]}")
    return sql


def narrate_result(pergunta: str, resultado_texto: str, schema_prompt: str) -> str:
    system = f"""Você é um assistente de análise de vendas da Frinense Alimentos.
Receberá dados em formato de tabela e deve responder de forma clara e objetiva em português.

{schema_prompt}

REGRAS:
- Seja direto e objetivo
- Destaque os números mais importantes
- Use R$ para valores monetários quando aplicável
- Máximo 5 parágrafos curtos
- Se os dados estiverem vazios, diga que não encontrou registros
- ⛔ NUNCA invente dados que não estejam na tabela recebida"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Pergunta do usuário: {pergunta}\n\nDados encontrados:\n{resultado_texto}",
            }
        ],
    )

    return response.content[0].text.strip()
