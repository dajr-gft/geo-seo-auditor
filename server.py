"""
GEO-SEO Auditor — Server FastAPI.

Endpoints:
  GET  /              → Dashboard HTML (static)
  POST /api/audit     → Executa audit completo e retorna JSON
  GET  /api/health    → Health check para Cloud Run

Deploy:
  docker build -t geo-seo-auditor .
  gcloud run deploy geo-seo-auditor --source .
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auditor.orchestrator import run_full_audit, run_domain_audit
from auditor.page_fetcher import fetch_robots_txt, fetch_llms_txt
from auditor.crawler_checker import check_ai_crawlers
from auditor.brand_scanner import scan_brand_presence
from auditor.report_generator import _clean_for_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("GEO-SEO Auditor server starting...")
    yield
    logger.info("GEO-SEO Auditor server shutting down.")


app = FastAPI(
    title="GEO-SEO Auditor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Static files ──
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Routes ──

@app.get("/")
async def dashboard():
    """Serve o dashboard HTML."""
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health():
    """Health check para Cloud Run."""
    return {"status": "ok", "service": "geo-seo-auditor"}


class AuditRequest(BaseModel):
    url: str = "https://hotmart.com"
    brand: Optional[str] = None


class DomainAuditRequest(BaseModel):
    url: str = "https://hotmart.com"
    brand: Optional[str] = None
    scope_path: str = "/pt-br"
    max_pages: int = 60


@app.post("/api/audit")
async def audit(req: AuditRequest):
    """
    Executa audit GEO completo.

    Roda todos os scripts de análise (citability, crawlers, brand, schema)
    contra o URL fornecido e retorna o JSON estruturado.
    """
    logger.info("Audit requested for: %s (brand: %s)", req.url, req.brand)

    try:
        result = run_full_audit(req.url, brand_name=req.brand)
        clean = _clean_for_json(result)
        logger.info("Audit complete: GEO Score %d/100", clean.get("geo_score", 0))
        return JSONResponse(content=clean)

    except Exception as e:
        logger.error("Audit failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


@app.post("/api/audit/domain")
async def audit_domain(req: DomainAuditRequest):
    """Executa auditoria de domínio completo dentro de um escopo (ex.: /pt-br)."""
    logger.info(
        "Domain audit requested for: %s (brand=%s, scope=%s, max_pages=%d)",
        req.url,
        req.brand,
        req.scope_path,
        req.max_pages,
    )

    try:
        result = run_domain_audit(
            req.url,
            brand_name=req.brand,
            scope_path=req.scope_path,
            max_pages=req.max_pages,
        )
        clean = _clean_for_json(result)
        logger.info(
            "Domain audit complete: GEO Score %d/100 (%d pages analyzed)",
            clean.get("geo_score", 0),
            clean.get("scan_summary", {}).get("pages_analyzed", 0),
        )
        return JSONResponse(content=clean)
    except Exception as e:
        logger.error("Domain audit failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Domain audit failed: {str(e)}")


@app.post("/api/crawlers")
async def crawlers_only(req: AuditRequest):
    """Executa apenas checagem de AI crawlers."""
    try:
        robots_txt = fetch_robots_txt(req.url)
        llms_txt = fetch_llms_txt(req.url)
        result = check_ai_crawlers(robots_txt, req.url, llms_txt)
        return JSONResponse(content=_clean_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/brand")
async def brand_only(req: AuditRequest):
    """Executa apenas scan de marca."""
    try:
        brand_name = req.brand or "Hotmart"
        result = scan_brand_presence(brand_name, domain=req.url)
        return JSONResponse(content=_clean_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Run ──

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
