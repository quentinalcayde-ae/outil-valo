"""SQLAlchemy models — see PROJECT_V1.md §4 for the full data model spec."""
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ValuationAggregate(StrEnum):
    ARR = "arr"
    REVENUE = "revenue"
    EBITDA = "ebitda"


class RunMode(StrEnum):
    A = "A"  # gèle les ancres (amorçage)
    B = "B"  # re-price median_now seulement (trimestriel)


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(255))
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False)
    valuation_aggregate: Mapped[str] = mapped_column(String(50), nullable=False)
    fund: Mapped[str | None] = mapped_column(String(100))
    # Chiffres clés saisis à la création (contexte découverte LLM + calcul valo)
    aggregate_value: Mapped[float | None] = mapped_column(Float)  # ex. ARR courant (€)
    net_debt: Mapped[float | None] = mapped_column(Float)
    growth_now: Mapped[float | None] = mapped_column(Float)  # croissance actuelle de la cible (décimal)
    description: Mapped[str | None] = mapped_column(Text)  # pitch pour la découverte LLM
    # Dernière découverte LLM mémorisée {comps:[...], transactions:[...]} — évite de re-appeler
    # le LLM à chaque nouveau run tant que le panel convient.
    discovery_json: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    anchors: Mapped[list["TargetAnchor"]] = relationship(back_populates="target")
    runs: Mapped[list["ValuationRun"]] = relationship(back_populates="target")


class TargetAnchor(Base):
    """Ancres historiques figées pour le MODE A (calibration par delta)."""
    __tablename__ = "target_anchors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(nullable=False)
    entry_round: Mapped[str | None] = mapped_column(String(100))
    m_entry_aggregate: Mapped[float] = mapped_column(Float, nullable=False)
    # Calculé sur historique (ou saisi cas ARR) — nullable tant que non ancré
    m_market_entry: Mapped[float | None] = mapped_column(Float)
    # Agrégat sur lequel l'ancre marché est calculée (revenue/ebitda/arr)
    market_anchor_basis: Mapped[str | None] = mapped_column(String(50))
    # computed (yfinance historique) / manual (override ou cas ARR)
    m_market_entry_source: Mapped[str] = mapped_column(String(20), default="computed")
    entry_growth: Mapped[float | None] = mapped_column(Float)         # croissance cible au tour (saisie)
    entry_panel_growth: Mapped[float | None] = mapped_column(Float)   # médiane croissance panel au tour (calculée)

    target: Mapped["Target"] = relationship(back_populates="anchors")


class Comp(Base):
    __tablename__ = "comps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    sector: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    recurring_basis_tag: Mapped[str | None] = mapped_column(String(50))

    snapshots: Mapped[list["CompSnapshot"]] = relationship(back_populates="comp")


class CompSnapshot(Base):
    """Snapshot financier horodaté immuable — ne jamais écraser, toujours insérer."""
    __tablename__ = "comp_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comp_id: Mapped[int] = mapped_column(ForeignKey("comps.id"), nullable=False)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    market_cap: Mapped[float | None] = mapped_column(Float)
    net_debt: Mapped[float | None] = mapped_column(Float)
    cash: Mapped[float | None] = mapped_column(Float)
    revenue_ltm: Mapped[float | None] = mapped_column(Float)
    revenue_growth: Mapped[float | None] = mapped_column(Float)  # croissance YoY (décimal, trailing)
    recurring_value: Mapped[float | None] = mapped_column(Float)
    source_by_field: Mapped[dict | None] = mapped_column(JSON)

    # Computed at insert time
    ev: Mapped[float | None] = mapped_column(Float)
    ev_rev: Mapped[float | None] = mapped_column(Float)
    ev_recurring: Mapped[float | None] = mapped_column(Float)

    comp: Mapped["Comp"] = relationship(back_populates="snapshots")


class ValuationRun(Base):
    __tablename__ = "valuation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), nullable=False)
    run_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    mode: Mapped[str] = mapped_column(String(1), nullable=False)
    aggregate: Mapped[str] = mapped_column(String(50), nullable=False)
    median_now: Mapped[float | None] = mapped_column(Float)
    retention_factor: Mapped[float | None] = mapped_column(Float)  # hérité (non utilisé, ancien mult.)
    other_deltas: Mapped[float | None] = mapped_column(Float)      # ajustements société additifs (tours)
    growth_delta: Mapped[float | None] = mapped_column(Float)      # delta croissance MANUEL (tours)
    winsor_mean: Mapped[float | None] = mapped_column(Float)       # moyenne winsorisée set priced
    flags: Mapped[dict | None] = mapped_column(JSON)               # alertes de run (liste)
    m_final: Mapped[float | None] = mapped_column(Float)
    result_ev: Mapped[float | None] = mapped_column(Float)
    result_equity: Mapped[float | None] = mapped_column(Float)
    excel_path: Mapped[str | None] = mapped_column(String(500))

    target: Mapped["Target"] = relationship(back_populates="runs")
    run_comps: Mapped[list["RunComp"]] = relationship(back_populates="run")


class RunComp(Base):
    """Panel d'un run — les exclus sont conservés hors médiane."""
    __tablename__ = "run_comps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("valuation_runs.id"), nullable=False)
    # Identité du comp fixée au panel (avant toute recherche financière)
    comp_id: Mapped[int] = mapped_column(ForeignKey("comps.id"), nullable=False)
    # Snapshot gelé effectivement utilisé — rempli à l'execute (recherche financière)
    comp_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("comp_snapshots.id"))
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    relevance_note: Mapped[str | None] = mapped_column(Text)
    # Classification panel (Ordre 1) : tier 1/2/3, statut priced/proxy/outlier/distressed
    tier: Mapped[int | None] = mapped_column(Integer)
    statut: Mapped[str] = mapped_column(String(20), default="priced")
    pct_ca_comparable: Mapped[float | None] = mapped_column(Float)  # part du CA sur l'activité comparable

    run: Mapped["ValuationRun"] = relationship(back_populates="run_comps")
    comp: Mapped["Comp"] = relationship()
    comp_snapshot: Mapped["CompSnapshot"] = relationship()


class Transaction(Base):
    """Transactions M&A — cross-check qualitatif, jamais dans la médiane."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Optionnel : rattache la transaction à une cible (proposition LLM contextualisée)
    target_id: Mapped[int | None] = mapped_column(ForeignKey("targets.id"))
    target_company: Mapped[str] = mapped_column(String(255), nullable=False)
    acquirer: Mapped[str | None] = mapped_column(String(255))
    tx_date: Mapped[date | None] = mapped_column()
    sector: Mapped[str | None] = mapped_column(String(255))
    price_disclosed: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[float | None] = mapped_column(Float)
    implied_multiple: Mapped[float | None] = mapped_column(Float)
    source_doc_url: Mapped[str | None] = mapped_column(String(1000))
    # llm (proposée, chiffres à vérifier) / manual (saisie humaine)
    origin: Mapped[str] = mapped_column(String(20), default="manual")
    # proposed (LLM, non validée) / validated (chiffres confirmés par l'humain)
    status: Mapped[str] = mapped_column(String(20), default="validated")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
