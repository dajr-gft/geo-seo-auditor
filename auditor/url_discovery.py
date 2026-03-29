"""
URL Discovery — Descoberta de URLs para auditoria de domínio.

Estratégia:
1) Tenta sitemap.xml (inclui suporte a sitemap index)
2) Filtra por mesmo domínio e prefixo de escopo (ex.: /pt-br)
3) Se não encontrar URLs suficientes, faz fallback por links da homepage
"""

import logging
from collections import deque
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    DEFAULT_HEADERS,
    DOMAIN_AUDIT_DISCOVERY_TIMEOUT,
    DOMAIN_AUDIT_SITEMAP_MAX_URLS,
)

logger = logging.getLogger(__name__)


def discover_domain_urls(
    base_url: str,
    scope_path: str = "/pt-br",
    max_urls: int = 60,
    timeout: int = DOMAIN_AUDIT_DISCOVERY_TIMEOUT,
) -> list[str]:
    """Descobre URLs do mesmo domínio e dentro do escopo informado."""
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    normalized_scope = _normalize_scope(scope_path)

    urls = _discover_from_sitemap(root, normalized_scope, max_urls=max_urls, timeout=timeout)
    if len(urls) >= max_urls:
        return urls[:max_urls]

    # Fallback quando sitemap não existe, está incompleto ou bloqueado.
    fallback = _discover_from_internal_links(root, normalized_scope, max_urls=max_urls, timeout=timeout)

    merged = []
    seen = set()
    for url in urls + fallback:
        if url not in seen:
            seen.add(url)
            merged.append(url)
        if len(merged) >= max_urls:
            break

    return merged


def _discover_from_sitemap(root: str, scope_path: str, max_urls: int, timeout: int) -> list[str]:
    sitemap_url = f"{root}/sitemap.xml"
    try:
        resp = requests.get(sitemap_url, headers=DEFAULT_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            logger.info("sitemap.xml not available (%d): %s", resp.status_code, sitemap_url)
            return []

        soup = BeautifulSoup(resp.text, "xml")

        # Caso 1: sitemap index
        nested_sitemaps = [loc.get_text(strip=True) for loc in soup.find_all("sitemap") for loc in loc.find_all("loc")]
        if nested_sitemaps:
            urls = []
            for nested in nested_sitemaps[:50]:
                urls.extend(_read_urlset(nested, root, scope_path, timeout))
                if len(urls) >= max_urls:
                    break
            return _dedupe(urls)[:max_urls]

        # Caso 2: urlset direto
        return _read_urlset(sitemap_url, root, scope_path, timeout)[:max_urls]

    except Exception as exc:
        logger.warning("Error reading sitemap %s: %s", sitemap_url, exc)
        return []


def _read_urlset(sitemap_url: str, root: str, scope_path: str, timeout: int) -> list[str]:
    try:
        resp = requests.get(sitemap_url, headers=DEFAULT_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "xml")
        urls = []
        for loc in soup.find_all("loc")[:DOMAIN_AUDIT_SITEMAP_MAX_URLS]:
            value = loc.get_text(strip=True)
            normalized = _normalize_url(value)
            if _in_scope(normalized, root, scope_path):
                urls.append(normalized)
        return _dedupe(urls)
    except Exception:
        return []


def _discover_from_internal_links(root: str, scope_path: str, max_urls: int, timeout: int) -> list[str]:
    start = f"{root}{scope_path}" if scope_path != "/" else root
    queue = deque([start, root])
    seen = set()
    found = []

    while queue and len(found) < max_urls:
        current = queue.popleft()
        current = _normalize_url(current)
        if current in seen:
            continue
        seen.add(current)

        try:
            resp = requests.get(current, headers=DEFAULT_HEADERS, timeout=timeout)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception:
            continue

        if _in_scope(current, root, scope_path):
            found.append(current)

        for link in soup.find_all("a", href=True):
            abs_url = _normalize_url(urljoin(current, link["href"]))
            if not _in_scope(abs_url, root, scope_path):
                continue
            if abs_url not in seen:
                queue.append(abs_url)

    return _dedupe(found)


def _normalize_scope(scope_path: Optional[str]) -> str:
    if not scope_path:
        return "/"
    scope = scope_path.strip()
    if not scope.startswith("/"):
        scope = "/" + scope
    return scope.rstrip("/") or "/"


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or "/"
    cleaned = parsed._replace(query="", fragment="", path=path)
    return cleaned.geturl()


def _in_scope(url: str, root: str, scope_path: str) -> bool:
    parsed = urlparse(url)
    root_parsed = urlparse(root)

    if parsed.netloc != root_parsed.netloc:
        return False

    if scope_path == "/":
        return True

    path = parsed.path.rstrip("/") or "/"
    return path == scope_path or path.startswith(scope_path + "/")


def _dedupe(items: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out

