"""Shared fixtures for the treasury test suite."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import Base, get_db
from treasury.models.llc_configuration import LLCConfiguration
from treasury.models.property_status import PropertyStatus
from treasury.models.property_cash_flow_history import PropertyCashFlowHistory
from treasury.models.transaction_ledger import TransactionLedger

_TREASURY_TABLES = [
    LLCConfiguration.__table__,
    PropertyStatus.__table__,
    PropertyCashFlowHistory.__table__,
    TransactionLedger.__table__,
]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=_TREASURY_TABLES)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    from treasury.controllers.llc_controller import router as llc_router
    from treasury.controllers.property_controller import router as property_router
    from treasury.controllers.cash_flow_controller import router as cash_flow_router
    from treasury.controllers.transaction_controller import router as transaction_router
    from treasury.controllers.webhook_controller import router as webhook_router
    from treasury.controllers.settlement_controller import router as settlement_router

    app.include_router(llc_router)
    app.include_router(property_router)
    app.include_router(cash_flow_router)
    app.include_router(transaction_router)
    app.include_router(webhook_router)
    app.include_router(settlement_router)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
