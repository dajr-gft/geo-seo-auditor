#!/usr/bin/env python3
"""
Setup BigQuery — cria dataset e tabela para o GEO-SEO Auditor.

Execute uma única vez antes do primeiro deploy:
    python setup_bigquery.py

Estrutura:
  Dataset : geo_seo_auditor  (southamerica-east1)
  Table   : audits
    - Particionada por DAY (created_at) → reduz custo de query
    - Clusterizada por (domain, audit_type) → acelera filtros comuns
    - raw_result STRING → JSON completo para o dashboard
    - Campos escalares → analytics / histórico de scores
"""

import os
from google.cloud import bigquery

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "ia-sandbox-bangalo")
DATASET_ID = "geo_seo_auditor"
TABLE_ID = "audits"
LOCATION = "southamerica-east1"


def setup():
    client = bigquery.Client(project=PROJECT_ID)

    # ── Dataset ──────────────────────────────────────────────────────────────
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset_ref.location = LOCATION
    dataset_ref.description = "GEO-SEO Auditor — histórico de auditorias GEO"
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"[OK] Dataset : {PROJECT_ID}.{DATASET_ID}  ({LOCATION})")

    # ── Schema ───────────────────────────────────────────────────────────────
    schema = [
        # Identidade
        bigquery.SchemaField(
            "audit_id", "STRING", mode="REQUIRED",
            description="UUID único desta auditoria",
        ),
        bigquery.SchemaField(
            "created_at", "TIMESTAMP", mode="REQUIRED",
            description="Momento da execução (UTC) — coluna de partição",
        ),
        bigquery.SchemaField(
            "audit_type", "STRING",
            description="single_page | domain",
        ),

        # Identificação do alvo
        bigquery.SchemaField("url", "STRING", description="URL auditada"),
        bigquery.SchemaField("domain", "STRING", description="Domínio extraído — coluna de cluster"),
        bigquery.SchemaField("brand_name", "STRING", description="Nome da marca"),
        bigquery.SchemaField("audit_date", "DATE", description="Data da auditoria (YYYY-MM-DD)"),

        # Score principal
        bigquery.SchemaField(
            "geo_score", "INTEGER",
            description="GEO Score composto 0–100 (média ponderada das 6 categorias)",
        ),
        bigquery.SchemaField(
            "audit_duration_seconds", "FLOAT",
            description="Tempo total de execução em segundos",
        ),

        # Scores por categoria (desnormalizados para queries analíticas rápidas)
        bigquery.SchemaField(
            "score_ai_citability", "INTEGER",
            description="AI Citability score 0–100 (peso 25%)",
        ),
        bigquery.SchemaField(
            "score_brand_authority", "INTEGER",
            description="Brand Authority score 0–100 (peso 20%)",
        ),
        bigquery.SchemaField(
            "score_content_eeat", "INTEGER",
            description="Content E-E-A-T score 0–100 (peso 20%)",
        ),
        bigquery.SchemaField(
            "score_technical", "INTEGER",
            description="Technical SEO score 0–100 (peso 15%)",
        ),
        bigquery.SchemaField(
            "score_schema", "INTEGER",
            description="Schema Markup score 0–100 (peso 10%)",
        ),
        bigquery.SchemaField(
            "score_platform_optimization", "INTEGER",
            description="Platform Optimization score 0–100 (peso 10%)",
        ),

        # Cobertura de páginas (para domain audits)
        bigquery.SchemaField(
            "pages_analyzed", "INTEGER",
            description="Número de páginas analisadas (1 para single_page)",
        ),

        # Resultado completo (para recuperação no dashboard)
        bigquery.SchemaField(
            "raw_result", "STRING",
            description="JSON completo do resultado — carregado pelo dashboard",
        ),
    ]

    # ── Table ────────────────────────────────────────────────────────────────
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    table = bigquery.Table(table_ref, schema=schema)

    # Particionamento diário — cada query escaneia apenas as partições necessárias
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="created_at",
        expiration_ms=None,  # sem expiração automática
    )

    # Clustering — acelera WHERE domain = '...' AND audit_type = '...'
    table.clustering_fields = ["domain", "audit_type"]

    client.create_table(table, exists_ok=True)
    print(f"[OK] Table    : {table_ref}")
    print(f"     Partitioned by : created_at (DAY)")
    print(f"     Clustered by   : domain, audit_type")
    print()
    print("Setup concluido.")


if __name__ == "__main__":
    setup()