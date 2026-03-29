"""
Schema Analyzer — Detecção e análise de JSON-LD / schema.org.

Verifica a presença de dados estruturados no HTML de uma página,
avalia cobertura por tipo de schema, e gera recomendações de
schemas faltantes com base na vertical do negócio.
"""

import re
import json
import logging
from typing import Optional

from bs4 import BeautifulSoup

from config import SCHEMA_TYPES_PRIORITY

logger = logging.getLogger(__name__)


def analyze_schema(soup: BeautifulSoup, url: str) -> dict:
    """
    Analisa dados estruturados (JSON-LD) de uma página.

    Args:
        soup: Objeto BeautifulSoup da página parseada.
        url: URL da página para contexto.

    Returns:
        dict com schemas detectados, cobertura, score e recomendações.
    """
    result = {
        "url": url,
        "schemas_found": [],
        "schema_types": [],
        "has_organization": False,
        "has_website": False,
        "has_product": False,
        "has_faq": False,
        "has_breadcrumb": False,
        "has_article": False,
        "has_person": False,
        "has_same_as": False,
        "same_as_urls": [],
        "coverage_pct": 0,
        "category_score": 0,
        "findings": [],
        "recommended_schemas": [],
    }

    # ── Extrair JSON-LD blocks ──
    json_ld_blocks = _extract_json_ld(soup)
    result["schemas_found"] = json_ld_blocks

    # ── Identificar tipos ──
    all_types = set()
    for block in json_ld_blocks:
        types = _extract_types(block)
        all_types.update(types)

        # Verificar sameAs
        same_as = block.get("sameAs", [])
        if isinstance(same_as, str):
            same_as = [same_as]
        if same_as:
            result["has_same_as"] = True
            result["same_as_urls"].extend(same_as)

    result["schema_types"] = sorted(all_types)

    # ── Flags de presença ──
    result["has_organization"] = "Organization" in all_types or "Corporation" in all_types
    result["has_website"] = "WebSite" in all_types
    result["has_product"] = "Product" in all_types or "SoftwareApplication" in all_types or "Course" in all_types
    result["has_faq"] = "FAQPage" in all_types
    result["has_breadcrumb"] = "BreadcrumbList" in all_types
    result["has_article"] = "Article" in all_types or "BlogPosting" in all_types or "NewsArticle" in all_types
    result["has_person"] = "Person" in all_types

    # ── Cobertura ──
    priority_found = sum(1 for t in SCHEMA_TYPES_PRIORITY if t in all_types)
    result["coverage_pct"] = round(priority_found / len(SCHEMA_TYPES_PRIORITY) * 100)

    # ── Score ──
    result["category_score"] = _compute_schema_score(result)

    # ── Findings ──
    result["findings"] = _generate_schema_findings(result)

    # ── Recomendações ──
    result["recommended_schemas"] = _recommend_schemas(result)

    logger.info(
        "Schema analysis for %s: %d schemas found, types: %s, score: %d",
        url, len(json_ld_blocks), result["schema_types"], result["category_score"],
    )

    return result


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Extrai todos os blocos JSON-LD do HTML."""
    blocks = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            content = script.string
            if content:
                data = json.loads(content)
                # Se é um array, adiciona cada item
                if isinstance(data, list):
                    blocks.extend(data)
                else:
                    blocks.append(data)
        except json.JSONDecodeError as e:
            logger.debug("Invalid JSON-LD block: %s", str(e)[:100])
        except Exception as e:
            logger.debug("Error parsing JSON-LD: %s", str(e)[:100])
    return blocks


def _extract_types(schema: dict) -> set:
    """Extrai todos os @type de um schema, incluindo nested."""
    types = set()

    schema_type = schema.get("@type")
    if schema_type:
        if isinstance(schema_type, list):
            types.update(schema_type)
        else:
            types.add(schema_type)

    # Procura types em @graph
    graph = schema.get("@graph", [])
    if isinstance(graph, list):
        for item in graph:
            if isinstance(item, dict):
                types.update(_extract_types(item))

    # Procura types em propriedades nested
    for key, value in schema.items():
        if isinstance(value, dict) and "@type" in value:
            types.update(_extract_types(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "@type" in item:
                    types.update(_extract_types(item))

    return types


def _compute_schema_score(result: dict) -> int:
    """Calcula score da categoria schema (0-100)."""
    score = 0

    # Nenhum schema = 0
    if not result["schemas_found"]:
        return 0

    # Tem Organization ou equivalente (essencial)
    if result["has_organization"]:
        score += 25

    # Tem WebSite
    if result["has_website"]:
        score += 10

    # Tem Product/SoftwareApplication/Course
    if result["has_product"]:
        score += 20

    # Tem FAQ
    if result["has_faq"]:
        score += 15

    # Tem Article/BlogPosting
    if result["has_article"]:
        score += 10

    # Tem sameAs (entity linking)
    if result["has_same_as"]:
        score += 10
        # Bonus por quantidade de sameAs
        if len(result["same_as_urls"]) >= 5:
            score += 5

    # Tem BreadcrumbList
    if result["has_breadcrumb"]:
        score += 5

    return min(100, score)


def _generate_schema_findings(result: dict) -> list[dict]:
    """Gera findings de schema."""
    findings = []

    if not result["schemas_found"]:
        findings.append({
            "severity": "critical",
            "title": "Zero schema markup detectado",
            "description": (
                "Nenhum JSON-LD encontrado na página. Sem dados estruturados, "
                "LLMs não conseguem identificar a marca como entidade distinta. "
                "Schema é fundamental para entity recognition em IA."
            ),
            "fix": "Implementar Organization, WebSite e Product/Course JSON-LD schemas",
            "effort": "1-2 dias",
            "impact_pts": 8,
        })
        return findings

    if not result["has_organization"]:
        findings.append({
            "severity": "high",
            "title": "Sem Organization schema",
            "description": (
                "Nenhum schema Organization ou Corporation encontrado. "
                "Este é o schema mais fundamental para identity — "
                "sem ele, LLMs não sabem quem/o que é a entidade."
            ),
            "fix": "Adicionar Organization JSON-LD com name, url, logo, sameAs, foundingDate",
            "effort": "2 horas",
            "impact_pts": 4,
        })

    if not result["has_same_as"]:
        findings.append({
            "severity": "high",
            "title": "Sem sameAs no schema",
            "description": (
                "Nenhum sameAs encontrado no schema. sameAs conecta a entidade "
                "a perfis em outras plataformas (LinkedIn, YouTube, Wikipedia, Wikidata), "
                "reforçando entity disambiguation para LLMs."
            ),
            "fix": "Adicionar sameAs com links para todas as redes e plataformas",
            "effort": "30 minutos",
            "impact_pts": 3,
        })

    if not result["has_faq"]:
        findings.append({
            "severity": "medium",
            "title": "Sem FAQPage schema",
            "description": (
                "Nenhum FAQPage schema detectado. Perplexity e Google AI Overviews "
                "citam FAQ schema diretamente como fonte de respostas."
            ),
            "fix": "Implementar FAQPage JSON-LD nas páginas de FAQ e ajuda",
            "effort": "2 horas",
            "impact_pts": 3,
        })

    return findings


def _recommend_schemas(result: dict) -> list[dict]:
    """Gera lista de schemas recomendados que estão faltando."""
    recommendations = []

    essential = [
        ("Organization", "Identidade da entidade — nome, logo, endereço, redes sociais"),
        ("WebSite", "Metadata do site — nome, URL, SearchAction"),
        ("BreadcrumbList", "Navegação estruturada para AI crawlers"),
    ]

    product_schemas = [
        ("Product", "Produtos individuais com offers e ratings"),
        ("SoftwareApplication", "Se é uma plataforma SaaS"),
        ("Course", "Se oferece cursos/educação"),
    ]

    content_schemas = [
        ("Article", "Posts de blog e conteúdo editorial"),
        ("FAQPage", "Páginas de FAQ — alto impacto em citações IA"),
        ("HowTo", "Tutoriais passo a passo"),
        ("Person", "Autores/experts com credenciais (E-E-A-T)"),
    ]

    for schema_type, description in essential + product_schemas + content_schemas:
        if schema_type not in result["schema_types"]:
            recommendations.append({
                "type": schema_type,
                "description": description,
                "priority": "essential" if schema_type in dict(essential) else "recommended",
            })

    return recommendations
