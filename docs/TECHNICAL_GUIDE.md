# Guia Técnico — GEO-SEO Auditor

> **Versão:** 1.0.1 · **Stack:** Python 3.9+ · FastAPI · React 18 · Google ADK · BigQuery

Este documento cobre como cada parte do sistema foi construída, as decisões de design por trás de cada escolha e um guia prático para evoluir o produto sem quebrar o que já existe.

---

## Sumário

1. [Visão geral do produto](#1-visão-geral-do-produto)
2. [Decisões de arquitetura](#2-decisões-de-arquitetura)
3. [Estrutura de arquivos](#3-estrutura-de-arquivos)
4. [Stack tecnológica](#4-stack-tecnológica)
5. [Backend — como cada módulo foi construído](#5-backend--como-cada-módulo-foi-construído)
   - [5.1 page_fetcher.py](#51-page_fetcherpy--coleta-de-dados)
   - [5.2 citability_scorer.py](#52-citability_scorerpy--score-de-citabilidade)
   - [5.3 crawler_checker.py](#53-crawler_checkerpy--permissões-de-ai-crawlers)
   - [5.4 brand_scanner.py](#54-brand_scannerpy--presença-de-marca)
   - [5.5 schema_analyzer.py](#55-schema_analyzerpy--structured-data)
   - [5.6 orchestrator.py](#56-orchestratorpy--coordenador-central)
   - [5.7 url_discovery.py](#57-url_discoverypy--audit-de-domínio)
6. [Metodologia de scoring](#6-metodologia-de-scoring)
7. [Servidor web e API REST](#7-servidor-web-e-api-rest)
8. [Frontend — Dashboard React](#8-frontend--dashboard-react)
9. [Agente Letícia (Google ADK)](#9-agente-letícia-google-adk)
10. [Persistência — BigQuery](#10-persistência--bigquery)
11. [Fluxo de dados end-to-end](#11-fluxo-de-dados-end-to-end)
12. [Configuração e variáveis de ambiente](#12-configuração-e-variáveis-de-ambiente)
13. [Como executar localmente](#13-como-executar-localmente)
14. [Guia de evoluções](#14-guia-de-evoluções)

---

## 1. Visão geral do produto

O **GEO-SEO Auditor** é uma ferramenta de análise que avalia a "citabilidade" de um site por sistemas de IA generativa — ChatGPT, Perplexity, Gemini, Google AI Overviews e similares. O conceito central é o **GEO Score** (Generative Engine Optimization), uma nota de 0 a 100 que agrega seis dimensões de qualidade.

### Por que foi criado

Com a ascensão das respostas geradas por IA nos buscadores, o tráfego orgânico tradicional está migrando para "citações de IA". Um site bem posicionado no Google pode ter score zero de GEO se o conteúdo não estiver estruturado para ser citado por LLMs. Esta ferramenta identifica exatamente o que bloqueia ou favorece essa citabilidade.

### O que o produto entrega

| Saída | Uso |
|---|---|
| GEO Score (0-100) | Benchmark geral |
| Score por categoria (6) | Priorização de esforço |
| Findings com severidade | Backlog de correções |
| Quick Wins com ROI | Ações de alto impacto/baixo esforço |
| Relatório Markdown | Comunicação com stakeholders |
| Sumário executivo | C-level, apresentações |
| Dashboard interativo | Visualização e monitoramento |
| Chat com Letícia | Análise conversacional guiada |

---

## 2. Decisões de arquitetura

### 2.1 Scoring sem IA generativa

Todo o cálculo de GEO Score usa **regras linguísticas e heurísticas calibradas** — regex, contagem de palavras, padrões sintáticos — sem nenhuma chamada a APIs de LLM. Isso garante:

- **Velocidade:** análise de uma página em < 10 segundos
- **Custo zero:** sem token cost por auditoria
- **Explicabilidade:** cada ponto do score é rastreável a uma regra específica
- **Sem dependências externas:** funciona offline, sem API keys

A IA entra apenas na camada conversacional (agente Letícia), que é totalmente opcional e não afeta os scores.

### 2.2 Módulos independentes e orquestrador central

Cada dimensão de análise (citabilidade, crawlers, brand, schema) é um módulo Python autônomo com interface padronizada: recebe dados brutos e retorna um dicionário com `score`, `findings`, `recommendations`. O `orchestrator.py` os combina.

Isso permite:
- Testar e evoluir cada módulo isoladamente
- Adicionar novos módulos sem tocar no núcleo
- Reutilizar módulos via CLI individualmente

### 2.3 Frontend sem build step

O dashboard é um único `static/index.html` com React e Recharts carregados de `static/vendor/` (local, sem CDN externo). Não há bundler, transpiler ou node_modules. Isso simplifica o deploy (Cloud Run serve o arquivo diretamente), facilita edição (qualquer editor funciona) e elimina a camada de toolchain JavaScript como ponto de falha.

### 2.4 BigQuery como banco de dados

BigQuery foi escolhido por ser nativo no Google Cloud, suportar inserção por streaming, e fornecer SQL sobre histórico de auditorias sem necessidade de gerenciar infraestrutura de banco. A tabela é particionada por dia e clusterizada por domínio para queries eficientes.

### 2.5 Agente conversacional como camada separada

O agente Letícia (Google ADK) tem seu próprio session service e ciclo de vida dentro do processo do servidor. Ele não acessa o BigQuery diretamente — chama a mesma engine de análise do backend via tools tipadas. Isso mantém o agente stateless em relação ao banco e garante que qualquer análise feita via chat seja consistente com os scores exibidos no dashboard.

---

## 3. Estrutura de arquivos

```
geo-seo-auditor/
│
├── main.py                    # Ponto de entrada da CLI
├── server.py                  # Servidor FastAPI (API + dashboard)
├── config.py                  # Constantes globais e pesos de score
├── requirements.txt           # Dependências Python
├── bigquery_store.py          # Camada de persistência (BigQuery)
│
├── auditor/                   # Engine de análise (núcleo do produto)
│   ├── orchestrator.py        # Coordenador central — agrega tudo
│   ├── page_fetcher.py        # HTTP client + parser de HTML
│   ├── citability_scorer.py   # Score de citabilidade por bloco de conteúdo
│   ├── crawler_checker.py     # Análise de robots.txt + AI crawlers
│   ├── brand_scanner.py       # Presença de marca em plataformas
│   ├── schema_analyzer.py     # Detecção de JSON-LD e schema markup
│   └── url_discovery.py       # Descoberta de URLs via sitemap/crawl
│
├── agentes/leticia/           # Agente conversacional (Google ADK)
│   ├── agent.py               # Definição do agente e ferramentas
│   ├── prompts.py             # System prompt e instruções
│   ├── tools.py               # Ferramentas (data access, análises)
│   └── requirements.txt       # Dependências do agente
│
├── static/
│   ├── index.html             # Dashboard React (self-contained)
│   └── vendor/                # React, Recharts, Babel (local)
│
└── docs/
    ├── ARCHITECTURE.md        # Diagrama rápido de arquitetura
    └── TECHNICAL_GUIDE.md     # Este documento
```

---

## 4. Stack tecnológica

### Backend

| Componente | Tecnologia | Versão | Motivo da escolha |
|---|---|---|---|
| Framework web | FastAPI | 0.115+ | Async nativo, tipagem, auto-docs |
| App server | Uvicorn | 0.32+ | ASGI, performance para Cloud Run |
| HTTP client | requests | 2.31+ | Simplicidade, battle-tested |
| HTML parser | BeautifulSoup4 + lxml | 4.12+ / 5.0+ | Robustez com HTML malformado |
| Linguagem | Python | 3.9+ | Compatibilidade ampla |

### Dados e cloud

| Componente | Tecnologia | Motivo da escolha |
|---|---|---|
| Banco de dados | Google BigQuery | Serverless, streaming insert, SQL |
| Deploy | Google Cloud Run | Containerless, escala a zero |
| Auth | Application Default Credentials | Sem gestão de keys |

### Inteligência artificial

| Componente | Tecnologia | Motivo da escolha |
|---|---|---|
| Agente conversacional | Google ADK 1.0+ | Integração nativa com Gemini |
| Modelo | Gemini 2.5 Flash / 3 Flash Preview | Custo-benefício, baixa latência |
| Scoring de conteúdo | Regras heurísticas (sem IA) | Custo zero, explicável, rápido |

### Frontend

| Componente | Tecnologia | Motivo da escolha |
|---|---|---|
| Framework UI | React 18 | Reatividade, ecosistema |
| Gráficos | Recharts | Composable, compatível com React |
| Distribuição | HTML único + vendor local | Zero build step, fácil deploy |
| Estilo | CSS vanilla (dark theme) | Sem dependência extra, controle total |

### APIs externas

| API | Uso | Autenticação |
|---|---|---|
| Wikipedia Search API | Verificar presença de marca | Pública (sem key) |
| Wikidata Entity Search | Identificar entidade Wikidata | Pública (sem key) |
| robots.txt | Verificar permissões de crawlers | HTTP GET padrão |
| Sitemap XML | Descoberta de URLs do domínio | HTTP GET padrão |

---

## 5. Backend — como cada módulo foi construído

### 5.1 `page_fetcher.py` — Coleta de dados

**Responsabilidade:** Fazer o HTTP GET da página e estruturar o conteúdo para análise.

**Como funciona:**
1. Emite GET com headers de Chrome real (User-Agent, Accept-Language) para evitar bloqueios
2. Parseia o HTML com BeautifulSoup usando o parser `lxml` (mais tolerante a HTML inválido)
3. Remove tags de ruído: `<script>`, `<style>`, `<nav>`, `<footer>`, `<form>`, `<header>`
4. Percorre o DOM agrupando parágrafos sob o heading imediatamente anterior (h1–h4)
5. Descarta blocos com menos de 50 palavras (muito curtos para análise)
6. Detecta tecnologia da página: framework JS (React, Vue, Next.js, Angular), CMS (WordPress, Shopify, Wix, HubSpot), modo de renderização (SSR vs SPA)

**Estrutura de saída (content block):**
```python
{
    "heading": "Como funciona o modelo de afiliados",
    "content": "O modelo de afiliados da Hotmart permite que produtores...",
    "word_count": 142,
    "char_count": 891,
    "source_tag": "h2"
}
```

**Ponto de extensão:** Para suporte a páginas SPA sem SSR (conteúdo renderizado apenas no cliente), o ponto de integração com Playwright está neste módulo — ver [seção 14.1](#141-suporte-a-páginas-spa--javascript-pesado).

---

### 5.2 `citability_scorer.py` — Score de citabilidade

**Responsabilidade:** Avaliar cada bloco de conteúdo em 5 dimensões e atribuir nota de 0 a 100.

**As 5 dimensões e seus pesos:**

| Dimensão | Peso | O que avalia |
|---|---|---|
| Answer Block Quality | 30% | Padrões de definição, resposta direta, fontes citadas |
| Self-Containment | 25% | Contexto próprio (sem depender de texto anterior) |
| Structural Readability | 20% | Comprimento de sentenças, marcadores sequenciais |
| Statistical Density | 15% | Números, percentuais, anos recentes, valores |
| Uniqueness Signals | 10% | Dados originais, casos reais, ferramentas específicas |

**Multiplicador de comprimento (fator crítico):**

```
134–167 palavras → 1.0x   (faixa ideal para citação por LLM)
100–200 palavras → 0.92x
80–250 palavras  → 0.82x
50–400 palavras  → 0.65x
< 50 ou > 400    → 0.50x  (penalidade severa)
```

A faixa 134–167 palavras foi calibrada com base em estudos de como LLMs selecionam passagens para citação em respostas longas.

**Grades:**
- A (≥ 80): Altamente citável
- B (65–79): Boa citabilidade
- C (50–64): Citabilidade moderada
- D (35–49): Citabilidade baixa
- F (< 35): Não citável

**Bilinguismo:** Os regex de padrões semânticos cobrem inglês e português. Padrões de definição, por exemplo, reconhecem tanto `"X is a"` (EN) quanto `"X é um"` e `"X refere-se a"` (PT-BR). Para adicionar outros idiomas, ver [seção 14.9](#149-evolução-do-modelo-de-scoring).

---

### 5.3 `crawler_checker.py` — Permissões de AI crawlers

**Responsabilidade:** Parsear o `robots.txt` e determinar o status de 15 crawlers de IA.

**Crawlers rastreados (15 total):**

| Crawler | Plataforma | Criticidade |
|---|---|---|
| GPTBot | ChatGPT (indexação) | Crítico |
| OAI-SearchBot | ChatGPT Search | Crítico |
| ChatGPT-User | ChatGPT Browse | Crítico |
| ClaudeBot | Claude / Perplexity | Crítico |
| anthropic-ai | Claude (treinamento) | Crítico |
| PerplexityBot | Perplexity AI | Crítico |
| Google-Extended | Gemini / AI Overviews | Crítico |
| Googlebot | Google Search | Adicional |
| Bingbot | Bing / Copilot | Adicional |
| Meta-ExternalAgent | Meta AI | Adicional |
| Bytespider | TikTok / ByteDance | Adicional |
| cohere-ai | Cohere | Adicional |
| Diffbot | Diffbot | Adicional |
| CCBot | Common Crawl | Adicional |
| YouBot | You.com | Adicional |

**Algoritmo de parse do robots.txt:**
1. Percorre linha por linha identificando blocos `User-agent:`
2. Para cada bloco, coleta as diretivas `Allow:` e `Disallow:`
3. Ao checar um crawler, aplica: match exato de user-agent → fallback wildcard (`*`)
4. Para cada URL/path: regra mais específica (mais longa) vence
5. `Allow` vence sobre `Disallow` em empate de comprimento

**Scoring:**
- Cada crawler crítico bloqueado subtrai pontos pesados (> 10 pts cada)
- Cada crawler adicional bloqueado subtrai pontos menores
- `llms.txt` presente adiciona bônus de modernidade

---

### 5.4 `brand_scanner.py` — Presença de marca

**Responsabilidade:** Verificar se a marca está presente nas plataformas com maior correlação com citações de IA.

**Base de correlação (Ahrefs, Dez 2025):**

| Plataforma | Correlação com citações de IA |
|---|---|
| YouTube | 0.737 (mais forte de todas) |
| Reddit | 0.580 |
| Wikipedia | 0.520 |
| Wikidata | 0.480 |
| LinkedIn | 0.410 |
| Backlinks (DR) | 0.266 (referência comparativa) |

**Verificação automática (via API):**
- **Wikipedia:** `GET https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={brand}` com fallback para `pt.wikipedia.org`
- **Wikidata:** `GET https://www.wikidata.org/w/api.php?action=wbsearchentities&search={brand}&language=en`

**Verificação semi-automática (checklist):**
Para YouTube, Reddit, LinkedIn e outras 8 plataformas, o módulo gera URLs de busca para verificação manual e retorna checklist estruturado no findings.

**Por que não automatizar tudo:** As plataformas checklist (YouTube, Reddit, etc.) exigem autenticação ou têm limitações de rate que tornam a automação inviável sem API keys pagas. O modelo atual é o melhor custo-benefício.

---

### 5.5 `schema_analyzer.py` — Structured data

**Responsabilidade:** Detectar schema markup JSON-LD e avaliar cobertura.

**16 tipos prioritários rastreados:**

```
Organization, WebSite, WebPage, Product, SoftwareApplication,
Course, Article, FAQPage, HowTo, BreadcrumbList, LocalBusiness,
Person, Review, AggregateRating, VideoObject, ImageObject
```

**Lógica de extração:**
1. Seleciona todos os `<script type="application/ld+json">`
2. Parseia JSON com `json.loads()`
3. Lida com `@graph` aninhado (array de entidades)
4. Lida com `@type` como string ou array
5. Extrai URLs `sameAs` para entity linking

**Scoring:**
- `Organization` + `WebSite` = schemas base (peso alto)
- `FAQPage`, `HowTo`, `Article` = schemas de conteúdo citável (peso alto)
- Cobertura % = tipos encontrados / tipos prioritários possíveis

---

### 5.6 `orchestrator.py` — Coordenador central

**Responsabilidade:** Orquestrar todas as análises, calcular o GEO Score, e estruturar o output final.

**Fluxo interno de `run_full_audit()`:**

```python
# 1. Coleta de dados da página
page_data = fetch_page(url)
robots_txt = fetch_robots_txt(url)
llms_txt   = fetch_llms_txt(url)

# 2. Análises (sequenciais; v1.0.1 — ver seção 14 para paralelização)
citability = analyze_page_citability(page_data["content_blocks"])
crawlers   = check_ai_crawlers(robots_txt, url, llms_txt)
brand      = scan_brand_presence(brand_name, domain)
schema     = analyze_schema(page_data["soup"], url)

# 3. GEO Score: média ponderada das categorias
geo_score = compute_weighted_score(citability, crawlers, brand, schema, ...)

# 4. Agregação e priorização de findings
findings   = aggregate_findings(citability, crawlers, brand, schema)
findings.sort(key=severity_order)        # crítico → alto → médio → baixo
quick_wins = extract_quick_wins(findings) # ordenados por ROI

# 5. Estrutura o resultado final
return build_result_dict(...)
```

**Pesos do GEO Score:**

| Categoria | Peso |
|---|---|
| AI Citability | 25% |
| Brand Authority | 20% |
| Content E-E-A-T | 20% |
| Technical SEO | 15% |
| Schema Markup | 10% |
| Platform Optimization | 10% |

**Cálculo de platform readiness:**
Cada plataforma (ChatGPT, Perplexity, Gemini, etc.) tem uma fórmula específica que considera quais crawlers estão bloqueados para aquela plataforma e ajusta o score base:

```python
chatgpt_score = base + (+10 se GPTBot allowed, -20 se bloqueado)
perplexity_score = base + (+10 se PerplexityBot/ClaudeBot allowed)
gemini_score = base + (+10 se Google-Extended allowed)
```

---

### 5.7 `url_discovery.py` — Audit de domínio

**Responsabilidade:** Descobrir URLs de um domínio para auditoria em escala.

**Estratégia em cascata:**
1. Tenta `/sitemap.xml` → parseia URLs com BeautifulSoup XML
2. Se for sitemap index, segue para sub-sitemaps
3. Filtra por `scope_path` (padrão: `/pt-br` — configurável)
4. Deduplica e normaliza URLs
5. Se sitemap insuficiente, faz crawl BFS de links internos

**Limitações configuráveis:**
- `max_urls = 60` por auditoria de domínio
- `discovery_timeout = 20s`
- `sitemap_max_urls = 5000`

---

## 6. Metodologia de scoring

### GEO Score

```
GEO Score = Σ(score_categoria × peso_categoria / 100)

Exemplo:
  citability_score = 70, peso = 25 → contribui 17.5
  brand_score      = 60, peso = 20 → contribui 12.0
  eeat_score       = 65, peso = 20 → contribui 13.0
  technical_score  = 80, peso = 15 → contribui 12.0
  schema_score     = 50, peso = 10 → contribui  5.0
  platform_score   = 75, peso = 10 → contribui  7.5
  ─────────────────────────────────────────────────
  GEO Score = 67
```

### Interpretação do GEO Score

| Faixa | Significado |
|---|---|
| 85–100 | Excelente — alto potencial de citação por IA |
| 70–84 | Bom — melhorias pontuais recomendadas |
| 50–69 | Regular — gaps significativos identificados |
| 35–49 | Fraco — problemas estruturais importantes |
| 0–34 | Crítico — site praticamente invisível para IA |

### Quick Wins (ROI)

```python
roi = impact_pts / effort_days

# Exemplo:
# "Adicionar llms.txt" → impact_pts=3, effort_days=0.5 → roi=6.0
# "Reescrever 10 blocos D/F" → impact_pts=8, effort_days=3 → roi=2.7

quick_wins = [f for f in findings if roi > threshold]
quick_wins.sort(key=lambda x: x["roi"], reverse=True)
```

---

## 7. Servidor web e API REST

O `server.py` expõe o dashboard e a API via FastAPI/Uvicorn.

### Endpoints

| Método | Path | Descrição |
|---|---|---|
| `GET` | `/` | Dashboard HTML |
| `GET` | `/api/health` | Health check (para Cloud Run) |
| `GET` | `/api/latest` | Última auditoria do BigQuery |
| `GET` | `/api/history` | Histórico de auditorias (até 100) |
| `POST` | `/api/audit` | Auditoria de página única |
| `POST` | `/api/audit/domain` | Auditoria de domínio completo |
| `POST` | `/api/crawlers` | Apenas análise de crawlers |
| `POST` | `/api/brand` | Apenas análise de brand |
| `POST` | `/api/chat` | Chat com Letícia |

### Payload de auditoria

```json
POST /api/audit
{
  "url": "https://hotmart.com/pt-br",
  "brand": "Hotmart"
}
```

### Processamento assíncrono

A auditoria roda no thread principal e o save no BigQuery é disparado como `BackgroundTask` do FastAPI — não bloqueia a resposta ao cliente.

```python
@app.post("/api/audit")
async def audit(request: AuditRequest, background_tasks: BackgroundTasks):
    result = run_full_audit(request.url, request.brand)
    background_tasks.add_task(bigquery_store.save_audit, result)
    return result
```

---

## 8. Frontend — Dashboard React

O dashboard é um arquivo `static/index.html` com ~3.000 linhas de HTML + JavaScript inline.

### Arquitetura do componente

```
<GEODashboard data={auditData}>
  ├── <Header>          — Logo, GEO Score gauge, badge de grade
  ├── <TabNav>          — Navegação entre as 9 abas
  │
  ├── <OverviewTab>     — Radar chart + métricas principais
  ├── <PlatformsTab>    — Cards por plataforma + gráfico de evolução
  ├── <CitabilityTab>   — Grade distribution + top/bottom blocks
  ├── <CrawlersTab>     — Tabela de crawlers + cobertura
  ├── <BrandTab>        — Status por plataforma + correlações
  ├── <SchemaTab>       — Tipos detectados + cobertura
  ├── <FindingsTab>     — Lista de findings por severidade
  ├── <RoadmapTab>      — Quick wins + scatter de ROI
  └── <ChatTab>         — Interface de chat com Letícia
```

### Como os dados chegam ao dashboard

**Modo servidor (produção):**
```javascript
// O dashboard faz GET /api/latest ao carregar
// e POST /api/audit quando o usuário submete uma URL
fetch('/api/latest')
  .then(r => r.json())
  .then(data => setAuditData(data))
```

**Modo standalone (desenvolvimento/Claude artifact):**
```javascript
// Objeto RAW no topo do arquivo é substituído pelo JSON de output
const RAW = { /* resultado do run_full_audit() */ }
```

### Design system

- **Tema:** Dark, fundo `#0f172a` (slate-900)
- **Cores de score:** Verde (≥70), Amarelo (50–69), Vermelho (<50)
- **Fonte:** System font stack (sem dependência de Google Fonts)
- **Gráficos:** Recharts — RadarChart, AreaChart, BarChart, PieChart, ScatterChart

### Animações

As abas são montadas com stagger progressivo (delay incremental por card) usando CSS `animation-delay`. Os gauges circulares usam `stroke-dashoffset` animado via CSS transition.

---

## 9. Agente Letícia (Google ADK)

Letícia é a analista de GEO conversacional embutida no dashboard. Ela tem acesso a 10 ferramentas especializadas que chamam a engine de análise e permitem consultas sobre qualquer dado da auditoria.

### Ferramentas disponíveis

| Ferramenta | O que faz |
|---|---|
| `get_geo_score` | Retorna o GEO Score e scores por categoria |
| `get_citability_analysis` | Top/bottom blocos, grade distribution |
| `get_crawler_status` | Status de cada crawler de IA |
| `get_brand_presence` | Resultado por plataforma |
| `get_schema_analysis` | Tipos encontrados e recomendações |
| `get_quick_wins` | Quick wins priorizados por ROI |
| `get_findings` | Findings filtrados por severidade |
| `run_page_audit` | Executa nova auditoria on-demand |
| `compare_with_competitor` | Compara dois domínios |
| `get_platform_readiness` | Score por plataforma de IA |

### Configuração do agente

```python
root_agent = Agent(
    name="leticia",
    model="gemini-2.5-flash-preview",
    instruction=SYSTEM_PROMPT,   # prompts.py
    tools=TOOLS,                 # tools.py
    generation_config={
        "temperature": 0.2,      # baixa criatividade — respostas analíticas
        "max_output_tokens": 2048
    }
)
```

### Sistema de sessão

```python
runner = Runner(
    agent=root_agent,
    app_name="leticia_geo_seo",
    session_service=InMemorySessionService()
)
# Cada usuário tem session_id único — contexto mantido durante a sessão
```

### Tratamento de rate limits

```python
async for event in runner.run_async(...):
    if is_quota_error(event):
        await asyncio.sleep(10)  # backoff
        # retry automático
```

---

## 10. Persistência — BigQuery

### Schema da tabela `geo_seo_auditor.audits`

| Coluna | Tipo | Descrição |
|---|---|---|
| `audit_id` | STRING | UUID da auditoria |
| `created_at` | TIMESTAMP | Data/hora UTC |
| `domain` | STRING | Domínio auditado (ex: `hotmart.com`) |
| `url` | STRING | URL completa |
| `geo_score` | INTEGER | Score geral (0-100) |
| `citability_score` | INTEGER | Score de citabilidade |
| `crawler_score` | INTEGER | Score de crawlers |
| `brand_score` | INTEGER | Score de brand |
| `schema_score` | INTEGER | Score de schema |
| `technical_score` | INTEGER | Score técnico |
| `platform_score` | INTEGER | Score de plataforma |
| `raw_result` | JSON | Output completo da auditoria |

**Particionamento:** por dia em `created_at` (reduz custo de queries históricas)  
**Clustering:** por `domain` (queries por domínio sem full scan)

### Operações disponíveis

```python
from bigquery_store import BigQueryStore

store = BigQueryStore()

# Salvar
store.save_audit(result, audit_type="single_page")

# Recuperar última auditoria (geral ou por domínio)
store.get_latest_audit(domain="hotmart.com")

# Histórico
store.get_audit_history(domain="hotmart.com", limit=30)
```

---

## 11. Fluxo de dados end-to-end

```
                    USUÁRIO
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
    CLI: main.py               Browser/Dashboard
    audit <URL>                POST /api/audit
          │                         │
          └────────────┬────────────┘
                       ▼
              orchestrator.py
              run_full_audit(url, brand)
                       │
          ┌────────────┼────────────────────┐
          ▼            ▼                    ▼
    fetch_page()   fetch_robots.txt()  fetch_llms.txt()
    ┌──────────┐        │                   │
    │HTML parse│        └─────────┬─────────┘
    │ content  │                  ▼
    │ blocks   │         crawler_checker.py
    │ schema   │         check_ai_crawlers()
    │ soup     │
    └────┬─────┘
         │
    ┌────┴────────────────────┐
    ▼                         ▼
citability_scorer.py    schema_analyzer.py
analyze_page_cit.()     analyze_schema()
         │
         └──── brand_scanner.py
               scan_brand_presence()
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
    compute_scores()          aggregate_findings()
    weighted GEO Score        sort by severity
          │                   extract quick_wins
          └────────────┬────────────┘
                       ▼
               build_result_dict()
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       JSON         Markdown    Executive
       output       report      summary
          │
          ├──→ Response HTTP (Dashboard)
          └──→ BigQuery (background)
```

**Tempos típicos:**
- Auditoria de página única: **5–10 segundos**
- Auditoria de domínio (60 páginas): **60–120 segundos**
- Save no BigQuery: **< 100ms** (assíncrono, não bloqueia)

---

## 12. Configuração e variáveis de ambiente

### `config.py` — constantes configuráveis

Todas as constantes que governam o comportamento do sistema estão centralizadas aqui. Altere neste arquivo para ajustar pesos, limites e timeouts sem tocar nos módulos de análise.

```python
# Pesos do GEO Score (devem somar 100)
CATEGORY_WEIGHTS = {
    "ai_citability":         25,
    "brand_authority":       20,
    "content_eeat":          20,
    "technical":             15,
    "schema":                10,
    "platform_optimization": 10,
}

# Faixa ideal de comprimento para citabilidade (em palavras)
OPTIMAL_WORD_COUNT_MIN = 134
OPTIMAL_WORD_COUNT_MAX = 167
MIN_BLOCK_WORDS = 50        # Blocos abaixo disso são descartados da análise

# Auditoria de domínio
DOMAIN_AUDIT_MAX_PAGES = 60
DOMAIN_AUDIT_DEFAULT_SCOPE_PATH = "/pt-br"  # Filtro de path — ajuste por domínio

# HTTP
DEFAULT_TIMEOUT = 30        # segundos
```

### Variáveis de ambiente

| Variável | Obrigatório | Descrição |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Para BigQuery | ID do projeto GCP onde a tabela de auditorias será criada |
| `GOOGLE_API_KEY` | Para Letícia | API key do Google AI Studio (obtenha em aistudio.google.com) |
| `PORT` | Não | Porta do servidor web (padrão: `8080`) |

### Application Default Credentials

Para BigQuery, o sistema usa ADC (Application Default Credentials). Em desenvolvimento local:

```bash
gcloud auth application-default login
```

Em Cloud Run, as credenciais da service account são usadas automaticamente.

---

## 13. Como executar localmente

### Pré-requisitos

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### CLI

```bash
# Auditoria completa
python main.py audit https://hotmart.com --brand "Hotmart"

# Apenas citabilidade
python main.py citability https://hotmart.com

# Apenas crawlers
python main.py crawlers https://hotmart.com

# Brand scan
python main.py brand "Hotmart" --domain hotmart.com

# Schema
python main.py schema https://hotmart.com

# Formatos de output
python main.py audit https://hotmart.com --format json
python main.py audit https://hotmart.com --format markdown
python main.py audit https://hotmart.com --format executive
```

### Servidor web

```bash
python server.py
# Dashboard disponível em http://localhost:8080
```

---

## 14. Guia de evoluções

Esta seção documenta como adicionar novas funcionalidades sem quebrar o que já existe.

---

### 14.1 Suporte a páginas SPA / JavaScript pesado

**Problema:** Páginas React/Vue sem SSR retornam HTML vazio ao fetch simples. O `page_fetcher.py` detecta isso mas não resolve.

**Como implementar:**

1. Adicionar `playwright` ao `requirements.txt`
2. Em `page_fetcher.py`, criar função alternativa:

```python
async def fetch_page_with_browser(url: str) -> dict:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        html = await page.content()
        await browser.close()
    return parse_html(html, url)
```

3. No `orchestrator.py`, usar fallback:

```python
page_data = fetch_page(url)
if page_data.get("is_spa") and not page_data["content_blocks"]:
    page_data = await fetch_page_with_browser(url)
```

**Impacto:** Nenhum módulo de análise precisa mudar — todos consomem o mesmo formato de `page_data`.

---

### 14.2 Novo módulo de análise

**Cenário:** Adicionar análise de "Core Web Vitals" ou "Page Speed" como nova dimensão.

**Passo a passo:**

1. Criar `auditor/performance_analyzer.py`:

```python
def analyze_performance(url: str) -> dict:
    """
    Retorna dict padronizado com:
    - score (0-100)
    - findings (list)
    - recommendations (list)
    - raw_data (dict)
    """
    # Implementação aqui (ex: PageSpeed Insights API)
    return {
        "score": score,
        "lcp_ms": lcp,
        "fid_ms": fid,
        "cls": cls,
        "findings": [...],
        "recommendations": [...]
    }
```

2. Em `config.py`, ajustar pesos (devem somar 100%):

```python
CATEGORY_WEIGHTS = {
    "ai_citability":         22,   # reduzido
    "brand_authority":       18,   # reduzido
    "content_eeat":          18,   # reduzido
    "technical":             15,
    "schema":                10,
    "platform_optimization": 10,
    "performance":            7,   # NOVO
}
```

3. Em `orchestrator.py`, chamar o novo módulo:

```python
from auditor.performance_analyzer import analyze_performance

performance = analyze_performance(url)
# Já está pronto para entrar no GEO Score pelo mecanismo de pesos
```

4. Em `static/index.html`, adicionar aba ou card ao dashboard.

---

### 14.3 Nova plataforma de IA no crawler checker

**Cenário:** Adicionar Grok (xAI) ou um novo crawler que surgiu.

Em `auditor/crawler_checker.py`, adicionar ao dicionário de crawlers:

```python
AI_CRAWLERS = [
    # ... crawlers existentes ...
    {
        "user_agent": "Grok",
        "platform": "Grok (xAI)",
        "operator": "xAI",
        "critical": False,      # True se for uma plataforma principal
        "description": "xAI Grok crawler"
    },
]
```

Não há mais nada a mudar — o mecanismo de análise, scoring e findings é genérico para todos os crawlers no array.

---

### 14.4 Nova plataforma de brand

**Cenário:** Adicionar verificação automática no GitHub ou Crunchbase via API.

Em `auditor/brand_scanner.py`:

```python
def check_github_presence(brand_name: str) -> dict:
    """Busca organização no GitHub"""
    slug = brand_name.lower().replace(" ", "-")
    r = requests.get(
        f"https://api.github.com/orgs/{slug}",
        headers={"Accept": "application/vnd.github+json"},
        timeout=10
    )
    found = r.status_code == 200
    return {
        "platform": "GitHub",
        "found": found,
        "url": f"https://github.com/{slug}" if found else None,
        "correlation": 0.35  # Correlation score estimado
    }
```

Adicionar ao `scan_brand_presence()` e ao array de plataformas verificadas.

---

### 14.5 Adicionar nova aba ao dashboard

**Cenário:** Criar aba "Concorrentes" com comparação side-by-side.

1. No `static/index.html`, adicionar tab na navegação:

```javascript
const TABS = [
  // ... tabs existentes ...
  { id: "competitors", label: "Concorrentes", icon: "⚔️" }
]
```

2. Criar o componente de aba:

```javascript
function CompetitorsTab({ data }) {
  const [competitor, setCompetitor] = useState(null);
  
  const runCompetitorAudit = async (url) => {
    const result = await fetch('/api/audit', {
      method: 'POST',
      body: JSON.stringify({ url })
    }).then(r => r.json());
    setCompetitor(result);
  };
  
  return (
    <div>
      <input onSubmit={runCompetitorAudit} placeholder="URL do concorrente" />
      {competitor && <ComparisonChart current={data} competitor={competitor} />}
    </div>
  );
}
```

3. Renderizar no switch de abas existente.

---

### 14.6 Exportação para PDF

**Cenário:** Gerar relatório PDF para envio a clientes.

1. Adicionar `reportlab` ou `weasyprint` ao `requirements.txt`

2. Criar `report_pdf.py`:

```python
from weasyprint import HTML

def to_pdf(audit_result: dict, output_path: str):
    html_content = to_html_report(audit_result)
    HTML(string=html_content).write_pdf(output_path)
```

3. Adicionar endpoint no `server.py`:

```python
@app.post("/api/audit/pdf")
async def audit_pdf(request: AuditRequest):
    result = run_full_audit(request.url, request.brand)
    pdf_bytes = to_pdf(result)
    return Response(content=pdf_bytes, media_type="application/pdf")
```

---

### 14.7 Webhook e notificações

**Cenário:** Notificar via Slack ou email quando o GEO Score cair abaixo de um threshold.

Criar `notifier.py`:

```python
def notify_slack(webhook_url: str, audit_result: dict, threshold: int = 60):
    score = audit_result["geo_score"]
    if score < threshold:
        message = {
            "text": f"⚠️ GEO Score caiu para {score}/100 em {audit_result['domain']}"
        }
        requests.post(webhook_url, json=message)
```

No `server.py`, usar como `BackgroundTask` junto com o save no BigQuery.

---

### 14.8 Auditoria agendada

**Cenário:** Rodar auditoria diária/semanal automaticamente.

Opção 1 — Cloud Scheduler + Cloud Run Job:
```bash
gcloud scheduler jobs create http geo-seo-daily \
  --schedule="0 8 * * 1" \
  --uri="https://YOUR-CLOUD-RUN-URL/api/audit" \
  --http-method=POST \
  --message-body='{"url": "https://hotmart.com", "brand": "Hotmart"}'
```

Opção 2 — APScheduler dentro do servidor:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=8, minute=0)
async def daily_audit():
    result = run_full_audit("https://hotmart.com", "Hotmart")
    await bigquery_store.save_audit(result)

scheduler.start()
```

---

### 14.9 Evolução do modelo de scoring

**Quando alterar os pesos:**
- Se uma nova dimensão for adicionada, redistribuir os 100% em `config.py`
- Os pesos atuais refletem consenso da literatura GEO de 2024–2025 — revisar anualmente

**Como recalibrar a faixa ideal de palavras:**
- A faixa 134–167 palavras está em `config.py` como `OPTIMAL_WORD_COUNT_MIN/MAX`
- Pode ser ajustada com base em estudos mais recentes de citação por LLMs

**Como adicionar padrões linguísticos ao citability scorer:**
- Os regex estão em `citability_scorer.py` como listas comentadas por dimensão
- Para PT-BR: adicionar variantes em português às listas existentes
- Para outros idiomas: criar arquivo `patterns_es.py`, `patterns_fr.py`, etc., e importar por locale

---

### 14.10 Escalar para multi-tenant (múltiplos clientes)

A arquitetura atual suporta um único "tenant" (configuração via env vars). Para multi-tenant:

1. **BigQuery:** Adicionar coluna `tenant_id` na tabela e filtrar por ela
2. **API:** Adicionar autenticação JWT nos endpoints
3. **Dashboard:** Parametrizar `tenant_id` na URL (`/dashboard?tenant=acme`)
4. **Config:** Mover `CATEGORY_WEIGHTS` para banco (permitir personalização por cliente)

---

---

*Mantido em `docs/TECHNICAL_GUIDE.md`. Atualizar junto a cada release.*
