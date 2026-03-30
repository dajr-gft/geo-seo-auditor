"""
GEO-SEO Auditor — Server FastAPI.

Endpoints:
  GET  /                   → Dashboard HTML (static)
  GET  /api/health         → Health check para Cloud Run
  GET  /api/latest         → Última auditoria do BigQuery
  GET  /api/history        → Histórico de auditorias do BigQuery
  POST /api/audit          → Executa audit de página única → salva no BQ
  POST /api/audit/domain   → Executa audit de domínio completo → salva no BQ
  POST /api/crawlers       → Checagem de AI crawlers (sem persistência)
  POST /api/brand          → Scan de marca (sem persistência)
"""

import os
import sys
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auditor.orchestrator import run_full_audit, run_domain_audit
from auditor.page_fetcher import fetch_robots_txt, fetch_llms_txt
from auditor.crawler_checker import check_ai_crawlers
from auditor.brand_scanner import scan_brand_presence
from auditor.report_generator import _clean_for_json
from bigquery_store import save_audit, get_latest_audit, get_audit_history

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


# ── Helper ──────────────────────────────────────────────────────────────────

def _save_to_bq(result: dict, audit_type: str) -> None:
    """Salva no BQ — chamado via BackgroundTasks (após response enviado)."""
    try:
        audit_id = save_audit(result, audit_type)
        logger.info("BQ save complete: audit_id=%s", audit_id)
    except Exception as e:
        logger.error("BQ save failed: %s", str(e))


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
async def dashboard():
    """Serve o dashboard HTML."""
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health():
    """Health check para Cloud Run."""
    return {"status": "ok", "service": "geo-seo-auditor"}


@app.get("/api/latest")
async def latest(domain: str = Query(default=None, description="Filtrar por domínio")):
    """
    Retorna a auditoria mais recente do BigQuery.
    Usado pelo dashboard no carregamento inicial da página.
    """
    try:
        result = await asyncio.to_thread(get_latest_audit, domain)
        if result is None:
            raise HTTPException(status_code=404, detail="Nenhuma auditoria encontrada.")
        return JSONResponse(content=_clean_for_json(result))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/latest failed: %s", str(e))
        raise HTTPException(status_code=503, detail=f"BigQuery indisponível: {str(e)}")


@app.get("/api/history")
async def history(
    domain: str = Query(default=None, description="Filtrar por domínio"),
    limit: int = Query(default=10, ge=1, le=100),
):
    """
    Retorna histórico resumido de auditorias do BigQuery.
    Campos escalares apenas — sem raw_result.
    """
    try:
        results = await asyncio.to_thread(get_audit_history, domain, limit)
        return JSONResponse(content={"audits": results, "count": len(results)})
    except Exception as e:
        logger.error("GET /api/history failed: %s", str(e))
        raise HTTPException(status_code=503, detail=f"BigQuery indisponível: {str(e)}")


class AuditRequest(BaseModel):
    url: str = "https://hotmart.com"
    brand: Optional[str] = None


class DomainAuditRequest(BaseModel):
    url: str = "https://hotmart.com"
    brand: Optional[str] = None
    scope_path: str = "/pt-br"
    max_pages: int = 60


@app.post("/api/audit")
async def audit(req: AuditRequest, background_tasks: BackgroundTasks):
    """
    Executa audit GEO de página única.
    Retorna o resultado imediatamente e salva no BigQuery em background.
    """
    logger.info("Audit requested: url=%s brand=%s", req.url, req.brand)
    try:
        result = run_full_audit(req.url, brand_name=req.brand)
        clean = _clean_for_json(result)
        background_tasks.add_task(_save_to_bq, clean, "single_page")
        logger.info("Audit complete: GEO Score %d/100", clean.get("geo_score", 0))
        return JSONResponse(content=clean)
    except Exception as e:
        logger.error("Audit failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


@app.post("/api/audit/domain")
async def audit_domain(req: DomainAuditRequest, background_tasks: BackgroundTasks):
    """
    Executa audit GEO de domínio completo.
    Retorna o resultado imediatamente e salva no BigQuery em background.
    """
    logger.info(
        "Domain audit requested: url=%s brand=%s scope=%s max_pages=%d",
        req.url, req.brand, req.scope_path, req.max_pages,
    )
    try:
        result = run_domain_audit(
            req.url,
            brand_name=req.brand,
            scope_path=req.scope_path,
            max_pages=req.max_pages,
        )
        clean = _clean_for_json(result)
        background_tasks.add_task(_save_to_bq, clean, "domain")
        logger.info(
            "Domain audit complete: GEO Score %d/100 (%d pages)",
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


# ── ADK Agent (Letícia) ──────────────────────────────────────────────────────

_agent_runner = None
_runner_error: Optional[str] = None


def _get_runner():
    """Inicialização lazy do ADK Runner (operação síncrona — só cria objetos Python)."""
    global _agent_runner, _runner_error
    if _runner_error:
        raise RuntimeError(_runner_error)
    if _agent_runner is None:
        try:
            agentes_path = os.path.join(os.path.dirname(__file__), "agentes")
            if agentes_path not in sys.path:
                sys.path.insert(0, agentes_path)
            from leticia.agent import root_agent
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            _agent_runner = Runner(
                agent=root_agent,
                app_name="leticia_geo_seo",
                session_service=InMemorySessionService(),
            )
            logger.info("ADK Runner initialized: agent=%s", root_agent.name)
        except Exception as e:
            _runner_error = str(e)
            logger.error("ADK Runner init failed: %s", str(e))
            raise
    return _agent_runner


_AGENT_TIMEOUT = 60  # segundos máximos por chamada ao agente
_QUOTA_MSGS = ("quota", "rate", "429", "resource exhausted", "resource_exhausted")
_QUOTA_WAIT = 10     # segundos de espera em quota error antes de tentar de novo


async def _run_agent_async(message: str, session_id: str) -> str:
    """Executa o agente usando run_async (InMemorySessionService é async)."""
    from google.genai import types as gt

    runner = _get_runner()

    # create_session é async — deve ser awaited
    try:
        await runner.session_service.create_session(
            app_name="leticia_geo_seo",
            user_id="dashboard",
            session_id=session_id,
        )
    except Exception:
        pass  # sessão já existe — ok

    content = gt.Content(role="user", parts=[gt.Part(text=message)])

    async def _invoke() -> str:
        final_text = ""
        last_text = ""
        async for event in runner.run_async(
            user_id="dashboard", session_id=session_id, new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        last_text = part.text
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            final_text = part.text
                            break
                logger.info("ADK final response: %d chars", len(final_text))
        return final_text or last_text or ""

    # Retry único em quota/rate-limit; timeout global
    for attempt in range(2):
        try:
            text = await asyncio.wait_for(_invoke(), timeout=_AGENT_TIMEOUT)
            if text:
                return text
            # resposta vazia mas sem erro — retorna placeholder
            return "Não consegui obter uma resposta. Tente reformular a pergunta."
        except asyncio.TimeoutError:
            logger.warning("ADK timeout (attempt %d/%d)", attempt + 1, 2)
            return "A análise demorou mais do que o esperado. Tente novamente em instantes."
        except Exception as e:
            err_lower = str(e).lower()
            is_quota = any(q in err_lower for q in _QUOTA_MSGS)
            if is_quota and attempt == 0:
                logger.warning("ADK quota/rate-limit — aguardando %ds antes de retry", _QUOTA_WAIT)
                await asyncio.sleep(_QUOTA_WAIT)
                continue
            logger.error("ADK error (attempt %d): %s", attempt + 1, str(e))
            if is_quota:
                return "Limite de requisições atingido. Aguarde alguns segundos e tente novamente."
            raise

    return "Sem resposta."


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Envia mensagem para Letícia (ADK Agent) e retorna resposta."""
    session_id = req.session_id.strip() or str(uuid.uuid4())
    logger.info("Chat request: session=%s msg_len=%d", session_id, len(req.message))
    try:
        response = await _run_agent_async(req.message, session_id)
        return JSONResponse(content={"response": response, "session_id": session_id})
    except Exception as e:
        logger.error("Chat failed: %s", str(e))
        raise HTTPException(status_code=503, detail=f"Agente indisponível: {str(e)}")


# ── Run ──

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
