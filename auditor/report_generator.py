"""
Report Generator — Serialização e formatação do relatório final.

Converte o dict de auditoria em:
- JSON estruturado (para dashboard React)
- Markdown resumido (para leitura humana)
- Sumário executivo (para C-level)
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def to_json(audit_result: dict, pretty: bool = True) -> str:
    """
    Serializa resultado de auditoria para JSON.

    Args:
        audit_result: Dict retornado pelo orchestrator.
        pretty: Se True, formata com indentação.

    Returns:
        String JSON pronta para salvar ou enviar ao dashboard.
    """
    # Remove objetos não serializáveis (BeautifulSoup, etc.)
    clean = _clean_for_json(audit_result)

    return json.dumps(
        clean,
        indent=2 if pretty else None,
        ensure_ascii=False,
        default=str,
    )


def to_markdown(audit_result: dict) -> str:
    """
    Gera relatório em Markdown para leitura humana.

    Args:
        audit_result: Dict retornado pelo orchestrator.

    Returns:
        String Markdown formatada.
    """
    r = audit_result
    lines = []

    # Header
    lines.append(f"# GEO-SEO Audit Report — {r.get('brand_name', 'N/A')}")
    lines.append(f"")
    lines.append(f"**URL:** {r.get('url', 'N/A')}")
    lines.append(f"**Data:** {r.get('date', 'N/A')}")
    lines.append(f"**GEO Score:** {r.get('geo_score', 0)}/100")
    lines.append(f"**Duração:** {r.get('audit_duration_seconds', 0)}s")
    lines.append(f"")

    # Scores por categoria
    lines.append(f"## Scores por Categoria")
    lines.append(f"")
    scores = r.get("scores", {})
    for key, data in scores.items():
        lines.append(f"- **{data.get('label', key)}**: {data.get('value', 0)}/100 (peso: {data.get('weight', 0)}%)")
    lines.append(f"")

    # Platform readiness
    lines.append(f"## Readiness por Plataforma")
    lines.append(f"")
    platforms = r.get("platforms", {})
    for name, score in platforms.items():
        lines.append(f"- **{name}**: {score}/100")
    lines.append(f"")

    # Findings
    lines.append(f"## Findings ({len(r.get('findings', []))})")
    lines.append(f"")
    for i, f in enumerate(r.get("findings", []), 1):
        severity = f.get("severity", "info").upper()
        lines.append(f"### {i}. [{severity}] {f.get('title', 'N/A')}")
        lines.append(f"")
        lines.append(f"{f.get('description', '')}")
        lines.append(f"")
        if f.get("fix"):
            lines.append(f"**Fix:** {f['fix']}")
        if f.get("effort"):
            lines.append(f"**Esforço:** {f['effort']}")
        if f.get("impact_pts"):
            lines.append(f"**Impacto:** +{f['impact_pts']} pts")
        lines.append(f"")

    # Quick wins
    lines.append(f"## Quick Wins (priorizados por ROI)")
    lines.append(f"")
    for i, w in enumerate(r.get("quick_wins", []), 1):
        lines.append(f"{i}. **{w.get('action', '')}** — +{w.get('pts', 0)} pts | {w.get('effort', '')} | ROI: {w.get('roi', 0)}x")
    lines.append(f"")

    # Crawler summary
    crawlers = r.get("crawlers", {})
    summary = crawlers.get("summary", {})
    lines.append(f"## AI Crawlers")
    lines.append(f"")
    lines.append(f"- Permitidos: {summary.get('allowed_count', 0)}/{summary.get('total_crawlers', 0)}")
    lines.append(f"- Bloqueados críticos: {summary.get('critical_blocked_count', 0)}")
    lines.append(f"- llms.txt: {'Sim' if crawlers.get('llms_txt_exists') else 'Não'}")
    lines.append(f"")

    # Footer
    lines.append(f"---")
    lines.append(f"*Gerado por GEO-SEO Auditor v1.0 em {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def executive_summary(audit_result: dict) -> str:
    """
    Gera sumário executivo de 3-5 parágrafos para C-level.

    Args:
        audit_result: Dict retornado pelo orchestrator.

    Returns:
        String com sumário executivo.
    """
    r = audit_result
    score = r.get("geo_score", 0)
    brand = r.get("brand_name", "a empresa")
    findings = r.get("findings", [])
    quick_wins = r.get("quick_wins", [])
    crawlers = r.get("crawlers", {}).get("summary", {})

    # Tier
    if score >= 80:
        tier = "Excelente"
        outlook = "bem posicionada"
    elif score >= 60:
        tier = "Bom"
        outlook = "com boas fundações mas oportunidades de melhoria"
    elif score >= 40:
        tier = "Fraco"
        outlook = "com gaps significativos que precisam de atenção"
    else:
        tier = "Crítico"
        outlook = "com lacunas críticas que exigem ação imediata"

    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    total_impact = sum(w.get("pts", 0) for w in quick_wins)

    summary = f"""SUMÁRIO EXECUTIVO — GEO Audit {brand}

{brand} obteve um GEO Score de {score}/100 (tier: {tier}), indicando que está {outlook} para visibilidade em buscadores baseados em IA (ChatGPT, Perplexity, Google AI Overviews, Gemini, Bing Copilot).

Foram identificados {len(findings)} findings, sendo {critical_count} de severidade crítica. O site tem {crawlers.get('allowed_count', 0)} de {crawlers.get('total_crawlers', 0)} AI crawlers permitidos no robots.txt, com {crawlers.get('critical_blocked_count', 0)} crawlers críticos bloqueados — o que significa invisibilidade parcial para plataformas de IA.

As {len(quick_wins)} ações prioritárias identificadas (quick wins) podem adicionar até +{total_impact} pontos ao GEO Score, com ROI estimado calculado para cada ação. A maioria dos quick wins requer menos de 1 dia de esforço técnico.

O tráfego referido por IA cresceu +527% ano a ano e converte 4.4x mais que tráfego orgânico tradicional. A janela de oportunidade está aberta — apenas 23% dos profissionais de marketing estão investindo em GEO atualmente."""

    return summary


def _clean_for_json(obj):
    """Remove objetos não serializáveis recursivamente."""
    if isinstance(obj, dict):
        return {
            k: _clean_for_json(v)
            for k, v in obj.items()
            if k != "soup" and not callable(v)
        }
    elif isinstance(obj, (list, tuple)):
        return [_clean_for_json(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)
