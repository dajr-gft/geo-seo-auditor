"""
Ferramentas BigQuery para a agente Letícia.

Cada tool retorna um dict com chave 'status':
  - "success"   → dados encontrados e retornados
  - "sem_dados" → nenhuma auditoria no BQ para o domínio
  - "error"     → falha técnica (mensagem em 'message')

Regras ADK para tools:
  - Type annotations em todos os parâmetros
  - Docstring obrigatória (vira a descrição que o LLM vê)
  - Nunca raise exceptions — retornar erro no dict
  - Retornar dict com chave 'status'
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT  = os.environ.get("GOOGLE_CLOUD_PROJECT", "ia-sandbox-bangalo")
_TABLE    = f"{_PROJECT}.geo_seo_auditor.audits"
_bq       = None  # lazy-init


def _client():
    global _bq
    if _bq is None:
        from google.cloud import bigquery
        _bq = bigquery.Client(project=_PROJECT)
        logger.info("BQ client iniciado (project=%s)", _PROJECT)
    return _bq


def _latest_raw(dominio: str) -> Optional[dict]:
    """Consulta BQ e retorna o raw_result mais recente para o domínio."""
    from google.cloud import bigquery
    q = f"""
        SELECT raw_result, created_at, audit_type
        FROM `{_TABLE}`
        WHERE domain = @d
        ORDER BY created_at DESC
        LIMIT 1
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("d", "STRING", dominio),
    ])
    rows = list(_client().query(q, job_config=cfg).result())
    if not rows:
        return None
    r = rows[0]
    data = json.loads(r.raw_result)
    data["_created_at"] = r.created_at.isoformat()
    data["_audit_type"]  = r.audit_type
    return data


# ── TOOLS ────────────────────────────────────────────────────────────────────

def buscar_ultima_auditoria(dominio: str = "hotmart.com") -> dict:
    """
    Busca o GEO Score mais recente e os scores por categoria para um domínio.

    Use quando o usuário perguntar sobre o estado atual, score geral, resumo
    executivo de performance GEO, ou quando precisar de contexto para outras análises.

    Args:
        dominio: Domínio a consultar (ex: "hotmart.com"). Default: "hotmart.com".

    Returns:
        dict com geo_score, scores por categoria (valor e peso), brand_name, data
        da auditoria, tipo (single_page ou domain) e páginas analisadas.
    """
    try:
        data = _latest_raw(dominio)
        if not data:
            return {
                "status": "sem_dados",
                "message": (
                    f"Nenhuma auditoria encontrada para '{dominio}'. "
                    "Execute uma auditoria pelo dashboard primeiro."
                ),
            }

        scores_raw = data.get("scores", {})
        scores = {
            k: {
                "valor":    v.get("value")  if isinstance(v, dict) else int(v or 0),
                "peso_pct": v.get("weight") if isinstance(v, dict) else None,
                "label":    v.get("label")  if isinstance(v, dict) else k,
            }
            for k, v in scores_raw.items()
        }

        plat_raw = data.get("platforms", {})
        plataformas = {
            name: (v.get("score") if isinstance(v, dict) else int(v or 0))
            for name, v in plat_raw.items()
        }

        scan = data.get("scan_summary") or {}

        return {
            "status":             "success",
            "dominio":            data.get("domain"),
            "marca":              data.get("brand_name"),
            "data_auditoria":     data.get("date"),
            "timestamp_bq":       data.get("_created_at"),
            "tipo_auditoria":     data.get("_audit_type"),
            "geo_score":          data.get("geo_score"),
            "duracao_segundos":   data.get("audit_duration_seconds"),
            "paginas_analisadas": scan.get("pages_analyzed", 1),
            "escopo_auditado":    scan.get("scope_path"),
            "scores_por_categoria": scores,
            "scores_por_plataforma": plataformas,
        }

    except Exception as e:
        logger.exception("buscar_ultima_auditoria")
        return {"status": "error", "message": str(e)}


def buscar_historico_scores(dominio: str = "hotmart.com", limite: int = 5) -> dict:
    """
    Retorna o histórico de GEO Scores ao longo do tempo para análise de tendência.

    Use quando o usuário perguntar sobre evolução, progresso, variação de scores
    entre auditorias, ou quiser comparar o estado atual com auditorias anteriores.

    Args:
        dominio: Domínio a consultar. Default: "hotmart.com".
        limite:  Número de auditorias a retornar (1–20). Default: 5.

    Returns:
        dict com lista de auditorias da mais recente para a mais antiga, score
        atual, score mais antigo, variação no período e histórico detalhado.
    """
    try:
        from google.cloud import bigquery

        limite = max(1, min(int(limite), 20))
        q = f"""
            SELECT
                created_at, audit_type, geo_score, pages_analyzed,
                score_ai_citability, score_brand_authority, score_content_eeat,
                score_technical, score_schema, score_platform_optimization
            FROM `{_TABLE}`
            WHERE domain = @d
            ORDER BY created_at DESC
            LIMIT {limite}
        """
        cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("d", "STRING", dominio),
        ])
        rows = list(_client().query(q, job_config=cfg).result())
        if not rows:
            return {"status": "sem_dados", "message": f"Nenhuma auditoria para '{dominio}'."}

        historico = [
            {
                "data":              r.created_at.isoformat(),
                "tipo":              r.audit_type,
                "geo_score":         r.geo_score,
                "paginas_analisadas": r.pages_analyzed,
                "scores": {
                    "ai_citability":         r.score_ai_citability,
                    "brand_authority":        r.score_brand_authority,
                    "content_eeat":           r.score_content_eeat,
                    "technical":              r.score_technical,
                    "schema":                 r.score_schema,
                    "platform_optimization":  r.score_platform_optimization,
                },
            }
            for r in rows
        ]

        variacao = (
            historico[0]["geo_score"] - historico[-1]["geo_score"]
            if len(historico) >= 2 else None
        )
        tendencia = (
            "melhora" if variacao and variacao > 0
            else "piora" if variacao and variacao < 0
            else "estável"
        )

        return {
            "status":            "success",
            "dominio":           dominio,
            "total_auditorias":  len(historico),
            "score_atual":       historico[0]["geo_score"],
            "score_mais_antigo": historico[-1]["geo_score"],
            "variacao_periodo":  variacao,
            "tendencia":         tendencia,
            "historico":         historico,
        }

    except Exception as e:
        logger.exception("buscar_historico_scores")
        return {"status": "error", "message": str(e)}


def analisar_citabilidade(dominio: str = "hotmart.com") -> dict:
    """
    Análise detalhada de citabilidade: distribuição de grades (A–F), métricas
    Answer Quality / Self-Containment / Statistical Density por bloco, e
    identificação dos melhores e piores blocos de conteúdo.

    Use quando o usuário perguntar sobre: citabilidade, blocos de conteúdo,
    Answer Quality, Self-Containment, faixa ideal de palavras (134–167),
    quais páginas/seções têm melhor ou pior performance para IA.

    Args:
        dominio: Domínio a consultar. Default: "hotmart.com".

    Returns:
        dict com score médio, distribuição de grades, blocos top-5/bottom-5,
        percentual na faixa ótima e insights acionáveis.
    """
    try:
        data = _latest_raw(dominio)
        if not data:
            return {"status": "sem_dados", "message": f"Nenhuma auditoria para '{dominio}'."}

        cit         = data.get("citability", {})
        all_blocks  = cit.get("all_blocks") or cit.get("top_blocks") or []
        grade_dist  = cit.get("grade_distribution", {})
        total       = cit.get("total_blocks_analyzed") or len(all_blocks) or 1

        ideal  = sum(1 for b in all_blocks if 134 <= b.get("word_count", 0) <= 167)
        curtos = sum(1 for b in all_blocks if b.get("word_count", 0) < 100)
        longos = sum(1 for b in all_blocks if b.get("word_count", 0) > 200)

        def _block_summary(b: dict) -> dict:
            bd = b.get("breakdown") or {}
            return {
                "titulo":          b.get("heading"),
                "score":           b.get("total_score"),
                "grade":           b.get("grade"),
                "palavras":        b.get("word_count"),
                "faixa_ideal":     134 <= b.get("word_count", 0) <= 167,
                "answer_quality":  round(bd.get("answer_block_quality", 0) * 3.33) if bd else None,
                "self_contain":    round(bd.get("self_containment", 0) * 4)         if bd else None,
                "stat_density":    round(bd.get("statistical_density", 0) * 6.67)   if bd else None,
                "url":             b.get("source_url"),
            }

        top5    = [_block_summary(b) for b in sorted(all_blocks, key=lambda b: b.get("total_score", 0), reverse=True)[:5]]
        bottom5 = [_block_summary(b) for b in sorted(all_blocks, key=lambda b: b.get("total_score", 0))[:5]]

        return {
            "status":                        "success",
            "dominio":                       dominio,
            "score_medio_citabilidade":      cit.get("average_score"),
            "total_blocos_analisados":       total,
            "blocos_faixa_ideal_134_167":    ideal,
            "pct_faixa_ideal":               round(ideal / total * 100, 1),
            "blocos_curtos_abaixo_100":      curtos,
            "blocos_longos_acima_200":       longos,
            "distribuicao_grades":           grade_dist,
            "referencia_grades": {
                "A (≥80)":    "Altamente citável — prioridade para manter",
                "B (65–79)": "Boa citabilidade — ajuste fino possível",
                "C (50–64)": "Moderada — reestruturar com foco em respostas diretas",
                "D (35–49)": "Baixa — reescrever priorizando Answer Quality",
                "F (<35)":   "Ruim — substituir ou refatorar completamente",
            },
            "top_5_mais_citaveis":  top5,
            "bottom_5_menos_citaveis": bottom5,
        }

    except Exception as e:
        logger.exception("analisar_citabilidade")
        return {"status": "error", "message": str(e)}


def analisar_plataformas_ia(dominio: str = "hotmart.com") -> dict:
    """
    Retorna o readiness score para cada plataforma de IA e identifica gaps.
    Plataformas: Google AI Overviews, ChatGPT Search, Perplexity AI, Google Gemini, Bing Copilot.

    Use quando o usuário perguntar: visibilidade em plataformas específicas,
    qual IA tem melhor/pior cobertura, como priorizar por canal, gap vs concorrente.

    Args:
        dominio: Domínio a consultar. Default: "hotmart.com".

    Returns:
        dict com scores por plataforma, ranking, gap vs líder, média geral
        e spread entre a melhor e pior plataforma.
    """
    try:
        data = _latest_raw(dominio)
        if not data:
            return {"status": "sem_dados", "message": f"Nenhuma auditoria para '{dominio}'."}

        plat_raw = data.get("platforms", {})
        if not plat_raw:
            return {"status": "sem_dados", "message": "Dados de plataformas não encontrados."}

        scores = {
            name: (v.get("score") if isinstance(v, dict) else int(v or 0))
            for name, v in plat_raw.items()
        }

        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        melhor  = ranking[0]
        pior    = ranking[-1]
        media   = round(sum(scores.values()) / len(scores))

        return {
            "status":               "success",
            "dominio":              dominio,
            "geo_score_geral":      data.get("geo_score"),
            "media_plataformas":    media,
            "scores_por_plataforma": scores,
            "ranking": [
                {
                    "posicao":       i + 1,
                    "plataforma":    p,
                    "score":         s,
                    "gap_vs_lider":  melhor[1] - s,
                    "tier":          (
                        "Excelente" if s >= 80 else
                        "Bom"       if s >= 60 else
                        "Fraco"     if s >= 40 else "Crítico"
                    ),
                }
                for i, (p, s) in enumerate(ranking)
            ],
            "melhor_plataforma": {"nome": melhor[0], "score": melhor[1]},
            "pior_plataforma":   {"nome": pior[0],   "score": pior[1]},
            "spread_max_min":    melhor[1] - pior[1],
        }

    except Exception as e:
        logger.exception("analisar_plataformas_ia")
        return {"status": "error", "message": str(e)}


def listar_findings(dominio: str = "hotmart.com", severidade: str = "") -> dict:
    """
    Lista os findings de auditoria ordenados por severidade e impacto.
    Cada finding contém o problema, contexto, ação corretiva, esforço e impacto em pts.

    Use quando o usuário perguntar: problemas encontrados, o que está errado, o que
    precisa ser corrigido, findings críticos/high/medium, ou para construir um plano de ação.

    Args:
        dominio:    Domínio a consultar. Default: "hotmart.com".
        severidade: Filtro opcional: "critical", "high", "medium", "low". Vazio = todos.

    Returns:
        dict com lista de findings, distribuição por severidade e impacto total em pts.
    """
    try:
        data = _latest_raw(dominio)
        if not data:
            return {"status": "sem_dados", "message": f"Nenhuma auditoria para '{dominio}'."}

        todos = data.get("findings", [])

        # normaliza campo severity vs sev
        for f in todos:
            if "sev" in f and "severity" not in f:
                f["severity"] = f["sev"]

        filtrados = (
            [f for f in todos if f.get("severity") == severidade]
            if severidade else todos
        )

        dist: dict[str, int] = {}
        for f in todos:
            sev = f.get("severity", "unknown")
            dist[sev] = dist.get(sev, 0) + 1

        return {
            "status":                   "success",
            "dominio":                  dominio,
            "total_findings":           len(filtrados),
            "distribuicao_severidade":  dist,
            "impacto_total_pts":        sum(f.get("impact_pts", 0) for f in filtrados),
            "filtro_aplicado":          severidade or "todos",
            "findings": [
                {
                    "severidade":      f.get("severity"),
                    "titulo":          f.get("title"),
                    "descricao":       f.get("description", f.get("desc")),
                    "acao_corretiva":  f.get("fix"),
                    "esforco":         f.get("effort"),
                    "impacto_pts":     f.get("impact_pts", 0),
                }
                for f in filtrados
            ],
        }

    except Exception as e:
        logger.exception("listar_findings")
        return {"status": "error", "message": str(e)}


def listar_quick_wins(dominio: str = "hotmart.com", top_n: int = 5) -> dict:
    """
    Lista as ações de maior ROI (impacto ÷ esforço) para melhorar o GEO Score.

    Use quando o usuário perguntar: o que fazer primeiro, como melhorar o score mais
    rápido, qual ação tem melhor custo-benefício, ou para montar um roadmap de sprint.

    Args:
        dominio: Domínio a consultar. Default: "hotmart.com".
        top_n:   Quantos quick wins retornar (1–10). Default: 5.

    Returns:
        dict com quick wins por ROI, impacto acumulado dos top-N e score projetado.
    """
    try:
        data = _latest_raw(dominio)
        if not data:
            return {"status": "sem_dados", "message": f"Nenhuma auditoria para '{dominio}'."}

        geo_score   = data.get("geo_score", 0)
        wins        = data.get("quick_wins", [])
        top_n       = max(1, min(int(top_n), 10))

        _esforco_h  = {
            "15 minutos": 0.25, "30min": 0.5, "30 min": 0.5, "30 minutos": 0.5,
            "1 hora": 1, "1h": 1, "2 horas": 2, "2h": 2,
            "1 dia": 8, "1d": 8, "2-3 dias": 20, "3 dias": 24,
            "1 semana": 40, "2 semanas": 80, "2-4 semanas": 120,
        }

        def _roi(w: dict) -> float:
            if w.get("roi"):
                return float(w["roi"])
            hrs = _esforco_h.get(w.get("effort", ""), 8)
            return round(w.get("pts", 0) / (hrs / 10), 1) if hrs else 0

        wins_com_roi = sorted(wins, key=_roi, reverse=True)
        top          = wins_com_roi[:top_n]

        ganho_todos = sum(w.get("pts", 0) for w in wins)
        ganho_top   = sum(w.get("pts", 0) for w in top)

        return {
            "status":                "success",
            "dominio":               dominio,
            "geo_score_atual":       geo_score,
            "score_projetado_total": min(100, geo_score + ganho_todos),
            "ganho_potencial_total": ganho_todos,
            "top_quick_wins": [
                {
                    "ranking":     i + 1,
                    "acao":        w.get("action"),
                    "categoria":   w.get("category"),
                    "impacto_pts": w.get("pts"),
                    "esforco":     w.get("effort"),
                    "roi":         _roi(w),
                    "roi_classe":  "Excelente" if _roi(w) >= 3 else "Bom" if _roi(w) >= 1 else "Baixo",
                }
                for i, w in enumerate(top)
            ],
            "impacto_acumulado_top_n": ganho_top,
        }

    except Exception as e:
        logger.exception("listar_quick_wins")
        return {"status": "error", "message": str(e)}


def verificar_crawlers_ia(dominio: str = "hotmart.com") -> dict:
    """
    Verifica o status dos AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended,
    Bingbot, etc.) no robots.txt e a existência do llms.txt.

    Use quando o usuário perguntar sobre: robots.txt, quais IAs podem rastrear o site,
    se o GPTBot ou ClaudeBot está bloqueado, cobertura de crawlers, llms.txt.

    Args:
        dominio: Domínio a consultar. Default: "hotmart.com".

    Returns:
        dict com status de cada crawler, cobertura percentual, crawlers críticos
        bloqueados, robots.txt e llms.txt presentes.
    """
    try:
        data = _latest_raw(dominio)
        if not data:
            return {"status": "sem_dados", "message": f"Nenhuma auditoria para '{dominio}'."}

        cr_data   = data.get("crawlers", {})
        cr_list   = cr_data.get("crawlers_list", [])
        summary   = cr_data.get("summary", {})

        permitidos = [c for c in cr_list if c.get("status") == "ALLOWED"]
        bloqueados = [c for c in cr_list if c.get("status") != "ALLOWED"]
        criticos_b = [c for c in bloqueados if c.get("critical")]

        cobertura = (
            summary.get("coverage_pct")
            or (round(len(permitidos) / len(cr_list) * 100) if cr_list else 0)
        )

        return {
            "status":                    "success",
            "dominio":                   dominio,
            "robots_txt_existe":         cr_data.get("robots_txt_exists"),
            "llms_txt_existe":           cr_data.get("llms_txt_exists"),
            "total_crawlers_verificados": len(cr_list),
            "permitidos":                len(permitidos),
            "bloqueados":                len(bloqueados),
            "criticos_bloqueados":       len(criticos_b),
            "cobertura_pct":             cobertura,
            "impacto_criticos_bloqueados": (
                "Sem crawlers críticos bloqueados — ótimo."
                if not criticos_b
                else f"{len(criticos_b)} crawler(s) crítico(s) bloqueado(s): "
                     + ", ".join(c.get("user_agent", "") for c in criticos_b)
            ),
            "crawlers_criticos_bloqueados": [
                {"user_agent": c.get("user_agent"), "plataforma": c.get("platform")}
                for c in criticos_b
            ],
            "lista_completa": [
                {
                    "user_agent": c.get("user_agent"),
                    "plataforma": c.get("platform"),
                    "status":     c.get("status"),
                    "critico":    c.get("critical"),
                }
                for c in cr_list
            ],
        }

    except Exception as e:
        logger.exception("verificar_crawlers_ia")
        return {"status": "error", "message": str(e)}


def calcular_potencial_pontos(dominio: str = "hotmart.com") -> dict:
    """
    Calcula o potencial máximo de melhoria do GEO Score implementando todos os quick wins.
    Projeta ganho por categoria e identifica as 3 ações de maior impacto imediato.

    Use quando o usuário quiser: score máximo alcançável, justificar ROI para stakeholders,
    priorizar esforço de otimização, ou montar um business case para GEO.

    Args:
        dominio: Domínio a consultar. Default: "hotmart.com".

    Returns:
        dict com score atual, projetado, ganho por categoria, top-3 ações e
        percentual de melhoria possível.
    """
    try:
        data = _latest_raw(dominio)
        if not data:
            return {"status": "sem_dados", "message": f"Nenhuma auditoria para '{dominio}'."}

        geo_score = data.get("geo_score", 0)
        wins      = data.get("quick_wins", [])
        findings  = data.get("findings", [])
        scores    = data.get("scores", {})

        ganho_total     = sum(w.get("pts", 0) for w in wins)
        score_projetado = min(100, geo_score + ganho_total)

        por_categoria: dict[str, int] = {}
        for w in wins:
            cat = w.get("category", "outros")
            por_categoria[cat] = por_categoria.get(cat, 0) + w.get("pts", 0)

        _esforco_h = {
            "30min": 0.5, "30 min": 0.5, "1 hora": 1, "1h": 1,
            "2 horas": 2, "2h": 2, "1 dia": 8, "1d": 8,
            "2-3 dias": 20, "3 dias": 24, "1 semana": 40,
        }
        top3 = sorted(
            wins,
            key=lambda w: w.get("pts", 0) / (_esforco_h.get(w.get("effort", ""), 8) / 10),
            reverse=True,
        )[:3]

        return {
            "status":                  "success",
            "dominio":                 dominio,
            "geo_score_atual":         geo_score,
            "geo_score_projetado":     score_projetado,
            "ganho_maximo_pts":        score_projetado - geo_score,
            "pct_melhoria_possivel":   round((score_projetado - geo_score) / max(geo_score, 1) * 100, 1),
            "total_quick_wins":        len(wins),
            "total_findings_abertos":  len(findings),
            "ganho_por_categoria":     dict(sorted(por_categoria.items(), key=lambda x: x[1], reverse=True)),
            "top3_maior_roi": [
                {
                    "acao":        w.get("action"),
                    "categoria":   w.get("category"),
                    "impacto_pts": w.get("pts"),
                    "esforco":     w.get("effort"),
                }
                for w in top3
            ],
            "scores_atuais": {
                k: (v.get("value") if isinstance(v, dict) else int(v or 0))
                for k, v in scores.items()
            },
        }

    except Exception as e:
        logger.exception("calcular_potencial_pontos")
        return {"status": "error", "message": str(e)}
