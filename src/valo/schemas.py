"""Pydantic schemas — contrats REST. Voir PROJECT_V1.md §7."""
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Targets ──────────────────────────────────────────────────────────────────

class TargetCreate(BaseModel):
    name: str
    sector: str | None = None
    is_recurring: bool
    valuation_aggregate: str  # arr / revenue / ebitda / …
    fund: str | None = None
    notes: str | None = None


class AnchorCreate(BaseModel):
    entry_date: date
    entry_round: str | None = None
    m_entry_aggregate: float
    m_market_entry: float


class TargetOut(BaseModel):
    id: int
    name: str
    sector: str | None
    is_recurring: bool
    valuation_aggregate: str
    fund: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnchorOut(BaseModel):
    id: int
    target_id: int
    entry_date: date
    entry_round: str | None
    m_entry_aggregate: float
    m_market_entry: float

    model_config = {"from_attributes": True}


# ── Comps ─────────────────────────────────────────────────────────────────────

class CompCreate(BaseModel):
    name: str
    ticker: str
    sector: str | None = None
    currency: str = "USD"
    is_recurring: bool = True
    recurring_basis_tag: str | None = None


class CompOut(BaseModel):
    id: int
    name: str
    ticker: str
    sector: str | None
    currency: str
    is_recurring: bool
    recurring_basis_tag: str | None

    model_config = {"from_attributes": True}


class SnapshotOut(BaseModel):
    id: int
    comp_id: int
    snapshot_date: datetime
    market_cap: float | None
    net_debt: float | None
    cash: float | None
    revenue_ltm: float | None
    recurring_value: float | None
    ev: float | None
    ev_rev: float | None
    ev_recurring: float | None
    source_by_field: dict[str, Any] | None

    model_config = {"from_attributes": True}


# ── Panel ─────────────────────────────────────────────────────────────────────

class PanelCompIn(BaseModel):
    ticker: str
    relevance_note: str | None = None


class PanelCreate(BaseModel):
    """Crée un run et associe le panel de comps soumis par l'utilisateur."""
    comps: list[PanelCompIn] = Field(min_length=1)
    mode: str = Field(default="A", pattern="^[AB]$")
    aggregate: str  # arr / revenue / ebitda / …
    retention_factor: float = 1.0
    target_aggregate_value: float = Field(gt=0, description="Valeur agrégat cible (€)")
    anchor: AnchorCreate | None = None  # si pas encore d'ancre sur la cible


class RunCompPatch(BaseModel):
    comp_snapshot_id: int
    included: bool
    exclusion_reason: str | None = None
    relevance_note: str | None = None


class RunCompsPatch(BaseModel):
    comps: list[RunCompPatch]


# ── Runs ──────────────────────────────────────────────────────────────────────

class RunCompOut(BaseModel):
    id: int
    comp_snapshot_id: int
    included: bool
    exclusion_reason: str | None
    relevance_note: str | None
    snapshot: SnapshotOut
    comp: CompOut

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: int
    target_id: int
    run_date: datetime
    mode: str
    aggregate: str
    median_now: float | None
    retention_factor: float | None
    m_final: float | None
    result_ev: float | None
    result_equity: float | None
    excel_path: str | None
    run_comps: list[RunCompOut] = []

    model_config = {"from_attributes": True}


class RunExecuteIn(BaseModel):
    target_aggregate_value: float = Field(gt=0)


# ── Transactions M&A ──────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    target_company: str
    acquirer: str | None = None
    tx_date: date | None = None
    sector: str | None = None
    price_disclosed: bool = False
    price: float | None = None
    implied_multiple: float | None = None
    source_doc_url: str | None = None
    notes: str | None = None


class TransactionUpdate(BaseModel):
    target_company: str | None = None
    acquirer: str | None = None
    tx_date: date | None = None
    sector: str | None = None
    price_disclosed: bool | None = None
    price: float | None = None
    implied_multiple: float | None = None
    source_doc_url: str | None = None
    notes: str | None = None


class TransactionOut(BaseModel):
    id: int
    target_company: str
    acquirer: str | None
    tx_date: date | None
    sector: str | None
    price_disclosed: bool
    price: float | None
    implied_multiple: float | None
    source_doc_url: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
