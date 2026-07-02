"""Pydantic schemas — contrats REST. Voir PROJECT_V1.md §7."""
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Targets ──────────────────────────────────────────────────────────────────

class TargetCreate(BaseModel):
    name: str
    sector: str | None = None
    is_recurring: bool
    valuation_aggregate: str
    fund: str | None = None
    aggregate_value: float | None = None  # chiffre clé : agrégat courant (€)
    net_debt: float | None = None
    growth_now: float | None = None        # croissance actuelle de la cible (décimal)
    description: str | None = None         # pitch pour la découverte LLM
    notes: str | None = None


class TargetOut(BaseModel):
    id: int
    name: str
    sector: str | None
    is_recurring: bool
    valuation_aggregate: str
    fund: str | None
    aggregate_value: float | None
    net_debt: float | None
    growth_now: float | None
    description: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnchorOut(BaseModel):
    id: int
    target_id: int
    entry_date: date
    entry_round: str | None
    m_entry_aggregate: float
    m_market_entry: float | None
    market_anchor_basis: str | None
    m_market_entry_source: str
    entry_growth: float | None
    entry_panel_growth: float | None

    model_config = {"from_attributes": True}


# ── Découverte (LLM) ──────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    extra_tickers: list[str] = []
    n_comps: int = 8
    n_transactions: int = 5


class CompSuggestionOut(BaseModel):
    name: str
    ticker: str
    rationale: str
    sector: str | None = None
    confidence: str = "medium"


class TransactionSuggestionOut(BaseModel):
    target_company: str
    acquirer: str | None
    tx_date: date | None
    rationale: str
    source_doc_url: str | None = None
    implied_multiple: float | None = None
    sector: str | None = None


class SuggestResponse(BaseModel):
    comps: list[CompSuggestionOut]
    transactions: list[TransactionSuggestionOut]


# ── Comps / snapshots ─────────────────────────────────────────────────────────

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


# ── Panel / run ───────────────────────────────────────────────────────────────

class PanelCompIn(BaseModel):
    ticker: str
    name: str | None = None
    relevance_note: str | None = None


class AnchorEntryIn(BaseModel):
    """Ancres du tour saisies au panel — m_market_entry sera calculé à l'étape /anchor."""
    entry_date: date
    entry_round: str | None = None
    m_entry_aggregate: float
    entry_growth: float | None = None  # croissance de la cible au tour (décimal)


class PanelCreate(BaseModel):
    comps: list[PanelCompIn] = Field(min_length=1)
    mode: str = Field(default="A", pattern="^[AB]$")
    aggregate: str
    other_deltas: float = 0.0  # ajustements société additifs (marge/NRR/taille), en tours
    anchor: AnchorEntryIn | None = None  # None → valorisation directe (sans ancre)


class RunCompPatch(BaseModel):
    run_comp_id: int
    included: bool
    exclusion_reason: str | None = None
    relevance_note: str | None = None


class RunCompsPatch(BaseModel):
    comps: list[RunCompPatch]


class AnchorComputeIn(BaseModel):
    """Calcule ou fixe m_market_entry. Si manual_value fourni → override (cas ARR / correction)."""
    manual_value: float | None = None
    basis: str | None = None  # revenue par défaut (auto) ; 'arr' si multiple manuel d'ARR


class AnchorCompDetailOut(BaseModel):
    ticker: str
    ev: float | None
    revenue_ltm: float | None
    multiple: float | None
    available: bool
    note: str


class AnchorProposalOut(BaseModel):
    basis: str
    entry_date: date
    m_market_entry: float | None
    n_available: int
    details: list[AnchorCompDetailOut]
    source: str  # computed / manual


class RunExecuteIn(BaseModel):
    target_aggregate_value: float | None = None  # défaut : target.aggregate_value


class RunCompOut(BaseModel):
    id: int
    comp_id: int
    comp_snapshot_id: int | None
    included: bool
    exclusion_reason: str | None
    relevance_note: str | None
    comp: CompOut
    snapshot: SnapshotOut | None = None

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


# ── Transactions M&A ──────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    target_id: int | None = None
    target_company: str
    acquirer: str | None = None
    tx_date: date | None = None
    sector: str | None = None
    price_disclosed: bool = False
    price: float | None = None
    implied_multiple: float | None = None
    source_doc_url: str | None = None
    origin: str = "manual"
    status: str = "validated"
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
    status: str | None = None
    notes: str | None = None


class TransactionOut(BaseModel):
    id: int
    target_id: int | None
    target_company: str
    acquirer: str | None
    tx_date: date | None
    sector: str | None
    price_disclosed: bool
    price: float | None
    implied_multiple: float | None
    source_doc_url: str | None
    origin: str
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
