"""
GEO-SEO Auditor — Engine de análise.

Módulos de análise especializados que compõem a auditoria GEO completa:

- page_fetcher:       Fetch HTTP e parsing de HTML
- citability_scorer:  Score de citabilidade por IA
- crawler_checker:    Análise de robots.txt para AI crawlers
- brand_scanner:      Presença de marca em plataformas citadas por IA
- schema_analyzer:    Detecção e validação de JSON-LD / schema.org
- orchestrator:       Orquestração de todas as análises
- report_generator:   Geração do JSON final de relatório
"""

from .orchestrator import run_full_audit, run_domain_audit
from .page_fetcher import fetch_page
from .citability_scorer import analyze_page_citability
from .crawler_checker import check_ai_crawlers
from .brand_scanner import scan_brand_presence
from .schema_analyzer import analyze_schema

__all__ = [
    "run_full_audit",
    "run_domain_audit",
    "fetch_page",
    "analyze_page_citability",
    "check_ai_crawlers",
    "scan_brand_presence",
    "analyze_schema",
]
