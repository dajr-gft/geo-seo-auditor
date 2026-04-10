# GEO-SEO Auditor

> Auditoria de visibilidade para buscadores generativos — ChatGPT, Perplexity, Gemini, Google AI Overviews e Bing Copilot.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.1-orange)]()

O **GEO-SEO Auditor** analisa qualquer URL e calcula um **GEO Score** (0–100) que indica o quanto aquele conteúdo está preparado para ser citado por sistemas de IA generativa. O resultado inclui um dashboard interativo, findings priorizados por severidade, quick wins com cálculo de ROI e um agente conversacional para análises guiadas.

---

## Por que GEO importa

O tráfego referido por IA cresceu **+527% ano a ano**. Visitantes vindos de IA convertem **4.4× mais** que tráfego orgânico tradicional. O Gartner projeta redução de **50% no tráfego de busca tradicional até 2028**, e apenas **23% dos profissionais de marketing** estão investindo em GEO hoje.

Um site bem posicionado no Google tradicional pode ter GEO Score zero se o conteúdo não estiver estruturado para ser citado por LLMs. Esta ferramenta identifica exatamente o que bloqueia ou favorece essa citabilidade.

---

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| **GEO Score composto** | Nota 0–100 agregando 6 categorias ponderadas |
| **Score de citabilidade** | Análise bloco a bloco do conteúdo da página |
| **Verificação de AI crawlers** | Status de 15 crawlers (GPTBot, ClaudeBot, PerplexityBot...) |
| **Brand scan** | Presença da marca em Wikipedia, Wikidata, YouTube, Reddit, LinkedIn |
| **Schema markup** | Detecção e cobertura de 16 tipos JSON-LD prioritários |
| **Domain audit** | Auditoria em escala de até 60 páginas via sitemap |
| **Dashboard interativo** | 9 abas com visualizações, findings e roadmap |
| **Histórico** | Persistência no BigQuery com evolução temporal |
| **API REST** | FastAPI com endpoints para integração |
| **Agente Letícia** | Analista conversacional via Google ADK + Gemini |
| **Relatórios** | Markdown e sumário executivo para stakeholders |

---

## Início rápido

### Pré-requisitos

- Python 3.9+
- pip

> **Nota:** não há dependência de Node.js ou build step. O dashboard é um HTML autocontido.

### Instalação

```bash
git clone https://github.com/seu-usuario/geo-seo-auditor.git
cd geo-seo-auditor

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# ou: .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### Primeira auditoria via CLI

```bash
python main.py audit https://exemplo.com --brand "Exemplo"
```

### Dashboard web

```bash
python server.py
# Acesse http://localhost:8080
```

Insira uma URL no campo de busca e clique em **Auditar**. Os resultados aparecem nas 9 abas em ~10 segundos.

---

## Uso

### CLI

```bash
# Auditoria completa (JSON por padrão)
python main.py audit https://exemplo.com --brand "Exemplo"

# Salvar resultado em arquivo
python main.py audit https://exemplo.com --output resultado.json

# Formatos alternativos
python main.py audit https://exemplo.com --format markdown
python main.py audit https://exemplo.com --format executive

# Análises individuais
python main.py citability https://exemplo.com
python main.py crawlers https://exemplo.com
python main.py brand "Exemplo" --domain exemplo.com
python main.py schema https://exemplo.com
```

### API REST

```bash
# Auditoria de página única
curl -X POST http://localhost:8080/api/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://exemplo.com", "brand": "Exemplo"}'

# Auditoria de domínio completo
curl -X POST http://localhost:8080/api/audit/domain \
  -H "Content-Type: application/json" \
  -d '{"url": "https://exemplo.com", "brand": "Exemplo", "max_pages": 30}'

# Consultar última auditoria salva
curl http://localhost:8080/api/latest

# Histórico de auditorias
curl http://localhost:8080/api/history
```

### Endpoints disponíveis

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/` | Dashboard HTML |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/latest` | Última auditoria salva |
| `GET` | `/api/history` | Histórico (até 100 registros) |
| `POST` | `/api/audit` | Auditoria de página única |
| `POST` | `/api/audit/domain` | Auditoria de domínio completo |
| `POST` | `/api/crawlers` | Apenas análise de crawlers |
| `POST` | `/api/brand` | Apenas brand scan |
| `POST` | `/api/chat` | Chat com agente Letícia |

---

## Dashboard

O dashboard possui 9 abas:

| Aba | Conteúdo |
|---|---|
| **Overview** | GEO Score gauge + radar chart das 6 categorias + KPIs |
| **Plataformas** | Readiness por ChatGPT, Perplexity, Gemini, Bing, Google AIO |
| **Citabilidade** | Scores por bloco, distribuição de grades A–F, top/bottom 5 |
| **Crawlers** | Status de 15 AI crawlers, cobertura %, presença de llms.txt |
| **Brand** | Presença em Wikipedia, Wikidata, YouTube, Reddit, LinkedIn |
| **Schema** | Tipos JSON-LD detectados, cobertura %, sameAs links |
| **Findings** | Problemas por severidade (crítico → informativo) com fix e esforço |
| **Roadmap** | Quick wins ordenados por ROI + gráfico esforço × impacto |
| **Chat** | Interface de conversa com Letícia, a analista de GEO |

---

## Metodologia de scoring

### GEO Score composto

```
GEO Score = Σ(score_categoria × peso / 100)
```

| Categoria | Peso | O que mede |
|---|---|---|
| AI Citability | 25% | Blocos de conteúdo prontos para citação por LLMs |
| Brand Authority | 20% | Presença em plataformas com alta correlação com citações de IA |
| Content E-E-A-T | 20% | Experiência, Expertise, Autoridade e Confiança |
| Technical SEO | 15% | Fundações técnicas (robots.txt, SSR, mobile) |
| Schema Markup | 10% | Dados estruturados JSON-LD para entidades |
| Platform Optimization | 10% | Otimização específica por plataforma de IA |

### Escala de referência

| GEO Score | Diagnóstico |
|---|---|
| 85–100 | Excelente — alto potencial de citação |
| 70–84 | Bom — ajustes pontuais recomendados |
| 50–69 | Regular — gaps significativos identificados |
| 35–49 | Fraco — problemas estruturais relevantes |
| 0–34 | Crítico — site invisível para sistemas de IA |

### Score de citabilidade — como funciona

Cada bloco de conteúdo (heading + parágrafos) recebe nota 0–100 em 5 dimensões:

| Dimensão | Peso | O que avalia |
|---|---|---|
| Answer Block Quality | 30% | Padrões de definição, resposta direta, claims com fonte |
| Self-Containment | 25% | Contexto próprio sem depender de texto adjacente |
| Structural Readability | 20% | Comprimento de sentenças, marcadores sequenciais |
| Statistical Density | 15% | Percentuais, valores, números, anos recentes |
| Uniqueness Signals | 10% | Dados originais, case studies, exemplos específicos |

A nota final é multiplicada por um fator de comprimento — a faixa ideal é **134–167 palavras** por bloco, calibrada com base em estudos de como LLMs selecionam passagens para citação.

### Brand Authority — correlações empíricas

Baseado em estudo Ahrefs (dezembro de 2025) sobre correlação de presença de plataformas com citações de IA:

| Plataforma | Correlação |
|---|---|
| YouTube | **0.737** |
| Reddit | 0.580 |
| Wikipedia | 0.520 |
| Wikidata | 0.480 |
| LinkedIn | 0.410 |
| Backlinks tradicionais (Domain Rating) | 0.266 |

---

## Configuração opcional

### BigQuery (persistência de histórico)

```bash
# Autenticar na Google Cloud
gcloud auth application-default login

# Definir projeto
export GOOGLE_CLOUD_PROJECT="seu-projeto-gcp"
```

Se não configurado, o dashboard funciona normalmente — apenas sem histórico persistido.

### Agente Letícia (chat com IA)

```bash
export GOOGLE_API_KEY="sua-chave-do-google-ai-studio"
```

Obtenha sua chave gratuitamente em [aistudio.google.com](https://aistudio.google.com/).

Se não configurado, todas as abas do dashboard funcionam normalmente — apenas o Chat fica desabilitado.

---

## Estrutura do projeto

```
geo-seo-auditor/
├── main.py                     # CLI
├── server.py                   # Servidor FastAPI
├── config.py                   # Pesos, limites e constantes
├── requirements.txt
├── bigquery_store.py           # Persistência
│
├── auditor/                    # Engine de análise
│   ├── orchestrator.py         # Coordenador central → GEO Score
│   ├── page_fetcher.py         # HTTP + parsing HTML
│   ├── citability_scorer.py    # Score por bloco de conteúdo
│   ├── crawler_checker.py      # robots.txt + 15 AI crawlers
│   ├── brand_scanner.py        # Presença cross-platform
│   ├── schema_analyzer.py      # JSON-LD / schema.org
│   └── url_discovery.py        # Descoberta via sitemap
│
├── agentes/leticia/            # Agente conversacional
│   ├── agent.py
│   ├── prompts.py
│   └── tools.py
│
├── static/
│   ├── index.html              # Dashboard (self-contained)
│   └── vendor/                 # React, Recharts, Babel
│
└── docs/
    ├── ARCHITECTURE.md         # Arquitetura e fluxo de dados
    └── TECHNICAL_GUIDE.md      # Guia técnico completo
```

---

## Documentação técnica

- **[docs/TECHNICAL_GUIDE.md](docs/TECHNICAL_GUIDE.md)** — arquitetura detalhada, decisões de design e guia passo a passo para evoluir cada módulo
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — diagramas de arquitetura e fluxo de dados

---

## Contribuindo

Contribuições são bem-vindas. Para mudanças significativas, abra uma issue primeiro para discutir o que você gostaria de mudar.

```bash
# Fork e clone
git clone https://github.com/seu-usuario/geo-seo-auditor.git

# Crie uma branch descritiva
git checkout -b feat/nova-analise
# ou: fix/crawler-parser

# Commit seguindo Conventional Commits
git commit -m "feat: adicionar análise de Core Web Vitals"

# Abra um Pull Request
```

Antes de abrir o PR, consulte o [guia de evoluções](docs/TECHNICAL_GUIDE.md#14-guia-de-evoluções) no guia técnico.

### Reportar bugs

Abra uma issue descrevendo:
1. URL que foi auditada (se aplicável)
2. Comportamento esperado vs observado
3. Saída de erro completa

---

## Licença

Distribuído sob a licença MIT. Veja [`LICENSE`](LICENSE) para mais informações.

---

Desenvolvido por **Djalma Saraiva**
