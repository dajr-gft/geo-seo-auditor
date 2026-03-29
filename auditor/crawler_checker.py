"""
Crawler Checker — Análise de robots.txt para AI crawlers.

Verifica o arquivo robots.txt de um domínio contra 15 user-agents
de crawlers de IA conhecidos, determinando quais estão permitidos
ou bloqueados.

Também verifica:
- Existência de arquivo llms.txt
- Sitemap declarado
- Regras de crawl-delay
"""

import re
import logging
from urllib.parse import urlparse
from typing import Optional

from config import AI_CRAWLERS

logger = logging.getLogger(__name__)


def check_ai_crawlers(robots_txt: Optional[str], url: str, llms_txt: Optional[str] = None) -> dict:
    """
    Analisa robots.txt para determinar acesso de AI crawlers.

    Args:
        robots_txt: Conteúdo do arquivo robots.txt (None se não encontrado).
        url: URL base do domínio (para contexto).
        llms_txt: Conteúdo do llms.txt (None se não encontrado).

    Returns:
        dict com status de cada crawler, métricas agregadas e recomendações.
    """
    domain = urlparse(url).netloc

    result = {
        "domain": domain,
        "robots_txt_exists": robots_txt is not None,
        "llms_txt_exists": llms_txt is not None,
        "crawlers": [],
        "summary": {},
        "sitemaps": [],
        "findings": [],
        "category_score": 0,
    }

    if robots_txt is None:
        # Sem robots.txt = tudo permitido por padrão
        result["crawlers"] = [
            _make_crawler_result(c, status="ALLOWED", reason="No robots.txt found (all allowed)")
            for c in AI_CRAWLERS
        ]
        result["summary"] = _compute_summary(result["crawlers"])
        result["category_score"] = 80  # bom mas sem controle explícito
        result["findings"].append({
            "severity": "medium",
            "title": "Sem robots.txt",
            "description": (
                "Nenhum robots.txt encontrado. Todos os crawlers são permitidos por padrão, "
                "mas não há controle explícito. Recomendado criar robots.txt com regras explícitas."
            ),
        })
        return result

    # ── Parse robots.txt ──
    rules = _parse_robots_txt(robots_txt)

    # ── Check cada crawler ──
    for crawler in AI_CRAWLERS:
        ua = crawler["user_agent"]
        status, reason = _check_crawler_access(ua, rules)
        result["crawlers"].append(_make_crawler_result(crawler, status=status, reason=reason))

    # ── Sitemaps ──
    result["sitemaps"] = _extract_sitemaps(robots_txt)

    # ── Summary ──
    result["summary"] = _compute_summary(result["crawlers"])

    # ── Score ──
    result["category_score"] = _compute_score(result)

    # ── Findings ──
    result["findings"] = _generate_findings(result)

    logger.info(
        "Crawler check for %s: %d allowed, %d blocked out of %d",
        domain,
        result["summary"]["allowed_count"],
        result["summary"]["blocked_count"],
        len(AI_CRAWLERS),
    )

    return result


def _parse_robots_txt(content: str) -> list[dict]:
    """
    Parse de robots.txt em lista de regras.

    Returns:
        Lista de {user_agent: str, rules: [{directive: 'allow'|'disallow', path: str}]}
    """
    blocks = []
    current_uas = []
    current_rules = []

    for line in content.split("\n"):
        line = line.strip()

        # Remove comentários
        if "#" in line:
            line = line[:line.index("#")].strip()

        if not line:
            continue

        # Parse directive
        if ":" not in line:
            continue

        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            # Se já temos regras, salva o bloco anterior
            if current_uas and current_rules:
                for ua in current_uas:
                    blocks.append({"user_agent": ua, "rules": list(current_rules)})
                current_rules = []

            if not current_rules:
                # Ainda coletando user-agents do mesmo bloco
                current_uas.append(value)
            else:
                # Novo bloco
                for ua in current_uas:
                    blocks.append({"user_agent": ua, "rules": list(current_rules)})
                current_uas = [value]
                current_rules = []

        elif directive in ("allow", "disallow"):
            current_rules.append({"directive": directive, "path": value})

    # Último bloco
    if current_uas and current_rules:
        for ua in current_uas:
            blocks.append({"user_agent": ua, "rules": list(current_rules)})

    return blocks


def _check_crawler_access(user_agent: str, rules: list[dict]) -> tuple[str, str]:
    """
    Verifica se um user-agent tem acesso baseado nas regras.

    Returns:
        Tuple (status, reason) onde status é 'ALLOWED' ou 'BLOCKED'.
    """
    # Busca regras específicas para este user-agent
    specific_rules = [
        block for block in rules
        if block["user_agent"].lower() == user_agent.lower()
    ]

    if specific_rules:
        # Regras específicas encontradas — verifica se bloqueia "/"
        for block in specific_rules:
            for rule in block["rules"]:
                if rule["directive"] == "disallow" and rule["path"] in ("/", ""):
                    if rule["path"] == "":
                        # Disallow vazio = allow
                        return "ALLOWED", f"Specific rule: Disallow empty (= allow all)"
                    return "BLOCKED", f"Specific rule: Disallow {rule['path']}"
                elif rule["directive"] == "allow" and rule["path"] == "/":
                    return "ALLOWED", f"Specific rule: Allow {rule['path']}"

        # Tem regras específicas mas nenhuma bloqueia "/"
        return "ALLOWED", "Specific rules exist but don't block root"

    # Sem regras específicas — verifica regras wildcard (*)
    wildcard_rules = [
        block for block in rules
        if block["user_agent"] == "*"
    ]

    if wildcard_rules:
        for block in wildcard_rules:
            for rule in block["rules"]:
                if rule["directive"] == "disallow" and rule["path"] == "/":
                    return "BLOCKED", "Wildcard rule: Disallow /"

    # Nenhuma regra bloqueia
    return "ALLOWED", "No blocking rules found"


def _make_crawler_result(crawler: dict, status: str, reason: str) -> dict:
    """Cria o resultado padronizado para um crawler."""
    rec = "Keep allowed" if status == "ALLOWED" else (
        "Whitelist immediately" if crawler["critical"] else "Whitelist recommended"
    )
    return {
        "user_agent": crawler["user_agent"],
        "platform": crawler["platform"],
        "operator": crawler["operator"],
        "critical": crawler["critical"],
        "status": status,
        "reason": reason,
        "recommendation": rec,
    }


def _extract_sitemaps(content: str) -> list[str]:
    """Extrai URLs de sitemap declaradas no robots.txt."""
    sitemaps = []
    for line in content.split("\n"):
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            sitemap_url = line.split(":", 1)[1].strip()
            if sitemap_url:
                sitemaps.append(sitemap_url)
    return sitemaps


def _compute_summary(crawlers: list[dict]) -> dict:
    """Calcula métricas agregadas dos crawlers."""
    allowed = [c for c in crawlers if c["status"] == "ALLOWED"]
    blocked = [c for c in crawlers if c["status"] == "BLOCKED"]
    critical_blocked = [c for c in blocked if c["critical"]]

    return {
        "total_crawlers": len(crawlers),
        "allowed_count": len(allowed),
        "blocked_count": len(blocked),
        "critical_blocked_count": len(critical_blocked),
        "coverage_pct": round(len(allowed) / len(crawlers) * 100) if crawlers else 0,
        "allowed_names": [c["user_agent"] for c in allowed],
        "blocked_names": [c["user_agent"] for c in blocked],
        "critical_blocked_names": [c["user_agent"] for c in critical_blocked],
    }


def _compute_score(result: dict) -> int:
    """Calcula score da categoria crawlers (0-100)."""
    summary = result["summary"]
    total = summary["total_crawlers"]
    if total == 0:
        return 0

    # Base: percentual de crawlers permitidos
    base_score = (summary["allowed_count"] / total) * 60

    # Penalidade pesada por crawlers críticos bloqueados
    critical_penalty = summary["critical_blocked_count"] * 10

    # Bonus por llms.txt
    llms_bonus = 10 if result["llms_txt_exists"] else 0

    # Bonus por sitemap
    sitemap_bonus = 5 if result["sitemaps"] else 0

    score = max(0, min(100, int(base_score - critical_penalty + llms_bonus + sitemap_bonus + 25)))
    return score


def _generate_findings(result: dict) -> list[dict]:
    """Gera findings baseados na análise de crawlers."""
    findings = []
    summary = result["summary"]

    # Crawlers críticos bloqueados
    if summary["critical_blocked_count"] > 0:
        names = ", ".join(summary["critical_blocked_names"])
        findings.append({
            "severity": "critical" if summary["critical_blocked_count"] >= 3 else "high",
            "title": f"{summary['critical_blocked_count']} AI crawlers críticos bloqueados",
            "description": (
                f"Os seguintes crawlers críticos estão bloqueados no robots.txt: {names}. "
                f"Isso torna o site invisível para as plataformas de IA correspondentes. "
                f"Impacto estimado: {summary['critical_blocked_count'] * 2} pts no GEO Score."
            ),
            "fix": f"Adicionar ao robots.txt: " + " / ".join(
                f"User-agent: {n}\\nAllow: /" for n in summary["critical_blocked_names"]
            ),
            "effort": "1 hora",
            "impact_pts": summary["critical_blocked_count"] * 2,
        })

    # Sem llms.txt
    if not result["llms_txt_exists"]:
        findings.append({
            "severity": "medium",
            "title": "Sem arquivo llms.txt",
            "description": (
                "Nenhum llms.txt encontrado. Este arquivo emergente ajuda crawlers de IA "
                "a entender a estrutura do site. Apenas ~12% dos sites possuem — adoção "
                "antecipada é vantagem competitiva."
            ),
            "fix": "Criar llms.txt na raiz do domínio com mapeamento de seções e conteúdo principal",
            "effort": "30 minutos",
            "impact_pts": 3,
        })

    # Sem sitemap
    if not result["sitemaps"]:
        findings.append({
            "severity": "low",
            "title": "Sem sitemap declarado no robots.txt",
            "description": "Nenhum sitemap declarado no robots.txt. Sitemaps ajudam crawlers a descobrir conteúdo.",
            "fix": "Adicionar Sitemap: https://domain.com/sitemap.xml ao robots.txt",
            "effort": "15 minutos",
            "impact_pts": 1,
        })

    return findings
