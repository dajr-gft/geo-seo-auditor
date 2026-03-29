"""
GEO-SEO Auditor — Configurações globais e constantes.

Centraliza todas as constantes de scoring, limiares e configurações
utilizadas pelos módulos de análise.
"""

# ============================================================
# VERSÃO
# ============================================================
VERSION = "1.0.0"
APP_NAME = "GEO-SEO Auditor"

# ============================================================
# HTTP — configurações de requisição
# ============================================================
DEFAULT_TIMEOUT = 30  # segundos
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
}

# ============================================================
# DOMAIN AUDIT — crawling/discovery defaults
# ============================================================
DOMAIN_AUDIT_DEFAULT_SCOPE_PATH = "/pt-br"
DOMAIN_AUDIT_MAX_PAGES = 60
DOMAIN_AUDIT_SITEMAP_MAX_URLS = 5000
DOMAIN_AUDIT_DISCOVERY_TIMEOUT = 20

# ============================================================
# SCORING — pesos por categoria (somam 100%)
# ============================================================
CATEGORY_WEIGHTS = {
    "ai_citability":         25,
    "brand_authority":       20,
    "content_eeat":          20,
    "technical":             15,
    "schema":                10,
    "platform_optimization": 10,
}

# ============================================================
# CITABILITY — parâmetros de scoring de passagens
# ============================================================
OPTIMAL_WORD_COUNT_MIN = 134  # palavras — início da faixa ótima
OPTIMAL_WORD_COUNT_MAX = 167  # palavras — fim da faixa ótima
MIN_BLOCK_WORDS = 50          # mínimo para considerar um bloco citável
MIN_PASSAGE_WORDS = 5         # mínimo por sentença/parágrafo

# Limiares de grade
GRADE_THRESHOLDS = {
    "A": 80,  # Highly Citable
    "B": 65,  # Good Citability
    "C": 50,  # Moderate Citability
    "D": 35,  # Low Citability
    "F": 0,   # Poor Citability
}

# ============================================================
# AI CRAWLERS — lista de user-agents de crawlers de IA
# Fonte: documentação oficial de cada plataforma (2026)
# ============================================================
AI_CRAWLERS = [
    {
        "user_agent": "GPTBot",
        "platform": "ChatGPT",
        "operator": "OpenAI",
        "critical": True,
        "doc_url": "https://platform.openai.com/docs/gptbot",
    },
    {
        "user_agent": "OAI-SearchBot",
        "platform": "ChatGPT Search",
        "operator": "OpenAI",
        "critical": True,
        "doc_url": "https://platform.openai.com/docs/bots",
    },
    {
        "user_agent": "ChatGPT-User",
        "platform": "ChatGPT Browse",
        "operator": "OpenAI",
        "critical": True,
        "doc_url": "https://platform.openai.com/docs/bots",
    },
    {
        "user_agent": "ClaudeBot",
        "platform": "Claude / Perplexity",
        "operator": "Anthropic",
        "critical": True,
        "doc_url": "https://docs.anthropic.com/en/docs/claude-bot",
    },
    {
        "user_agent": "anthropic-ai",
        "platform": "Claude (training)",
        "operator": "Anthropic",
        "critical": True,
        "doc_url": "https://docs.anthropic.com/en/docs/claude-bot",
    },
    {
        "user_agent": "PerplexityBot",
        "platform": "Perplexity AI",
        "operator": "Perplexity",
        "critical": True,
        "doc_url": "https://docs.perplexity.ai/guides/perplexity-bot",
    },
    {
        "user_agent": "Google-Extended",
        "platform": "Google Gemini / AI Overviews",
        "operator": "Google",
        "critical": True,
        "doc_url": "https://developers.google.com/search/docs/crawling-indexing/google-extended",
    },
    {
        "user_agent": "Googlebot",
        "platform": "Google Search",
        "operator": "Google",
        "critical": False,
        "doc_url": "https://developers.google.com/search/docs/crawling-indexing/googlebot",
    },
    {
        "user_agent": "Bingbot",
        "platform": "Bing Copilot",
        "operator": "Microsoft",
        "critical": False,
        "doc_url": "https://www.bing.com/webmaster/help/which-crawlers-does-bing-use",
    },
    {
        "user_agent": "Meta-ExternalAgent",
        "platform": "Meta AI",
        "operator": "Meta",
        "critical": False,
        "doc_url": "https://developers.facebook.com/docs/sharing/bot",
    },
    {
        "user_agent": "Bytespider",
        "platform": "TikTok / Doubao",
        "operator": "ByteDance",
        "critical": False,
        "doc_url": None,
    },
    {
        "user_agent": "cohere-ai",
        "platform": "Cohere",
        "operator": "Cohere",
        "critical": False,
        "doc_url": None,
    },
    {
        "user_agent": "Diffbot",
        "platform": "Various AI aggregators",
        "operator": "Diffbot",
        "critical": False,
        "doc_url": "https://docs.diffbot.com",
    },
    {
        "user_agent": "CCBot",
        "platform": "Common Crawl",
        "operator": "Common Crawl Foundation",
        "critical": False,
        "doc_url": "https://commoncrawl.org/ccbot",
    },
    {
        "user_agent": "YouBot",
        "platform": "You.com",
        "operator": "You.com",
        "critical": False,
        "doc_url": None,
    },
]

# ============================================================
# BRAND SCANNING — plataformas e pesos de correlação
# Fonte: Ahrefs Dec 2025 study (75K brands)
# ============================================================
BRAND_PLATFORMS = {
    "youtube": {
        "name": "YouTube",
        "correlation": 0.737,
        "weight": 25,
        "search_tpl": "https://www.youtube.com/results?search_query={query}",
    },
    "reddit": {
        "name": "Reddit",
        "correlation": 0.580,
        "weight": 25,
        "search_tpl": "https://www.reddit.com/search/?q={query}",
    },
    "wikipedia": {
        "name": "Wikipedia",
        "correlation": 0.520,
        "weight": 20,
        "api_tpl": "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json",
    },
    "linkedin": {
        "name": "LinkedIn",
        "correlation": 0.410,
        "weight": 15,
        "search_tpl": "https://www.linkedin.com/search/results/companies/?keywords={query}",
    },
    "wikidata": {
        "name": "Wikidata",
        "correlation": 0.480,
        "weight": 15,
        "api_tpl": "https://www.wikidata.org/w/api.php?action=wbsearchentities&search={query}&language=en&format=json",
    },
}

# Plataformas adicionais para checagem (sem API pública direta)
ADDITIONAL_PLATFORMS = [
    "Quora", "Stack Overflow", "GitHub", "Crunchbase",
    "Product Hunt", "G2", "Trustpilot", "Capterra",
]

# ============================================================
# SCHEMA — tipos de schema esperados por vertical
# ============================================================
SCHEMA_TYPES_PRIORITY = [
    "Organization",
    "WebSite",
    "WebPage",
    "Product",
    "SoftwareApplication",
    "Course",
    "Article",
    "FAQPage",
    "HowTo",
    "BreadcrumbList",
    "LocalBusiness",
    "Person",
    "Review",
    "AggregateRating",
    "VideoObject",
    "ImageObject",
]

# ============================================================
# SEVERITY — classificação de findings
# ============================================================
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
