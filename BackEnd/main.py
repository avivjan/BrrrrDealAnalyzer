from dotenv import load_dotenv

load_dotenv()

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import engine, SessionLocal
import bootstrap
from routers import ALL_ROUTERS
import mcp_server

# `lifespan` starts the MCP transport; it does not touch the HTTP routes or OpenAPI.
app = FastAPI(lifespan=mcp_server.lifespan)

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

for r in ALL_ROUTERS:
    app.include_router(r)

# One MCP tool per endpoint above, served at /mcp[/<MCP_PATH_SECRET>].
mcp_server.mount(app)
