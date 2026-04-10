"""
Letícia — Analista GEO-SEO Sênior (Google ADK Agent)

Uso local:
    cd agentes/
    adk run leticia          # terminal interativo
    adk web                  # UI web em http://localhost:8000

Requisitos:
    pip install google-adk google-cloud-bigquery
    Copiar .env.example → .env e preencher as variáveis.
"""

from google.adk.agents import Agent
from google.genai import types

from .prompts import INSTRUCTION
from . import tools


root_agent = Agent(
    name="leticia",

    # gemini-2.5-flash: melhor custo-benefício para análise conversacional
    # Para análises mais complexas, trocar por "gemini-2.5-pro"
    model="gemini-3-flash-preview",

    description=(
        "Letícia — Analista GEO-SEO Sênior especializada em visibilidade de marcas "
        "em plataformas de IA (ChatGPT, Perplexity, Google AI Overviews, Gemini, Bing Copilot). "
        "Responde perguntas sobre GEO Scores, citabilidade de conteúdo, AI crawlers, "
        "schema markup e oferece insights acionáveis baseados em dados reais de auditoria."
    ),

    instruction=INSTRUCTION,

    tools=[
        tools.buscar_ultima_auditoria,        # score geral e por categoria
        tools.buscar_historico_scores,        # tendência ao longo do tempo
        tools.analisar_citabilidade,          # blocos A–F, Answer Quality, faixa ideal
        tools.analisar_plataformas_ia,        # ChatGPT vs Perplexity vs Gemini vs ...
        tools.listar_findings,                # problemas priorizados por severidade
        tools.listar_quick_wins,              # ações ordenadas por ROI
        tools.verificar_crawlers_ia,          # robots.txt e llms.txt
        tools.calcular_potencial_pontos,      # business case e score projetado
        tools.analisar_seo_tecnico,           # schema, E-E-A-T, metadados, tecnologia
        tools.analisar_oportunidades_conteudo, # blocos para reescrever, faixa ideal, ação
    ],

    generate_content_config=types.GenerateContentConfig(
        # Temperatura baixa → respostas analíticas consistentes e reproduzíveis
        temperature=0.2,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.OFF,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.OFF,
            ),
        ],
    ),
)
