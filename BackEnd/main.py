from dotenv import load_dotenv

load_dotenv()

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

import os
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import engine, SessionLocal
import bootstrap
from routers import ALL_ROUTERS, health as health_router
from BL.auth.common.app_key import require_app_key
from BL.common.body_limit import BodyLimitMiddleware
from BL.common.logging_redact import install_access_log_redaction, install_secret_redaction
import mcp_server


def app_env() -> str:
    """`production` on Render (it sets `RENDER=true`) unless APP_ENV says otherwise."""
    return (os.getenv("APP_ENV") or ("production" if os.getenv("RENDER") else "development")).strip().lower()


IS_PRODUCTION = app_env() == "production"

# `lifespan` starts the MCP transport; it does not touch the HTTP routes or OpenAPI.
# The interactive docs are a route map for anyone on the internet; production
# serves the API only (`app.openapi()` still works for the MCP tool list).
app = FastAPI(
    lifespan=mcp_server.lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

bootstrap.run(engine, SessionLocal)


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """An unexpected error never reaches the client as exception text.

    The traceback is logged under a reference id; the client gets the id so a
    log line can be found from a screenshot. Deliberate `HTTPException`s are
    not affected -- FastAPI handles those before this handler.
    """
    ref = uuid.uuid4().hex[:12]
    logger.exception("unhandled error ref=%s %s %s", ref, request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error", "ref": ref})


# Outermost: a request body over MAX_BODY_BYTES is refused before it is read.
app.add_middleware(BodyLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://bigwhales.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 0 stopgap gate (SECURITY_PLAN.md §4, step 0.2): every data route requires
# the shared key when APP_KEY_MODE is on. `/helloworld` stays public -- it is the
# connection ping and Render's health check. The dependency declares no
# parameter, so the OpenAPI contract is unchanged.
for r in ALL_ROUTERS:
    if r is health_router:
        app.include_router(r)
    else:
        app.include_router(r, dependencies=[Depends(require_app_key)])

install_access_log_redaction()
install_secret_redaction()

# One MCP tool per endpoint above, served at /mcp[/<MCP_PATH_SECRET>].
mcp_server.mount(app)
