"""Tests de la méthode — base marché + ajustement de croissance (β) + deltas additifs."""
import pytest

from valo.method.valuation import ValuationInput, compute_multiple, run_valuation


def test_compute_multiple_basic():
    assert compute_multiple(ev=100, aggregate=10) == pytest.approx(10.0)


def test_compute_multiple_zero_aggregate():
    assert compute_multiple(ev=100, aggregate=0) is None


def test_compute_multiple_none():
    assert compute_multiple(ev=None, aggregate=10) is None


# ── Base marché (sans croissance) ─────────────────────────────────────────────

def test_delta_base_no_growth():
    # median 11, drift 1.1, base = 8 × 1.1 = 8.8 ; pas de croissance → m_final 8.8
    inp = ValuationInput(mode="A", comp_multiples=[9.0, 11.0, 12.0], comp_growths=[None, None, None],
                         m_entry_aggregate=8.0, m_market_entry=10.0)
    r = run_valuation(inp)
    assert r.calibrated is True
    assert r.median_now == pytest.approx(11.0)
    assert r.drift_ratio == pytest.approx(1.1)
    assert r.beta is None
    assert r.growth_delta == 0.0
    assert r.m_final == pytest.approx(8.8)


def test_direct_base_no_growth():
    inp = ValuationInput(mode="A", comp_multiples=[10.0, 12.0, 14.0], comp_growths=[None, None, None])
    r = run_valuation(inp)
    assert r.calibrated is False
    assert r.median_now == pytest.approx(12.0)
    assert r.m_final == pytest.approx(12.0)


def test_other_deltas_additive():
    inp = ValuationInput(mode="A", comp_multiples=[10.0], comp_growths=[None],
                         m_entry_aggregate=8.0, m_market_entry=10.0, other_deltas=1.5)
    r = run_valuation(inp)
    # base = 8 × (10/10) = 8 ; + autres_deltas 1.5 → 9.5
    assert r.m_final == pytest.approx(9.5)


def test_empty_panel_raises():
    with pytest.raises(ValueError, match="Panel vide"):
        run_valuation(ValuationInput(mode="B", comp_multiples=[], comp_growths=[]))


# ── Ajustement de croissance (β) ──────────────────────────────────────────────

def test_beta_computed_and_direct_growth_premium():
    # Panel : multiple croît avec la croissance → β ≈ 10 (chaque +10pts = +1x)
    # comps: growth 0.10→8x, 0.20→9x, 0.30→10x, 0.40→11x  (pente = 10 x/‰... 1x par 10pts)
    mults = [8.0, 9.0, 10.0, 11.0]
    grows = [0.10, 0.20, 0.30, 0.40]
    # cible à 0.50 de croissance, médiane panel 0.25 → gap +0.25 mais clampé à la fourchette
    inp = ValuationInput(mode="A", comp_multiples=mults, comp_growths=grows, target_growth_now=0.50)
    r = run_valuation(inp)
    assert r.beta == pytest.approx(10.0, rel=0.05)
    assert r.median_now == pytest.approx(9.5)  # médiane [8,9,10,11]
    # gap = 0.50 - 0.25 = 0.25 ; clampé à hi = max(0.40) - médiane(0.25) = 0.15
    assert r.growth_gap == pytest.approx(0.15, abs=1e-9)
    # m_final = 9.5 + 10 × 0.15 = 11.0
    assert r.m_final == pytest.approx(11.0, rel=0.02)


def test_growth_convexity_clamp_low():
    mults = [8.0, 9.0, 10.0, 11.0]
    grows = [0.10, 0.20, 0.30, 0.40]
    # cible en décroissance -0.20, bien en-dessous du panel → clampé à lo
    inp = ValuationInput(mode="A", comp_multiples=mults, comp_growths=grows, target_growth_now=-0.20)
    r = run_valuation(inp)
    lo = 0.10 - 0.25  # min - médiane = -0.15
    assert r.growth_gap == pytest.approx(lo, abs=1e-9)


def test_delta_mode_growth_since_round():
    # β ≈ 10. Depuis le tour : cible 0.45→0.50 (+0.05), panel 0.35→médiane_now 0.25 (−0.10)
    # sur-perf = +0.05 - (-0.10) = +0.15 (dans la fourchette) → Δ = 10 × 0.15 = 1.5
    mults = [8.0, 9.0, 10.0, 11.0]
    grows = [0.10, 0.20, 0.30, 0.40]   # médiane now = 0.25
    inp = ValuationInput(
        mode="A", comp_multiples=mults, comp_growths=grows,
        m_entry_aggregate=8.0, m_market_entry=10.0,
        target_growth_now=0.50, target_growth_entry=0.45, entry_panel_growth=0.35,
    )
    r = run_valuation(inp)
    # base = 8 × (9.5/10) = 7.6 ; gap = 0.15 clampé (hi = 0.40-0.25 = 0.15) ; Δ = 1.5
    assert r.growth_gap == pytest.approx(0.15, abs=1e-9)
    assert r.m_final == pytest.approx(7.6 + 1.5, rel=0.02)


def test_beta_omitted_few_comps():
    # < 3 comps avec croissance → pas de β → pas de terme de croissance
    inp = ValuationInput(mode="A", comp_multiples=[10.0, 12.0], comp_growths=[0.2, 0.3],
                         target_growth_now=0.5)
    r = run_valuation(inp)
    assert r.beta is None
    assert r.growth_delta == 0.0
    assert r.m_final == pytest.approx(11.0)  # médiane seule
