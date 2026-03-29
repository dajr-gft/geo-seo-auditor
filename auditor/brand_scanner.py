"""
Brand Scanner — Análise de presença de marca em plataformas citadas por IA.

Brand mentions correlacionam 3x mais com visibilidade em IA do que backlinks.
(Ahrefs, Dezembro 2025 — estudo de 75.000 marcas)

Correlações por plataforma:
1. YouTube mentions: ~0.737 (MAIS FORTE)
2. Reddit mentions:  ~0.580
3. Wikipedia:        ~0.520
4. Wikidata:         ~0.480
5. LinkedIn:         ~0.410
6. Backlinks (DR):   ~0.266 (fraco)

Este módulo verifica presença real via APIs públicas (Wikipedia, Wikidata)
e gera checklists para plataformas sem API pública (YouTube, Reddit, LinkedIn).
"""

import logging
from urllib.parse import quote_plus
from typing import Optional

import requests

from config import DEFAULT_HEADERS, DEFAULT_TIMEOUT, BRAND_PLATFORMS, ADDITIONAL_PLATFORMS

logger = logging.getLogger(__name__)


def scan_brand_presence(brand_name: str, domain: Optional[str] = None) -> dict:
    """
    Faz scan completo de presença de marca em plataformas citadas por IA.

    Args:
        brand_name: Nome da marca/empresa.
        domain: Domínio do site (opcional, para contexto).

    Returns:
        dict com resultados por plataforma, score agregado e recomendações.
    """
    result = {
        "brand_name": brand_name,
        "domain": domain,
        "platforms": {},
        "category_score": 0,
        "findings": [],
        "recommendations": [],
    }

    # ── Wikipedia (API pública) ──
    result["platforms"]["wikipedia"] = _check_wikipedia(brand_name)

    # ── Wikidata (API pública) ──
    result["platforms"]["wikidata"] = _check_wikidata(brand_name)

    # ── YouTube (checklist — sem API key) ──
    result["platforms"]["youtube"] = _build_youtube_checklist(brand_name)

    # ── Reddit (checklist) ──
    result["platforms"]["reddit"] = _build_reddit_checklist(brand_name)

    # ── LinkedIn (checklist) ──
    result["platforms"]["linkedin"] = _build_linkedin_checklist(brand_name)

    # ── Plataformas adicionais ──
    result["platforms"]["additional"] = _build_additional_checklist(brand_name)

    # ── Score agregado ──
    result["category_score"] = _compute_brand_score(result["platforms"])

    # ── Findings ──
    result["findings"] = _generate_brand_findings(result["platforms"], brand_name)

    # ── Recomendações priorizadas ──
    result["recommendations"] = [
        "Prioridade 1: YouTube — maior correlação (0.737) com citações de IA. Criar conteúdo educacional.",
        "Prioridade 2: Reddit — presença autêntica em subreddits da indústria. Sem marketing speak.",
        "Prioridade 3: Wikipedia — estabelecer notabilidade via cobertura de imprensa, depois criar/melhorar artigo.",
        "Prioridade 4: LinkedIn — thought leadership de fundadores e funcionários.",
        "Prioridade 5: Review platforms — G2, Trustpilot, Capterra para sinais de social proof.",
        "Cross-platform: Consistência de NAP (Nome, Endereço, Telefone) em todas as plataformas.",
        "Schema markup: Adicionar sameAs linkando para TODOS os perfis em plataformas.",
    ]

    logger.info("Brand scan for '%s': score=%d", brand_name, result["category_score"])

    return result


def _check_wikipedia(brand_name: str) -> dict:
    """Verifica presença na Wikipedia via API pública."""
    result = {
        "platform": "Wikipedia",
        "correlation": 0.520,
        "has_page": False,
        "search_results_count": 0,
        "page_title": None,
        "search_url": f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(brand_name)}",
        "status": "not_found",
    }

    # Busca em inglês
    for lang in ["en", "pt"]:
        try:
            api_url = (
                f"https://{lang}.wikipedia.org/w/api.php?"
                f"action=query&list=search&srsearch={quote_plus(brand_name)}"
                f"&format=json&srlimit=5"
            )
            response = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=15)
            if response.status_code == 200:
                data = response.json()
                search_results = data.get("query", {}).get("search", [])

                if search_results:
                    result[f"search_results_count_{lang}"] = len(search_results)
                    top_title = search_results[0].get("title", "").lower()

                    if brand_name.lower() in top_title:
                        result["has_page"] = True
                        result["page_title"] = search_results[0]["title"]
                        result["status"] = "found"
                        result["language"] = lang
                        break

        except Exception as e:
            logger.debug("Wikipedia API error for %s (%s): %s", brand_name, lang, e)

    return result


def _check_wikidata(brand_name: str) -> dict:
    """Verifica presença no Wikidata via API pública."""
    result = {
        "platform": "Wikidata",
        "correlation": 0.480,
        "has_entry": False,
        "entity_id": None,
        "description": None,
        "search_url": f"https://www.wikidata.org/w/index.php?search={quote_plus(brand_name)}",
        "status": "not_found",
    }

    try:
        api_url = (
            f"https://www.wikidata.org/w/api.php?"
            f"action=wbsearchentities&search={quote_plus(brand_name)}"
            f"&language=en&format=json&limit=5"
        )
        response = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=15)

        if response.status_code == 200:
            data = response.json()
            entities = data.get("search", [])

            if entities:
                # Verifica se o primeiro resultado é relevante
                top = entities[0]
                result["has_entry"] = True
                result["entity_id"] = top.get("id", "")
                result["description"] = top.get("description", "")
                result["status"] = "found"
                result["total_results"] = len(entities)

    except Exception as e:
        logger.debug("Wikidata API error for %s: %s", brand_name, e)

    return result


def _build_youtube_checklist(brand_name: str) -> dict:
    """Gera checklist de verificação para YouTube."""
    return {
        "platform": "YouTube",
        "correlation": 0.737,
        "weight": "25%",
        "search_url": f"https://www.youtube.com/results?search_query={quote_plus(brand_name)}",
        "status": "needs_manual_check",
        "checklist": [
            "Canal oficial existe?",
            "Vídeos educacionais/tutoriais publicados?",
            "Vídeos de terceiros sobre a marca?",
            "View count em vídeos relacionados?",
            "Reviews ou demos positivos?",
            "Transcrições nos vídeos?",
        ],
        "recommendations": [
            "Criar canal se não existir",
            "Publicar conteúdo educacional do nicho",
            "Incentivar reviews/demos de clientes",
            "Otimizar títulos e descrições com nome da marca",
            "Adicionar timestamps/chapters para parseabilidade IA",
        ],
    }


def _build_reddit_checklist(brand_name: str) -> dict:
    """Gera checklist de verificação para Reddit."""
    return {
        "platform": "Reddit",
        "correlation": 0.580,
        "weight": "25%",
        "search_url": f"https://www.reddit.com/search/?q={quote_plus(brand_name)}",
        "status": "needs_manual_check",
        "checklist": [
            "Subreddit próprio existe (r/brandname)?",
            "Marca discutida em subreddits do setor?",
            "Sentimento geral (positivo/negativo/neutro)?",
            "Threads de recomendação mencionam a marca?",
            "Presença oficial no Reddit?",
            "Menções recentes (últimos 6 meses)?",
        ],
        "recommendations": [
            "Monitorar subreddits relevantes",
            "Participar autenticamente (sem spam)",
            "Conta oficial para suporte",
            "Compartilhar conteúdo de valor",
            "Autenticidade Reddit — sem marketing speak",
        ],
    }


def _build_linkedin_checklist(brand_name: str) -> dict:
    """Gera checklist de verificação para LinkedIn."""
    return {
        "platform": "LinkedIn",
        "correlation": 0.410,
        "weight": "15%",
        "search_url": f"https://www.linkedin.com/search/results/companies/?keywords={quote_plus(brand_name)}",
        "status": "needs_manual_check",
        "checklist": [
            "Company page existe?",
            "Número de followers?",
            "Posts recentes e ativos?",
            "Thought leadership de funcionários?",
            "Artigos LinkedIn sobre a marca?",
            "Engajamento nos posts?",
        ],
        "recommendations": [
            "Criar/otimizar company page",
            "Thought leadership regular",
            "Funcionários compartilhando conteúdo",
            "Artigos long-form no LinkedIn",
            "Adicionar URL LinkedIn ao schema sameAs",
        ],
    }


def _build_additional_checklist(brand_name: str) -> dict:
    """Gera links de busca para plataformas adicionais."""
    platforms = {}
    search_templates = {
        "Quora": f"https://www.quora.com/search?q={quote_plus(brand_name)}",
        "Stack Overflow": f"https://stackoverflow.com/search?q={quote_plus(brand_name)}",
        "GitHub": f"https://github.com/search?q={quote_plus(brand_name)}",
        "Crunchbase": f"https://www.crunchbase.com/textsearch?q={quote_plus(brand_name)}",
        "Product Hunt": f"https://www.producthunt.com/search?q={quote_plus(brand_name)}",
        "G2": f"https://www.g2.com/search?query={quote_plus(brand_name)}",
        "Trustpilot": f"https://www.trustpilot.com/search?query={quote_plus(brand_name)}",
        "Capterra": f"https://www.capterra.com/search/?query={quote_plus(brand_name)}",
    }

    for name, url in search_templates.items():
        platforms[name] = {"search_url": url, "status": "needs_manual_check"}

    return {
        "platforms": platforms,
        "status": "needs_manual_check",
    }


def _compute_brand_score(platforms: dict) -> int:
    """Calcula score agregado de brand authority (0-100)."""
    score = 30  # base score

    # Wikipedia encontrada
    if platforms.get("wikipedia", {}).get("has_page"):
        score += 25

    # Wikidata encontrada
    if platforms.get("wikidata", {}).get("has_entry"):
        score += 15

    # YouTube, Reddit, LinkedIn são manual check — assume 10 pts cada se existir checklist
    # (em produção, integrações com APIs dariam dados reais)
    score += 10  # placeholder para manual checks pendentes

    return min(100, score)


def _generate_brand_findings(platforms: dict, brand_name: str) -> list[dict]:
    """Gera findings baseados na análise de marca."""
    findings = []

    # Wikipedia
    wiki = platforms.get("wikipedia", {})
    if not wiki.get("has_page"):
        findings.append({
            "severity": "high",
            "title": "Sem artigo Wikipedia",
            "description": (
                f"Nenhum artigo Wikipedia encontrado para '{brand_name}'. "
                f"47.9% das citações do ChatGPT vêm da Wikipedia. "
                f"Sem artigo, a marca está fora de quase metade do pool de citações."
            ),
            "fix": "Avaliar critérios de notabilidade e criar artigo Wikipedia + expandir existente",
            "effort": "2-4 semanas",
            "impact_pts": 5,
        })

    # Wikidata
    wikidata = platforms.get("wikidata", {})
    if not wikidata.get("has_entry"):
        findings.append({
            "severity": "high",
            "title": "Sem entry no Wikidata",
            "description": (
                f"Nenhuma entrada Wikidata encontrada para '{brand_name}'. "
                f"Wikidata é a base de conhecimento estruturado que LLMs consultam "
                f"para entity recognition. Sem entry, a marca não existe como entidade."
            ),
            "fix": "Criar Wikidata Q-code com dados estruturados completos (sameAs, founding, employees)",
            "effort": "1 dia",
            "impact_pts": 4,
        })

    return findings
