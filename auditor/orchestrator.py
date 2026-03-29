"""
Orchestrator — Coordena todas as análises em uma auditoria GEO completa.

Fluxo de execução:
1. Fetch da página (HTML + metadata)
2. Fetch do robots.txt
3. Fetch do llms.txt
4. Análise paralela:
   a) Citabilidade de conteúdo
   b) Status de AI crawlers
   c) Presença de marca
   d) Schema markup
5. Cálculo do GEO Score composto
6. Geração de findings priorizados
7. Output JSON estruturado
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from config import (
    CATEGORY_WEIGHTS,
    DOMAIN_AUDIT_DEFAULT_SCOPE_PATH,
    DOMAIN_AUDIT_MAX_PAGES,
)

from .page_fetcher import fetch_page, fetch_robots_txt, fetch_llms_txt
from .citability_scorer import analyze_page_citability
from .crawler_checker import check_ai_crawlers
from .brand_scanner import scan_brand_presence
from .schema_analyzer import analyze_schema
from .url_discovery import discover_domain_urls

logger = logging.getLogger(__name__)


def run_full_audit(url: str, brand_name: str = None) -> dict:
    """
    Executa auditoria GEO completa de um URL.

    Args:
        url: URL da página principal a ser auditada.
        brand_name: Nome da marca (auto-detectado se não fornecido).

    Returns:
        dict completo com todos os scores, findings e recomendações.
        Este é o JSON que alimenta o dashboard React.
    """
    start_time = datetime.now(timezone.utc)
    domain = urlparse(url).netloc

    logger.info("═══ Starting GEO audit for %s ═══", url)

    # ── 1. Fetch da página ──
    logger.info("Step 1/5: Fetching page...")
    page_data = fetch_page(url)

    if page_data["error"]:
        logger.error("Failed to fetch page: %s", page_data["error"])
        return _build_error_result(url, domain, page_data["error"])

    # Auto-detect brand name from title
    if not brand_name:
        brand_name = _detect_brand_name(page_data)
        logger.info("Auto-detected brand name: %s", brand_name)

    # ── 2. Fetch robots.txt ──
    logger.info("Step 2/5: Checking robots.txt...")
    robots_txt = fetch_robots_txt(url)

    # ── 3. Fetch llms.txt ──
    logger.info("Step 2.5/5: Checking llms.txt...")
    llms_txt = fetch_llms_txt(url)

    # ── 4. Análises paralelas ──
    # 4a. Citabilidade
    logger.info("Step 3/5: Analyzing citability...")
    for block in page_data["content_blocks"]:
        block["source_url"] = page_data.get("url", url)
    citability = analyze_page_citability(page_data["content_blocks"])

    # 4b. Crawlers
    logger.info("Step 3/5: Checking AI crawlers...")
    crawlers = check_ai_crawlers(robots_txt, url, llms_txt)

    # 4c. Brand
    logger.info("Step 4/5: Scanning brand presence...")
    brand = scan_brand_presence(brand_name, domain)

    # 4d. Schema
    logger.info("Step 4/5: Analyzing schema markup...")
    schema = analyze_schema(page_data["soup"], url)

    # ── 5. Cálculo do GEO Score composto ──
    logger.info("Step 5/5: Computing composite score...")
    scores = _compute_category_scores(citability, crawlers, brand, schema, page_data)
    geo_score = _compute_geo_score(scores)

    # ── 6. Agregar findings ──
    all_findings = _aggregate_findings(citability, crawlers, brand, schema)
    quick_wins = _extract_quick_wins(all_findings)

    # ── 7. Montar resultado final ──
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    result = {
        # Metadata
        "url": url,
        "domain": domain,
        "brand_name": brand_name,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "audit_duration_seconds": round(elapsed, 1),

        # Scores
        "geo_score": geo_score,
        "scores": scores,

        # Platform readiness (estimativa baseada nos sub-scores)
        "platforms": _estimate_platform_readiness(scores, crawlers),

        # Page metadata
        "page": {
            "title": page_data["title"],
            "meta_description": page_data["meta_description"],
            "canonical": page_data["canonical"],
            "technology": page_data["technology"],
            "content_blocks_count": len(page_data["content_blocks"]),
        },

        # Citability detail
        "citability": {
            "average_score": citability["average_score"],
            "total_blocks": citability["total_blocks_analyzed"],
            "grade_distribution": citability["grade_distribution"],
            "optimal_length_count": citability["optimal_length_count"],
            "top_blocks": citability["top_5"],
            "bottom_blocks": citability["bottom_5"],
            "all_blocks": citability["scored_blocks"],
        },

        # Crawler detail
        "crawlers": {
            "summary": crawlers["summary"],
            "crawlers_list": crawlers["crawlers"],
            "robots_txt_exists": crawlers["robots_txt_exists"],
            "llms_txt_exists": crawlers["llms_txt_exists"],
            "sitemaps": crawlers["sitemaps"],
        },

        # Brand detail
        "brand": {
            "platforms": brand["platforms"],
            "recommendations": brand["recommendations"],
        },

        # Schema detail
        "schema": {
            "types_found": schema["schema_types"],
            "has_organization": schema["has_organization"],
            "has_faq": schema["has_faq"],
            "has_same_as": schema["has_same_as"],
            "same_as_urls": schema["same_as_urls"],
            "coverage_pct": schema["coverage_pct"],
            "recommended": schema["recommended_schemas"],
        },

        # Findings & actions
        "findings": all_findings,
        "quick_wins": quick_wins,
    }

    logger.info(
        "═══ Audit complete for %s — GEO Score: %d/100 (%d findings, %.1fs) ═══",
        domain, geo_score, len(all_findings), elapsed,
    )

    return result


def run_domain_audit(
    url: str,
    brand_name: str = None,
    scope_path: str = DOMAIN_AUDIT_DEFAULT_SCOPE_PATH,
    max_pages: int = DOMAIN_AUDIT_MAX_PAGES,
) -> dict:
    """Executa auditoria GEO em múltiplas URLs do domínio dentro do escopo informado."""
    start_time = datetime.now(timezone.utc)
    domain = urlparse(url).netloc

    logger.info("═══ Starting DOMAIN GEO audit for %s (scope=%s, max_pages=%d) ═══", url, scope_path, max_pages)

    urls = discover_domain_urls(url, scope_path=scope_path, max_urls=max_pages)
    if not urls:
        logger.warning("No URLs discovered for scope %s; falling back to single-page audit.", scope_path)
        return run_full_audit(url, brand_name=brand_name)

    # Detect brand from the base URL when missing.
    if not brand_name:
        base_page = fetch_page(url)
        if not base_page.get("error"):
            brand_name = _detect_brand_name(base_page)
        else:
            brand_name = domain.replace("www.", "").split(".")[0].title()

    robots_txt = fetch_robots_txt(url)
    llms_txt = fetch_llms_txt(url)
    crawlers = check_ai_crawlers(robots_txt, url, llms_txt)
    brand = scan_brand_presence(brand_name, domain)

    pages_ok = []
    page_errors = []
    all_content_blocks = []
    schema_results = []
    eeat_scores = []
    technical_scores = []

    for page_url in urls:
        page_data = fetch_page(page_url)
        if page_data.get("error"):
            page_errors.append({"url": page_url, "error": page_data.get("error")})
            continue

        pages_ok.append(page_data)
        for block in page_data.get("content_blocks", []):
            block["source_url"] = page_data.get("url", page_url)
        all_content_blocks.extend(page_data.get("content_blocks", []))

        schema_result = analyze_schema(page_data["soup"], page_url)
        schema_results.append(schema_result)

        page_citability = analyze_page_citability(page_data.get("content_blocks", []))
        eeat_scores.append(_estimate_eeat_score(page_citability, page_data))
        technical_scores.append(_estimate_technical_score(page_data))

    if not pages_ok:
        return _build_error_result(url, domain, "Nenhuma página do escopo pôde ser analisada")

    citability = analyze_page_citability(all_content_blocks)
    schema = _aggregate_schema_results(schema_results)

    platform_score = _estimate_platform_score(crawlers, schema)
    scores = {
        "ai_citability": {
            "value": citability["category_score"],
            "weight": CATEGORY_WEIGHTS["ai_citability"],
            "label": "AI Citability",
        },
        "brand_authority": {
            "value": brand["category_score"],
            "weight": CATEGORY_WEIGHTS["brand_authority"],
            "label": "Brand Authority",
        },
        "content_eeat": {
            "value": round(sum(eeat_scores) / len(eeat_scores)) if eeat_scores else 0,
            "weight": CATEGORY_WEIGHTS["content_eeat"],
            "label": "Content E-E-A-T",
        },
        "technical": {
            "value": round(sum(technical_scores) / len(technical_scores)) if technical_scores else 0,
            "weight": CATEGORY_WEIGHTS["technical"],
            "label": "Technical SEO",
        },
        "schema": {
            "value": schema["category_score"],
            "weight": CATEGORY_WEIGHTS["schema"],
            "label": "Schema Markup",
        },
        "platform_optimization": {
            "value": platform_score,
            "weight": CATEGORY_WEIGHTS["platform_optimization"],
            "label": "Platform Optimization",
        },
    }

    geo_score = _compute_geo_score(scores)
    platforms = _estimate_platform_readiness(scores, crawlers)
    all_findings = _aggregate_findings(citability, crawlers, brand, schema)
    quick_wins = _extract_quick_wins(all_findings)
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    logger.info(
        "═══ Domain audit complete for %s — %d/%d pages analyzed, GEO Score: %d/100 (%.1fs) ═══",
        domain,
        len(pages_ok),
        len(urls),
        geo_score,
        elapsed,
    )

    return {
        "url": url,
        "domain": domain,
        "brand_name": brand_name,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "audit_duration_seconds": round(elapsed, 1),
        "geo_score": geo_score,
        "scores": scores,
        "platforms": platforms,
        "page": {
            "title": pages_ok[0].get("title"),
            "meta_description": pages_ok[0].get("meta_description"),
            "canonical": pages_ok[0].get("canonical"),
            "technology": pages_ok[0].get("technology"),
            "content_blocks_count": len(all_content_blocks),
        },
        "scan_summary": {
            "mode": "domain_complete",
            "scope_path": scope_path,
            "pages_discovered": len(urls),
            "pages_analyzed": len(pages_ok),
            "pages_failed": len(page_errors),
            "max_pages": max_pages,
        },
        "sample_urls": [p.get("url") for p in pages_ok[:12]],
        "citability": {
            "average_score": citability["average_score"],
            "total_blocks": citability["total_blocks_analyzed"],
            "grade_distribution": citability["grade_distribution"],
            "optimal_length_count": citability["optimal_length_count"],
            "top_blocks": citability["top_5"],
            "bottom_blocks": citability["bottom_5"],
            "all_blocks": citability["scored_blocks"],
        },
        "crawlers": {
            "summary": crawlers["summary"],
            "crawlers_list": crawlers["crawlers"],
            "robots_txt_exists": crawlers["robots_txt_exists"],
            "llms_txt_exists": crawlers["llms_txt_exists"],
            "sitemaps": crawlers["sitemaps"],
        },
        "brand": {
            "platforms": brand["platforms"],
            "recommendations": brand["recommendations"],
        },
        "schema": {
            "types_found": schema["schema_types"],
            "has_organization": schema["has_organization"],
            "has_faq": schema["has_faq"],
            "has_same_as": schema["has_same_as"],
            "same_as_urls": schema["same_as_urls"],
            "coverage_pct": schema["coverage_pct"],
            "recommended": schema["recommended_schemas"],
        },
        "findings": all_findings,
        "quick_wins": quick_wins,
    }


def _detect_brand_name(page_data: dict) -> str:
    """Detecta nome da marca a partir do título da página."""
    title = page_data.get("title", "")
    if not title:
        return urlparse(page_data["url"]).netloc.replace("www.", "").split(".")[0].title()

    # Remove sufixos comuns de título
    for sep in [" | ", " - ", " — ", " :: ", " · "]:
        if sep in title:
            parts = title.split(sep)
            # O nome da marca geralmente é a parte mais curta
            return min(parts, key=len).strip()

    return title.strip()[:50]


def _compute_category_scores(citability, crawlers, brand, schema, page_data) -> dict:
    """Calcula scores por categoria."""
    # Content E-E-A-T é estimado a partir de citabilidade + sinais de tecnologia
    eeat_score = _estimate_eeat_score(citability, page_data)

    # Technical é estimado a partir de technology detection
    technical_score = _estimate_technical_score(page_data)

    # Platform optimization é estimado a partir de crawlers + schema
    platform_score = _estimate_platform_score(crawlers, schema)

    return {
        "ai_citability": {
            "value": citability["category_score"],
            "weight": CATEGORY_WEIGHTS["ai_citability"],
            "label": "AI Citability",
        },
        "brand_authority": {
            "value": brand["category_score"],
            "weight": CATEGORY_WEIGHTS["brand_authority"],
            "label": "Brand Authority",
        },
        "content_eeat": {
            "value": eeat_score,
            "weight": CATEGORY_WEIGHTS["content_eeat"],
            "label": "Content E-E-A-T",
        },
        "technical": {
            "value": technical_score,
            "weight": CATEGORY_WEIGHTS["technical"],
            "label": "Technical SEO",
        },
        "schema": {
            "value": schema["category_score"],
            "weight": CATEGORY_WEIGHTS["schema"],
            "label": "Schema Markup",
        },
        "platform_optimization": {
            "value": platform_score,
            "weight": CATEGORY_WEIGHTS["platform_optimization"],
            "label": "Platform Optimization",
        },
    }


def _compute_geo_score(scores: dict) -> int:
    """Calcula o GEO Score composto (média ponderada 0-100)."""
    total_weighted = sum(
        s["value"] * s["weight"] / 100
        for s in scores.values()
    )
    return round(total_weighted)


def _estimate_eeat_score(citability, page_data) -> int:
    """Estima score E-E-A-T a partir de sinais disponíveis."""
    score = 30  # base

    # Citabilidade boa indica conteúdo de qualidade
    if citability["average_score"] > 60:
        score += 20
    elif citability["average_score"] > 40:
        score += 10

    # SSR indica conteúdo renderizado (bom para crawlers)
    tech = page_data.get("technology", {})
    if tech.get("is_ssr"):
        score += 10

    # Meta description presente
    if page_data.get("meta_description"):
        score += 5

    # Título presente e informativo
    title = page_data.get("title", "")
    if title and len(title) > 20:
        score += 5

    return min(100, score)


def _estimate_technical_score(page_data) -> int:
    """Estima score técnico a partir de sinais disponíveis."""
    score = 40  # base (assumimos que o site funciona)

    tech = page_data.get("technology", {})

    # SSR
    if tech.get("is_ssr"):
        score += 15

    # Framework moderno
    if tech.get("framework"):
        score += 10

    # HTTPS (implícito se a URL é https)
    if page_data.get("url", "").startswith("https"):
        score += 10

    # Canonical definido
    if page_data.get("canonical"):
        score += 5

    # Meta description
    if page_data.get("meta_description"):
        score += 5

    return min(100, score)


def _estimate_platform_score(crawlers, schema) -> int:
    """Estima score de otimização por plataforma."""
    score = 0

    # Crawlers permitidos
    coverage = crawlers["summary"]["coverage_pct"]
    score += int(coverage * 0.5)

    # Schema ajuda em todas as plataformas
    if schema["category_score"] > 50:
        score += 20
    elif schema["category_score"] > 20:
        score += 10

    # llms.txt
    if crawlers["llms_txt_exists"]:
        score += 10

    return min(100, score)


def _estimate_platform_readiness(scores: dict, crawlers: dict) -> dict:
    """Estima readiness por plataforma de IA específica."""
    base = sum(s["value"] * s["weight"] / 100 for s in scores.values())

    # Ajuste por plataforma baseado em quais crawlers estão liberados
    allowed = {c["user_agent"] for c in crawlers["crawlers"] if c["status"] == "ALLOWED"}

    platforms = {}

    # Google AI Overviews — depende de Google-Extended e schema
    google_bonus = 10 if "Google-Extended" in allowed else -15
    platforms["Google AI Overviews"] = max(0, min(100, round(base + google_bonus + scores["schema"]["value"] * 0.1)))

    # ChatGPT — depende de GPTBot e Wikipedia presence
    chatgpt_bonus = 10 if "GPTBot" in allowed else -20
    platforms["ChatGPT Search"] = max(0, min(100, round(base + chatgpt_bonus)))

    # Perplexity — depende de PerplexityBot/ClaudeBot
    perp_bonus = 10 if "PerplexityBot" in allowed or "ClaudeBot" in allowed else -15
    platforms["Perplexity AI"] = max(0, min(100, round(base + perp_bonus)))

    # Gemini — depende de Google-Extended
    gemini_bonus = 5 if "Google-Extended" in allowed else -20
    platforms["Google Gemini"] = max(0, min(100, round(base + gemini_bonus - 5)))

    # Bing Copilot — depende de Bingbot
    bing_bonus = 10 if "Bingbot" in allowed else -10
    platforms["Bing Copilot"] = max(0, min(100, round(base + bing_bonus + 5)))

    return platforms


def _aggregate_findings(citability, crawlers, brand, schema) -> list[dict]:
    """Agrega e prioriza findings de todas as análises."""
    all_findings = []
    all_findings.extend(crawlers.get("findings", []))
    all_findings.extend(brand.get("findings", []))
    all_findings.extend(schema.get("findings", []))

    # Citability findings
    if citability["average_score"] < 50:
        all_findings.append({
            "severity": "high",
            "title": "Conteúdo com baixa citabilidade",
            "description": (
                f"Score médio de citabilidade: {citability['average_score']}/100. "
                f"Apenas {citability['optimal_length_count']} blocos na faixa ótima (134-167 palavras). "
                f"Conteúdo precisa ser reestruturado para formato citável por IA."
            ),
            "fix": "Reescrever top 10 páginas com blocos auto-contidos, fact-rich, 134-167 palavras",
            "effort": "1 semana",
            "impact_pts": 6,
        })

    # Ordena por severidade
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    all_findings.sort(key=lambda f: severity_order.get(f.get("severity", "info"), 5))

    return all_findings


def _extract_quick_wins(findings: list[dict]) -> list[dict]:
    """Extrai quick wins (alto impacto, baixo esforço) dos findings."""
    effort_scores = {
        "15 minutos": 1, "30 minutos": 2, "30 min": 2,
        "1 hora": 3, "1h": 3, "2 horas": 4, "2h": 4,
        "1 dia": 8, "1d": 8, "2-3 dias": 16, "3 dias": 20,
        "1 semana": 40, "2 semanas": 80, "2-4 semanas": 120,
    }

    quick_wins = []
    for f in findings:
        effort = f.get("effort", "")
        impact = f.get("impact_pts", 0)
        effort_score = effort_scores.get(effort, 50)

        if impact > 0:
            roi = impact / (effort_score / 10) if effort_score > 0 else 0
            quick_wins.append({
                "action": f.get("fix", f.get("title", "")),
                "pts": impact,
                "effort": effort,
                "roi": round(roi, 1),
                "severity": f.get("severity", "medium"),
            })

    # Ordena por ROI decrescente
    quick_wins.sort(key=lambda w: w["roi"], reverse=True)

    return quick_wins


def _build_error_result(url: str, domain: str, error: str) -> dict:
    """Retorna resultado de erro quando o fetch falha."""
    return {
        "url": url,
        "domain": domain,
        "brand_name": domain,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "geo_score": 0,
        "error": error,
        "scores": {},
        "findings": [{
            "severity": "critical",
            "title": "Falha ao acessar o site",
            "description": f"Não foi possível acessar {url}: {error}",
            "fix": "Verificar se o site está online e acessível",
            "effort": "Imediato",
            "impact_pts": 0,
        }],
    }


def _aggregate_schema_results(schema_results: list[dict]) -> dict:
    """Agrega resultados de schema em múltiplas páginas para um único resumo."""
    if not schema_results:
        return {
            "schema_types": [],
            "has_organization": False,
            "has_faq": False,
            "has_same_as": False,
            "same_as_urls": [],
            "coverage_pct": 0,
            "category_score": 0,
            "findings": [],
            "recommended_schemas": [],
        }

    schema_types = sorted({t for r in schema_results for t in r.get("schema_types", [])})
    same_as_urls = sorted({u for r in schema_results for u in r.get("same_as_urls", [])})
    findings = []
    seen_finding_titles = set()

    for r in schema_results:
        for f in r.get("findings", []):
            title = f.get("title")
            if title in seen_finding_titles:
                continue
            seen_finding_titles.add(title)
            findings.append(f)

    recommended = []
    seen_types = set()
    for r in schema_results:
        for rec in r.get("recommended_schemas", []):
            rec_type = rec.get("type")
            if rec_type in seen_types:
                continue
            seen_types.add(rec_type)
            recommended.append(rec)

    avg_coverage = round(sum(r.get("coverage_pct", 0) for r in schema_results) / len(schema_results))
    avg_score = round(sum(r.get("category_score", 0) for r in schema_results) / len(schema_results))

    return {
        "schema_types": schema_types,
        "has_organization": any(r.get("has_organization") for r in schema_results),
        "has_faq": any(r.get("has_faq") for r in schema_results),
        "has_same_as": any(r.get("has_same_as") for r in schema_results),
        "same_as_urls": same_as_urls,
        "coverage_pct": avg_coverage,
        "category_score": avg_score,
        "findings": findings,
        "recommended_schemas": recommended,
    }

