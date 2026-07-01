"""Tests P3 — endpoints FastAPI."""
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from valo.dependencies import get_session
from valo.main import app
from valo.models import Base


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override():
        s = Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── Targets ───────────────────────────────────────────────────────────────────

def test_create_target(client):
    r = client.post('/targets', json={
        'name': 'Syroco', 'is_recurring': True, 'valuation_aggregate': 'arr',
    })
    assert r.status_code == 201
    assert r.json()['name'] == 'Syroco'


def test_list_targets_empty(client):
    r = client.get('/targets')
    assert r.status_code == 200
    assert r.json() == []


def test_get_target_not_found(client):
    r = client.get('/targets/999')
    assert r.status_code == 404


def test_create_anchor(client):
    t = client.post('/targets', json={'name': 'T', 'is_recurring': True, 'valuation_aggregate': 'revenue'}).json()
    r = client.post(f'/targets/{t["id"]}/anchors', json={
        'entry_date': '2023-06-30',
        'm_entry_aggregate': 8.0,
        'm_market_entry': 10.0,
    })
    assert r.status_code == 201
    assert r.json()['m_entry_aggregate'] == 8.0


# ── Comps ─────────────────────────────────────────────────────────────────────

def test_create_comp(client):
    r = client.post('/comps', json={'name': 'Adobe', 'ticker': 'ADBE', 'currency': 'USD', 'is_recurring': True})
    assert r.status_code == 201
    assert r.json()['ticker'] == 'ADBE'


def test_create_comp_duplicate(client):
    client.post('/comps', json={'name': 'Adobe', 'ticker': 'ADBE', 'currency': 'USD', 'is_recurring': True})
    r = client.post('/comps', json={'name': 'Adobe2', 'ticker': 'adbe', 'currency': 'USD', 'is_recurring': True})
    assert r.status_code == 409


def test_get_comp_not_found(client):
    r = client.get('/comps/ZZZZ')
    assert r.status_code == 404


# ── Transactions ──────────────────────────────────────────────────────────────

def test_transaction_crud(client):
    r = client.post('/transactions', json={
        'target_company': 'Acme SaaS',
        'tx_date': '2023-06-01',
        'implied_multiple': 8.5,
        'price_disclosed': True,
    })
    assert r.status_code == 201
    tx_id = r.json()['id']

    r = client.get('/transactions')
    assert len(r.json()) == 1

    r = client.patch(f'/transactions/{tx_id}', json={'implied_multiple': 9.0})
    assert r.json()['implied_multiple'] == 9.0

    r = client.delete(f'/transactions/{tx_id}')
    assert r.status_code == 204

    r = client.get('/transactions')
    assert r.json() == []


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get('/health')
    assert r.json() == {'status': 'ok'}
