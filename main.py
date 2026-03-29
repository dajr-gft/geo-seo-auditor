#!/usr/bin/env python3
"""
GEO-SEO Auditor — CLI de auditoria GEO.

Uso:
    python main.py audit https://hotmart.com
    python main.py audit https://hotmart.com --output results/hotmart.json
    python main.py audit https://hotmart.com --brand "Hotmart" --format markdown
    python main.py citability https://hotmart.com
    python main.py crawlers https://hotmart.com
    python main.py brand "Hotmart" --domain hotmart.com
    python main.py schema https://hotmart.com
"""

import sys
import os
import json
import argparse
import logging
from pathlib import Path

# Adiciona diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import VERSION, APP_NAME
from auditor.orchestrator import run_full_audit
from auditor.page_fetcher import fetch_page, fetch_robots_txt, fetch_llms_txt
from auditor.citability_scorer import analyze_page_citability
from auditor.crawler_checker import check_ai_crawlers
from auditor.brand_scanner import scan_brand_presence
from auditor.schema_analyzer import analyze_schema
from auditor.report_generator import to_json, to_markdown, executive_summary


def setup_logging(verbose: bool = False):
    """Configura logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_audit(args):
    """Executa auditoria GEO completa."""
    result = run_full_audit(args.url, brand_name=args.brand)

    # Formata output
    if args.format == "json":
        output = to_json(result)
    elif args.format == "markdown":
        output = to_markdown(result)
    elif args.format == "executive":
        output = executive_summary(result)
    else:
        output = to_json(result)

    # Salva ou imprime
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"✓ Relatório salvo em: {output_path}")
        print(f"  GEO Score: {result.get('geo_score', 0)}/100")
        print(f"  Findings: {len(result.get('findings', []))}")
        print(f"  Quick wins: {len(result.get('quick_wins', []))}")
    else:
        print(output)


def cmd_citability(args):
    """Executa apenas análise de citabilidade."""
    page_data = fetch_page(args.url)
    if page_data["error"]:
        print(f"Erro: {page_data['error']}", file=sys.stderr)
        sys.exit(1)

    result = analyze_page_citability(page_data["content_blocks"])
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def cmd_crawlers(args):
    """Executa apenas checagem de AI crawlers."""
    robots_txt = fetch_robots_txt(args.url)
    llms_txt = fetch_llms_txt(args.url)
    result = check_ai_crawlers(robots_txt, args.url, llms_txt)

    # Remove chaves internas desnecessárias
    output = {
        "domain": result["domain"],
        "robots_txt_exists": result["robots_txt_exists"],
        "llms_txt_exists": result["llms_txt_exists"],
        "summary": result["summary"],
        "crawlers": result["crawlers"],
        "sitemaps": result["sitemaps"],
        "findings": result["findings"],
        "category_score": result["category_score"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))


def cmd_brand(args):
    """Executa apenas scan de marca."""
    result = scan_brand_presence(args.brand_name, domain=args.domain)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def cmd_schema(args):
    """Executa apenas análise de schema."""
    page_data = fetch_page(args.url)
    if page_data["error"]:
        print(f"Erro: {page_data['error']}", file=sys.stderr)
        sys.exit(1)

    result = analyze_schema(page_data["soup"], args.url)

    # Remove soup do output
    output = {k: v for k, v in result.items() if k != "schemas_found"}
    output["schemas_count"] = len(result.get("schemas_found", []))
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))


def main():
    parser = argparse.ArgumentParser(
        prog="geo-seo-auditor",
        description=f"{APP_NAME} v{VERSION} — Auditoria GEO para visibilidade em IA",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Output verboso")

    subparsers = parser.add_subparsers(dest="command", help="Comando a executar")

    # ── audit ──
    p_audit = subparsers.add_parser("audit", help="Auditoria GEO completa")
    p_audit.add_argument("url", help="URL da página a auditar")
    p_audit.add_argument("--brand", help="Nome da marca (auto-detectado se omitido)")
    p_audit.add_argument("--output", "-o", help="Caminho do arquivo de saída")
    p_audit.add_argument(
        "--format", "-f",
        choices=["json", "markdown", "executive"],
        default="json",
        help="Formato de saída (default: json)",
    )
    p_audit.set_defaults(func=cmd_audit)

    # ── citability ──
    p_cit = subparsers.add_parser("citability", help="Análise de citabilidade apenas")
    p_cit.add_argument("url", help="URL da página")
    p_cit.set_defaults(func=cmd_citability)

    # ── crawlers ──
    p_crawl = subparsers.add_parser("crawlers", help="Checagem de AI crawlers apenas")
    p_crawl.add_argument("url", help="URL do domínio")
    p_crawl.set_defaults(func=cmd_crawlers)

    # ── brand ──
    p_brand = subparsers.add_parser("brand", help="Scan de marca apenas")
    p_brand.add_argument("brand_name", help="Nome da marca")
    p_brand.add_argument("--domain", help="Domínio do site")
    p_brand.set_defaults(func=cmd_brand)

    # ── schema ──
    p_schema = subparsers.add_parser("schema", help="Análise de schema apenas")
    p_schema.add_argument("url", help="URL da página")
    p_schema.set_defaults(func=cmd_schema)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
