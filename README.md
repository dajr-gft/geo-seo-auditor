# GEO-SEO Auditor

**Plataforma de auditoria GEO (Generative Engine Optimization) para análise de visibilidade em buscadores baseados em IA.**

Analisa qualquer site e gera um relatório completo de readiness para ChatGPT, Perplexity, Google AI Overviews, Gemini e Bing Copilot — com dashboard interativo para visualização executiva.

---

## Por que GEO importa

O tráfego referido por IA cresceu **+527% ano a ano**. Visitantes vindos de IA convertem **4.4x mais** que tráfego orgânico tradicional. O Gartner projeta queda de **50% no tráfego de busca tradicional até 2028**. Apenas **23% dos profissionais de marketing** estão investindo em GEO.

Este projeto permite auditar qualquer domínio e gerar um plano de ação priorizado para capturar essa oportunidade.

---

## Arquitetura

```
geo-seo-auditor/
├── main.py                     # CLI — ponto de entrada
├── config.py                   # Configurações e constantes
├── requirements.txt            # Dependências Python
│
├── auditor/                    # Engine de análise
│   ├── __init__.py
│   ├── orchestrator.py         # Orquestra todas as análises
│   ├── page_fetcher.py         # Fetch HTTP + parsing HTML
│   ├── citability_scorer.py    # Score de citabilidade por IA
│   ├── crawler_checker.py      # Análise de robots.txt (14 crawlers)
│   ├── brand_scanner.py        # Presença de marca cross-platform
│   ├── schema_analyzer.py      # Detecção de JSON-LD / schema.org
│   └── report_generator.py     # Geração do JSON de relatório
│
├── dashboard/                  # Frontend React
│   └── GEODashboard.jsx        # Dashboard interativo (standalone)
│
├── examples/                   # Exemplos de output
│   └── sample-audit.json       # Audit de exemplo
│
└── docs/
    └── ARCHITECTURE.md         # Documentação técnica detalhada
```

---

## Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/sua-org/geo-seo-auditor.git
cd geo-seo-auditor

# 2. Criar virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt
```

### Requisitos
- Python 3.9+
- Node.js 18+ (para o dashboard React — opcional)

---

## Uso

### Audit completo via CLI

```bash
# Audit de um domínio
python main.py audit https://hotmart.com

# Audit com output para arquivo
python main.py audit https://hotmart.com --output results/hotmart.json

# Apenas citabilidade
python main.py citability https://hotmart.com

# Apenas crawlers
python main.py crawlers https://hotmart.com

# Apenas brand scan
python main.py brand "Hotmart" --domain hotmart.com

# Apenas schema
python main.py schema https://hotmart.com
```

### Output

O CLI gera um arquivo JSON estruturado com todos os scores, findings e recomendações.
Este JSON é o input direto do dashboard React para visualização executiva.

### Dashboard

O dashboard React (`dashboard/GEODashboard.jsx`) consome o JSON de audit e renderiza:

- **Overview**: GEO Score com gauge animado, breakdown por categoria, KPIs
- **Plataformas**: Readiness por plataforma de IA com evolução temporal
- **Citabilidade**: Score por bloco de conteúdo, distribuição de grades, sub-dimensões
- **Crawlers**: Status de 14+ AI crawlers no robots.txt
- **Findings**: Problemas encontrados com severidade, fix e esforço estimado
- **Roadmap**: Projeção de impacto cumulativo com cálculo de ROI

Para usar o dashboard:
1. Cole o conteúdo de `GEODashboard.jsx` em qualquer projeto React + Recharts
2. Ou importe no Claude.ai como artifact `.jsx`
3. Substitua o objeto `RAW` pelo JSON gerado pelo `main.py`

---

## Metodologia de Scoring

| Categoria             | Peso | O que mede                                      |
|-----------------------|------|--------------------------------------------------|
| AI Citability         | 25%  | Blocos de conteúdo prontos para citação por LLMs  |
| Brand Authority       | 20%  | Presença em plataformas citadas por IA            |
| Content E-E-A-T       | 20%  | Experiência, Expertise, Autoridade, Confiança     |
| Technical SEO         | 15%  | Fundações técnicas (SSR, mobile, security)        |
| Schema Markup         | 10%  | Dados estruturados JSON-LD para entidades         |
| Platform Optimization | 10%  | Otimização específica por plataforma de IA        |

### Citabilidade — como funciona

Baseado em pesquisa que mostra que passagens citadas por IA têm perfil específico:

- **134-167 palavras** de extensão ótima
- **Auto-contidas** (extraíveis sem contexto externo)
- **Fact-rich** com estatísticas e dados específicos
- **Direct-answer** respondendo perguntas claramente

Cada bloco de conteúdo recebe score 0-100 composto por:
- Answer Block Quality (30%): padrões de definição, resposta direta, claims quotáveis
- Self-Containment (25%): densidade de pronomes, entidades nomeadas, extensão
- Structural Readability (20%): tamanho de sentença, listas, estrutura
- Statistical Density (15%): percentuais, valores monetários, números contextuais
- Uniqueness Signals (10%): dados originais, case studies, exemplos práticos

---

## Licença

MIT License — uso livre para fins comerciais e internos.

---

## Contribuindo

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/nova-analise`)
3. Commit suas mudanças (`git commit -m 'Add: nova análise X'`)
4. Push para a branch (`git push origin feature/nova-analise`)
5. Abra um Pull Request

---

Desenvolvido por **GFT Technologies** · 2026
