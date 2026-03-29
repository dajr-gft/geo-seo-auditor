# Arquitetura — GEO-SEO Auditor

## Visão geral

O GEO-SEO Auditor é composto por duas camadas independentes:

1. **Backend Python** — Engine de análise que coleta e pontua dados reais
2. **Frontend React** — Dashboard interativo que consome o JSON de output

```
┌──────────────────────────────────────────────────────────┐
│                        CLI (main.py)                     │
│  audit | citability | crawlers | brand | schema          │
└───────────────────────┬──────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────┐
│                  Orchestrator                            │
│  Coordena análises → calcula GEO Score → gera report    │
└──┬──────┬──────┬──────┬──────┬───────────────────────────┘
   │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼
┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
│Fetch││Cita-││Craw-││Brand││Sche-│
│Page ││bili- ││ler  ││Scan-││ma   │
│     ││ty   ││Check││ner  ││Anal.│
└─────┘└─────┘└─────┘└─────┘└─────┘
   │      │      │      │      │
   └──────┴──────┴──────┴──────┘
                 │
        ┌────────▼────────┐
        │  Report Generator│
        │  JSON / MD / Exec│
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   Dashboard      │
        │   React + Recharts│
        └─────────────────┘
```

## Módulos

### page_fetcher.py
- Fetch HTTP com headers realistas e timeout configurável
- Parse HTML via BeautifulSoup
- Extração de content blocks agrupados por heading
- Detecção de tecnologia (SSR, SPA, CMS, framework)
- Fetch de robots.txt e llms.txt

### citability_scorer.py
- Score 0-100 por passagem de texto
- 5 dimensões: Answer Quality, Self-Containment, Readability, Stats, Uniqueness
- Bilíngue (EN + PT-BR) nos regex patterns
- Grade distribution (A-F) com limiares configuráveis
- Detecção de passagens na faixa ótima (134-167 palavras)

### crawler_checker.py
- Parse completo de robots.txt (multi-UA blocks, wildcard)
- Checagem de 15 AI crawlers com metadata (operator, criticality)
- Detecção de sitemaps e llms.txt
- Score ponderado com penalidade pesada por crawlers críticos

### brand_scanner.py
- API calls reais: Wikipedia Search API, Wikidata Entity Search
- Checklists estruturados: YouTube, Reddit, LinkedIn
- Links de busca para 8 plataformas adicionais
- Score baseado em correlações empíricas (Ahrefs 2025)

### schema_analyzer.py
- Extração de todos os JSON-LD blocks (incluindo @graph nested)
- Detecção de 16 tipos de schema prioritários
- Verificação de sameAs links para entity disambiguation
- Score baseado em presença de schemas essenciais

### orchestrator.py
- Coordenação sequencial de todas as análises
- Cálculo do GEO Score composto (média ponderada)
- Estimativa de readiness por plataforma de IA
- Agregação e priorização de findings
- Extração de quick wins com ROI calculado

### report_generator.py
- Output JSON (para dashboard)
- Output Markdown (para leitura humana)
- Sumário executivo (para C-level)
- Limpeza recursiva de objetos não serializáveis

## Dashboard React

O dashboard (`dashboard/GEODashboard.jsx`) é um componente React standalone que:

- Consome diretamente o JSON produzido pelo backend
- Usa Recharts para gráficos (RadarChart, ComposedChart, PieChart, AreaChart)
- Animações orquestradas com stagger progressivo
- Design system dark com tokens de cor centralizados
- 6 abas: Overview, Plataformas, Citabilidade, Crawlers, Findings, Roadmap

### Como integrar
1. O JSON do backend vai no objeto `RAW` no início do arquivo
2. O componente é self-contained — só precisa de React + Recharts
3. Pode ser usado como artifact no Claude.ai, ou em qualquer projeto React

## Fluxo de dados

```
URL input
    │
    ├─→ HTTP GET page HTML
    │      └─→ BeautifulSoup parse
    │             ├─→ Content blocks → Citability scoring
    │             └─→ JSON-LD scripts → Schema analysis
    │
    ├─→ HTTP GET robots.txt
    │      └─→ Parse rules → Crawler checking
    │
    ├─→ HTTP GET llms.txt
    │
    └─→ Brand name
           └─→ Wikipedia API + Wikidata API → Brand scoring
                      │
                      ▼
              Orchestrator aggregation
                      │
                      ├─→ Weighted GEO Score (0-100)
                      ├─→ Platform readiness estimates
                      ├─→ Prioritized findings
                      └─→ Quick wins with ROI
                              │
                              ▼
                      JSON output → Dashboard
```

## Extensões futuras

- **Playwright integration**: Screenshot + Lighthouse audit
- **Sitemap crawling**: Análise de múltiplas páginas
- **API mode**: FastAPI server para integração com outros sistemas
- **Historical tracking**: Comparação temporal de audits
- **Competitor benchmarking**: Audit comparativo de concorrentes
- **PDF report generation**: ReportLab para relatórios visuais
