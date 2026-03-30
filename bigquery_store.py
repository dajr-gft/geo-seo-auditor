"""
BigQuery store — persiste e recupera auditorias GEO.

Esquema da tabela `audits`:
  - Campos escalares para queries analíticas (scores, domain, dates)
  - Coluna `raw_result` (STRING/JSON) para recuperação completa do dashboard
  - Particionamento diário por `created_at` + clustering por `domain`
"""

import json
import uuid
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "ia-sandbox-bangalo")
DATASET_ID = "geo_seo_auditor"
TABLE_ID = "audits"
TABLE_REF = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

_client = None


def _get_client():
    """Lazy init do BQ client — reutiliza entre requests."""
    global _client
    if _client is None:
        from google.cloud import bigquery
        _client = bigquery.Client(project=PROJECT_ID)
        logger.info("BigQuery client initialized (project=%s)", PROJECT_ID)
    return _client


def save_audit(result: dict, audit_type: str = "single_page") -> str:
    """
    Persiste resultado de auditoria no BigQuery via streaming insert.

    Args:
        result: Dict limpo retornado por _clean_for_json (sem objetos BS4).
        audit_type: "single_page" | "domain"

    Returns:
        audit_id (UUID) gerado para este registro.
    """
    client = _get_client()
    audit_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    scores = result.get("scores", {})

    def _score(key: str) -> int:
        v = scores.get(key, {})
        return int(v.get("value", 0) if isinstance(v, dict) else v or 0)

    row = {
        "audit_id": audit_id,
        "created_at": now.isoformat(),
        "audit_type": audit_type,
        "url": result.get("url", ""),
        "domain": result.get("domain", ""),
        "brand_name": result.get("brand_name", ""),
        "audit_date": result.get("date", now.strftime("%Y-%m-%d")),
        "geo_score": int(result.get("geo_score", 0)),
        "audit_duration_seconds": float(result.get("audit_duration_seconds", 0.0)),
        "score_ai_citability": _score("ai_citability"),
        "score_brand_authority": _score("brand_authority"),
        "score_content_eeat": _score("content_eeat"),
        "score_technical": _score("technical"),
        "score_schema": _score("schema"),
        "score_platform_optimization": _score("platform_optimization"),
        "pages_analyzed": int((result.get("scan_summary") or {}).get("pages_analyzed", 1)),
        "raw_result": json.dumps(result, ensure_ascii=False, default=str),
    }

    errors = client.insert_rows_json(TABLE_REF, [row])
    if errors:
        raise RuntimeError(f"BigQuery streaming insert errors: {errors}")

    logger.info(
        "Audit saved | domain=%s type=%s score=%d id=%s",
        row["domain"], audit_type, row["geo_score"], audit_id,
    )
    return audit_id


def get_latest_audit(domain: str = None) -> Optional[dict]:
    """
    Retorna o raw_result da auditoria mais recente.

    Args:
        domain: Se fornecido, filtra pelo domínio. Caso contrário, retorna o
                registro mais recente de qualquer domínio.

    Returns:
        Dict com o resultado completo + metadados BQ (_bq_audit_id, _bq_timestamp),
        ou None se não houver registros.
    """
    from google.cloud import bigquery

    client = _get_client()

    if domain:
        query = f"""
            SELECT raw_result, created_at, audit_id, audit_type
            FROM `{TABLE_REF}`
            WHERE domain = @domain
            ORDER BY created_at DESC
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
        ])
    else:
        query = f"""
            SELECT raw_result, created_at, audit_id, audit_type
            FROM `{TABLE_REF}`
            ORDER BY created_at DESC
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig()

    rows = list(client.query(query, job_config=job_config).result())
    if not rows:
        return None

    row = rows[0]
    data = json.loads(row.raw_result)
    # Metadados de proveniência — usados pelo frontend
    data["_bq_audit_id"] = row.audit_id
    data["_bq_timestamp"] = row.created_at.isoformat()
    data["_bq_audit_type"] = row.audit_type
    return data


def get_audit_history(domain: str = None, limit: int = 10) -> list:
    """
    Retorna histórico resumido de auditorias (sem raw_result para eficiência).
    Ideal para listagem e comparação de scores ao longo do tempo.
    """
    from google.cloud import bigquery

    client = _get_client()
    where = "WHERE domain = @domain" if domain else ""
    params = (
        [bigquery.ScalarQueryParameter("domain", "STRING", domain)]
        if domain else []
    )

    query = f"""
        SELECT
            audit_id, created_at, audit_type, url, domain, brand_name,
            geo_score, audit_duration_seconds, pages_analyzed,
            score_ai_citability, score_brand_authority, score_content_eeat,
            score_technical, score_schema, score_platform_optimization
        FROM `{TABLE_REF}`
        {where}
        ORDER BY created_at DESC
        LIMIT {limit}
    """

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = list(client.query(query, job_config=job_config).result())

    return [
        {
            "audit_id": r.audit_id,
            "created_at": r.created_at.isoformat(),
            "audit_type": r.audit_type,
            "url": r.url,
            "domain": r.domain,
            "brand_name": r.brand_name,
            "geo_score": r.geo_score,
            "audit_duration_seconds": r.audit_duration_seconds,
            "pages_analyzed": r.pages_analyzed,
            "scores": {
                "ai_citability": r.score_ai_citability,
                "brand_authority": r.score_brand_authority,
                "content_eeat": r.score_content_eeat,
                "technical": r.score_technical,
                "schema": r.score_schema,
                "platform_optimization": r.score_platform_optimization,
            },
        }
        for r in rows
    ]