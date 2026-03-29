"""
Page Fetcher — Requisição HTTP e parsing de HTML.

Responsável por:
- Fetch da página com headers realistas
- Parsing do HTML via BeautifulSoup
- Extração de blocos de conteúdo (headings + parágrafos)
- Extração de metadata (title, description, canonical)
- Detecção de tecnologia (SSR, SPA, CMS)
"""

import re
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS, DEFAULT_TIMEOUT, MIN_BLOCK_WORDS

logger = logging.getLogger(__name__)


def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Faz fetch de uma URL e retorna HTML parseado + metadados.

    Args:
        url: URL completa da página a ser analisada.
        timeout: Timeout em segundos para a requisição.

    Returns:
        dict com chaves:
            - url: URL final (após redirects)
            - status_code: código HTTP
            - html: conteúdo HTML bruto
            - soup: objeto BeautifulSoup parseado
            - title: tag <title>
            - meta_description: meta description
            - canonical: URL canonical
            - content_blocks: lista de {heading, content} extraídos
            - technology: detecção de SSR/SPA/CMS
            - error: mensagem de erro (se houver)
    """
    result = {
        "url": url,
        "status_code": None,
        "html": None,
        "soup": None,
        "title": None,
        "meta_description": None,
        "canonical": None,
        "content_blocks": [],
        "technology": {},
        "error": None,
    }

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        result["status_code"] = response.status_code
        result["url"] = response.url  # URL final após redirects
        response.raise_for_status()

    except requests.exceptions.Timeout:
        result["error"] = f"Timeout após {timeout}s"
        logger.error("Timeout fetching %s", url)
        return result
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Erro de conexão: {str(e)[:200]}"
        logger.error("Connection error fetching %s: %s", url, e)
        return result
    except requests.exceptions.HTTPError as e:
        result["error"] = f"HTTP {response.status_code}: {str(e)[:200]}"
        logger.warning("HTTP error fetching %s: %s", url, e)
        return result
    except Exception as e:
        result["error"] = f"Erro inesperado: {str(e)[:200]}"
        logger.error("Unexpected error fetching %s: %s", url, e)
        return result

    # ── Parse HTML ──
    result["html"] = response.text
    soup = BeautifulSoup(response.text, "html.parser")
    result["soup"] = soup

    # ── Metadata ──
    result["title"] = _extract_title(soup)
    result["meta_description"] = _extract_meta(soup, "description")
    result["canonical"] = _extract_canonical(soup, url)

    # ── Blocos de conteúdo ──
    result["content_blocks"] = _extract_content_blocks(soup)

    # ── Detecção de tecnologia ──
    result["technology"] = _detect_technology(soup, response)

    logger.info(
        "Fetched %s — %d blocks, title: %s",
        url, len(result["content_blocks"]), result["title"][:60] if result["title"] else "N/A"
    )

    return result


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Extrai o título da página."""
    tag = soup.find("title")
    return tag.get_text(strip=True) if tag else None


def _extract_meta(soup: BeautifulSoup, name: str) -> Optional[str]:
    """Extrai conteúdo de uma meta tag pelo atributo name."""
    tag = soup.find("meta", attrs={"name": name})
    if not tag:
        # Tenta og: prefix
        tag = soup.find("meta", attrs={"property": f"og:{name}"})
    return tag.get("content", "").strip() if tag else None


def _extract_canonical(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Extrai URL canonical."""
    tag = soup.find("link", attrs={"rel": "canonical"})
    if tag and tag.get("href"):
        href = tag["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        return href
    return None


def _extract_content_blocks(soup: BeautifulSoup) -> list[dict]:
    """
    Extrai blocos de conteúdo agrupados por heading.

    Percorre o DOM buscando headings (h1-h4) e agrupa os parágrafos,
    listas e tabelas subsequentes como conteúdo daquela seção.

    Returns:
        Lista de dicts {heading: str, content: str, tag: str}
    """
    # Remove elementos que não são conteúdo
    for tag_name in ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]:
        for element in soup.find_all(tag_name):
            element.decompose()

    blocks = []
    current_heading = "Introduction"
    current_heading_tag = "h1"
    current_paragraphs = []

    content_tags = ["h1", "h2", "h3", "h4", "p", "ul", "ol", "table", "blockquote", "dl"]

    for element in soup.find_all(content_tags):
        if element.name.startswith("h"):
            # Salva seção anterior se tiver conteúdo suficiente
            if current_paragraphs:
                combined = " ".join(current_paragraphs)
                word_count = len(combined.split())
                if word_count >= MIN_BLOCK_WORDS:
                    blocks.append({
                        "heading": current_heading,
                        "heading_tag": current_heading_tag,
                        "content": combined,
                        "word_count": word_count,
                    })

            current_heading = element.get_text(strip=True)
            current_heading_tag = element.name
            current_paragraphs = []
        else:
            text = element.get_text(strip=True)
            if text and len(text.split()) >= 5:
                current_paragraphs.append(text)

    # Último bloco
    if current_paragraphs:
        combined = " ".join(current_paragraphs)
        word_count = len(combined.split())
        if word_count >= MIN_BLOCK_WORDS:
            blocks.append({
                "heading": current_heading,
                "heading_tag": current_heading_tag,
                "content": combined,
                "word_count": word_count,
            })

    return blocks


def _detect_technology(soup: BeautifulSoup, response: requests.Response) -> dict:
    """
    Detecta tecnologia utilizada na página.

    Verifica sinais de SSR, SPA, CMS e frameworks.
    """
    tech = {
        "is_ssr": True,       # assume SSR até provar contrário
        "is_spa": False,
        "cms": None,
        "framework": None,
        "has_service_worker": False,
    }

    html = response.text.lower()

    # ── SPA detection ──
    # Se o body tem pouco conteúdo mas muitos scripts, provavelmente é SPA
    body = soup.find("body")
    if body:
        body_text = body.get_text(strip=True)
        scripts = soup.find_all("script")
        if len(body_text) < 200 and len(scripts) > 5:
            tech["is_spa"] = True
            tech["is_ssr"] = False

    # ── React / Next.js ──
    if "__next" in html or "__NEXT_DATA__" in html:
        tech["framework"] = "Next.js"
        tech["is_ssr"] = True
    elif "react" in html and "_reactRoot" in html:
        tech["framework"] = "React"

    # ── Vue / Nuxt ──
    if "__nuxt" in html or "nuxt" in html:
        tech["framework"] = "Nuxt.js"
        tech["is_ssr"] = True
    elif "vue" in html and "v-" in html:
        tech["framework"] = "Vue.js"

    # ── Angular ──
    if "ng-version" in html or "ng-app" in html:
        tech["framework"] = "Angular"

    # ── CMS detection ──
    if "wp-content" in html or "wordpress" in html:
        tech["cms"] = "WordPress"
    elif "shopify" in html:
        tech["cms"] = "Shopify"
    elif "wix.com" in html:
        tech["cms"] = "Wix"
    elif "squarespace" in html:
        tech["cms"] = "Squarespace"
    elif "hubspot" in html:
        tech["cms"] = "HubSpot"

    # ── Gerador meta tag ──
    generator = soup.find("meta", attrs={"name": "generator"})
    if generator:
        gen_content = generator.get("content", "")
        if gen_content and not tech["cms"]:
            tech["cms"] = gen_content

    return tech


def fetch_robots_txt(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """
    Faz fetch do robots.txt de um domínio.

    Args:
        url: Qualquer URL do domínio (extrai scheme + netloc).
        timeout: Timeout em segundos.

    Returns:
        Conteúdo do robots.txt como string, ou None se não encontrado.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        response = requests.get(
            robots_url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        if response.status_code == 200:
            logger.info("robots.txt found at %s (%d bytes)", robots_url, len(response.text))
            return response.text
        else:
            logger.warning("robots.txt returned %d at %s", response.status_code, robots_url)
            return None
    except Exception as e:
        logger.error("Error fetching robots.txt from %s: %s", robots_url, e)
        return None


def fetch_llms_txt(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """
    Verifica se existe um arquivo llms.txt no domínio.

    Args:
        url: Qualquer URL do domínio.
        timeout: Timeout em segundos.

    Returns:
        Conteúdo do llms.txt como string, ou None se não encontrado.
    """
    parsed = urlparse(url)
    llms_url = f"{parsed.scheme}://{parsed.netloc}/llms.txt"

    try:
        response = requests.get(
            llms_url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        if response.status_code == 200 and len(response.text.strip()) > 10:
            logger.info("llms.txt found at %s", llms_url)
            return response.text
        return None
    except Exception:
        return None
