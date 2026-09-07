from dotenv import load_dotenv

load_dotenv()

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import engine, SessionLocal
import bootstrap
from routers import ALL_ROUTERS, health as health_router
from BL.auth.common.app_key import require_app_key
from BL.common.logging_redact import install_access_log_redaction
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

# One MCP tool per endpoint above, served at /mcp[/<MCP_PATH_SECRET>].
mcp_server.mount(app)
