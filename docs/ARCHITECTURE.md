# Arquitetura — GEO-SEO Auditor v1.0.1

## Visão geral

O GEO-SEO Auditor é composto por três camadas independentes:

1. **Engine de análise** (`auditor/`) — coleta dados reais e calcula scores via regras heurísticas
2. **Servidor web** (`server.py`) — expõe a engine como API REST e serve o dashboard
3. **Dashboard React** (`static/index.html`) — visualização interativa que consome o JSON de output

```
┌─────────────────────────────────────────────────────────────┐
│                     Interfaces de entrada                    │
│                                                             │
│   CLI (main.py)              Dashboard / API REST            │
│   audit | citability         POST /api/audit                │
│   crawlers | brand           POST /api/audit/domain         │
│   schema                     GET  /api/latest               │
└──────────────┬───────────────────────┬──────────────────────┘
               │                       │
               └───────────┬───────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      orchestrator.py                        │
│   run_full_audit()  ·  run_domain_audit()                   │
│   Coordena análises → calcula GEO Score → gera relatório    │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
  │  page_  │ │citability│ │crawler_│ │ brand_ │ │ schema_  │
  │fetcher  │ │ _scorer  │ │checker │ │scanner │ │ analyzer │
  └────┬────┘ └──────────┘ └────────┘ └────────┘ └──────────┘
       │
  url_discovery.py
  (domain audits)
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│                      Outputs gerados                         │
│                                                             │
│   JSON estruturado · Markdown · Sumário executivo           │
└──────────────────┬───────────────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
  Dashboard React          BigQuery
  (static/index.html)   (histórico)
       │
       └── Agente Letícia (Google ADK)
           Chat conversacional sobre os dados
```

---

## Módulos

### `main.py` — CLI

Ponto de entrada via linha de comando. Parseia argumentos e delega ao orchestrator ou a módulos individuais. Suporta os subcomandos `audit`, `citability`, `crawlers`, `brand` e `schema`, além dos flags `--format` (json/markdown/executive) e `--output`.

---

### `server.py` — Servidor FastAPI

Expõe a engine como API REST e serve o dashboard HTML. Gerencia o ciclo de vida do agente Letícia (Google ADK) e despacha saves no BigQuery como `BackgroundTask` para não bloquear respostas.

**Endpoints:**

| Método | Path | Descrição |
|---|---|---|
| `GET` | `/` | Dashboard HTML |
| `GET` | `/api/health` | Health check (Cloud Run) |
| `GET` | `/api/latest` | Última auditoria salva |
| `GET` | `/api/history` | Histórico (até 100 registros) |
| `POST` | `/api/audit` | Auditoria de página única |
| `POST` | `/api/audit/domain` | Auditoria de domínio completo |
| `POST` | `/api/crawlers` | Análise de crawlers isolada |
| `POST` | `/api/brand` | Brand scan isolado |
| `POST` | `/api/chat` | Chat com Letícia |

---

### `auditor/page_fetcher.py`

Fetch HTTP com headers de browser real (User-Agent Chrome, Accept-Language) e parse de HTML com BeautifulSoup + lxml.

Responsabilidades:
- Extrair blocos de conteúdo (heading + parágrafos agrupados por h1–h4)
- Descartar elementos de ruído (`<nav>`, `<footer>`, `<script>`, `<form>`)
- Detectar tecnologia da página: framework JS (React, Vue, Next.js, Angular), CMS (WordPress, Shopify, Wix, HubSpot), modo de renderização (SSR vs SPA)
- Fazer fetch de `robots.txt` e `llms.txt`

---

### `auditor/citability_scorer.py`

Score de citabilidade (0–100) por bloco de conteúdo em 5 dimensões ponderadas:

| Dimensão | Peso |
|---|---|
| Answer Block Quality | 30% |
| Self-Containment | 25% |
| Structural Readability | 20% |
| Statistical Density | 15% |
| Uniqueness Signals | 10% |

O score bruto é multiplicado por um fator de comprimento. A faixa ideal é **134–167 palavras** — blocos fora dessa faixa recebem penalidade progressiva. Os padrões semânticos cobrem inglês e português (PT-BR).

Grades finais: A (≥80) · B (65–79) · C (50–64) · D (35–49) · F (<35)

---

### `auditor/crawler_checker.py`

Parse completo de `robots.txt` e verificação de 15 crawlers de IA:

**Críticos (7):** GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, anthropic-ai, PerplexityBot, Google-Extended

**Adicionais (8):** Googlebot, Bingbot, Meta-ExternalAgent, Bytespider, cohere-ai, Diffbot, CCBot, YouBot

O algoritmo de parse segue a especificação RFC 9309: match exato de User-agent com fallback para wildcard (`*`), regra mais específica (caminho mais longo) vence em conflito entre Allow e Disallow.

---

### `auditor/brand_scanner.py`

Verifica a presença da marca nas plataformas com maior correlação com citações de IA (dados: Ahrefs, dez 2025).

- **Automático via API:** Wikipedia Search API (EN + PT-BR), Wikidata Entity Search
- **Semi-automático (checklist):** YouTube, Reddit, LinkedIn e 8 plataformas adicionais — gera URLs de busca para verificação manual

---

### `auditor/schema_analyzer.py`

Extrai e analisa blocos `<script type="application/ld+json">`. Lida com `@graph` aninhado e `@type` como string ou array. Rastreia 16 tipos prioritários e extrai URLs `sameAs` para entity disambiguation.

---

### `auditor/orchestrator.py`

Coordenador central que:
1. Aciona fetch de página, `robots.txt` e `llms.txt`
2. Executa os quatro módulos de análise
3. Calcula o GEO Score como média ponderada das categorias
4. Estima readiness por plataforma de IA (ChatGPT, Perplexity, Gemini, Bing, Google AIO)
5. Agrega e prioriza findings por severidade
6. Extrai quick wins ordenados por ROI (`impact_pts / effort_days`)

---

### `auditor/url_discovery.py`

Descobre URLs de um domínio para auditorias em escala. Estratégia em cascata:
1. Parseia `/sitemap.xml` (com suporte a sitemap index)
2. Filtra por `scope_path` (padrão configurável)
3. Deduplica e normaliza URLs
4. Fallback: crawl BFS de links internos se o sitemap for insuficiente

---

### `agentes/leticia/` — Agente conversacional

Analista de GEO construída com Google ADK + Gemini 2.5 Flash. Mantém contexto de sessão em memória e tem acesso a 10 ferramentas tipadas que chamam a mesma engine de análise do backend.

```
agent.py    — definição do agente, modelo, tools e configuração
prompts.py  — system prompt com persona e instruções analíticas
tools.py    — 10 ferramentas: get_geo_score, get_citability_analysis,
              get_crawler_status, get_brand_presence, get_schema_analysis,
              get_quick_wins, get_findings, run_page_audit,
              compare_with_competitor, get_platform_readiness
```

---

### `bigquery_store.py` — Persistência

Streaming insert assíncrono para `{project}.geo_seo_auditor.audits`. A tabela é particionada por dia e clusterizada por domínio.

Schema: `audit_id`, `created_at`, `domain`, `url`, `geo_score`, scores individuais de cada categoria, `raw_result` (JSON completo).

---

### `static/index.html` — Dashboard React

Arquivo HTML único e autocontido (~3.000 linhas). React 18, Recharts e Babel são servidos via `static/vendor/` — sem build step, sem node_modules.

**9 abas:** Overview · Plataformas · Citabilidade · Crawlers · Brand · Schema · Findings · Roadmap · Chat

**Design:** dark theme (#0f172a), system font stack, animações com CSS stagger progressivo, gauges circulares via `stroke-dashoffset`.

**Integração de dados:**
- **Modo servidor:** GET `/api/latest` ao carregar + POST `/api/audit` ao submeter URL
- **Modo standalone:** substitui o objeto `RAW` no topo do arquivo pelo JSON de output

---

## Fluxo de dados

```
URL + Brand Name
       │
       ▼
page_fetcher.py
├── GET {url}           → HTML → content_blocks, soup, meta
├── GET {url}/robots.txt
└── GET {url}/llms.txt
       │
       ├──────────────────────────────────────┐
       ▼                                      ▼
citability_scorer.py              crawler_checker.py
analyze_page_citability()         check_ai_crawlers()
       │                                      │
       ▼                                      ▼
schema_analyzer.py                brand_scanner.py
analyze_schema()                  scan_brand_presence()
       │                                      │
       └──────────────┬───────────────────────┘
                      ▼
              orchestrator.py
              ├── compute_weighted_score()   → geo_score
              ├── estimate_platform_scores() → chatgpt, perplexity...
              ├── aggregate_findings()       → sorted by severity
              └── extract_quick_wins()       → sorted by ROI
                      │
                      ▼
              build_result_dict()
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       JSON        Markdown   Executive
       output      report     summary
          │
          ├──→ HTTP response → Dashboard
          └──→ BigQuery (BackgroundTask, não bloqueia)
```

**Tempos típicos:**
- Página única: 5–10 segundos
- Domínio (60 páginas): 60–120 segundos
- Save BigQuery: < 100 ms (assíncrono)

---

## Princípios de design

**Scoring sem IA generativa.** Todo o cálculo de GEO Score usa regras linguísticas e heurísticas calibradas — sem chamadas a APIs de LLM. Isso garante custo zero por auditoria, velocidade < 10s e explicabilidade total de cada ponto.

**Módulos com contrato padronizado.** Cada módulo de análise recebe dados brutos e retorna `{score, findings, recommendations}`. O orchestrator combina sem acoplar à implementação de cada módulo.

**Frontend sem build.** O dashboard é um HTML único — qualquer editor pode abrir e modificar, deploy é trivial, e não há dependência de toolchain JavaScript.

**Persistência desacoplada.** O BigQuery é opcional. A engine funciona integralmente sem ele — o save é sempre assíncrono e nunca bloqueia a resposta ao usuário.
