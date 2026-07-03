"""Tests méthode — base marché + delta croissance AUTO (médiane du ratio) + autres deltas manuels."""
import pytest

from valo.method.valuation import MIN_PRICED, ValuationInput, compute_multiple, run_valuation


def test_compute_multiple_basic():
    assert compute_multiple(ev=100, aggregate=10) == pytest.approx(10.0)


def test_compute_multiple_zero_aggregate():
    assert compute_multiple(ev=100, aggregate=0) is None


def _none(n):
    return [None] * n


def test_delta_base_no_growth():
    inp = ValuationInput(mode="A", comp_multiples=[9.0, 11.0, 12.0], comp_growths=_none(3),
                         m_entry_aggregate=8.0, m_market_entry=10.0)
    r = run_valuation(inp)
    assert r.calibrated is True
    assert r.drift_ratio == pytest.approx(1.1)
    assert r.base == pytest.approx(8.8)
    assert r.growth_delta == 0.0
    assert r.m_final == pytest.approx(8.8)


def test_direct_base_no_growth():
    inp = ValuationInput(mode="A", comp_multiples=[10.0, 12.0, 14.0], comp_growths=_none(3))
    r = run_valuation(inp)
    assert r.calibrated is False
    assert r.m_final == pytest.approx(12.0)


def test_other_deltas_additifs():
    inp = ValuationInput(mode="A", comp_multiples=[10.0], comp_growths=_none(1),
                         m_entry_aggregate=8.0, m_market_entry=10.0, other_deltas=1.5)
    r = run_valuation(inp)
    assert r.m_final == pytest.approx(9.5)  # base 8 + 1.5


def test_floor_at_zero():
    inp = ValuationInput(mode="A", comp_multiples=[10.0], comp_growths=_none(1), other_deltas=-20.0)
    r = run_valuation(inp)
    assert r.m_final == 0.0
    assert any("planch" in f for f in r.flags)


def test_empty_panel_raises():
    with pytest.raises(ValueError, match="Panel vide"):
        run_valuation(ValuationInput(mode="B", comp_multiples=[], comp_growths=[]))


def test_growth_auto_price_per_point():
    # multiple croît avec la croissance ; prix/point = médiane(EV/Rev ÷ croissance)
    mults = [8.0, 9.0, 10.0, 11.0]
    grows = [0.10, 0.20, 0.30, 0.40]
    inp = ValuationInput(mode="A", comp_multiples=mults, comp_growths=grows, target_growth_now=0.50)
    r = run_valuation(inp)
    # ratios = [80, 45, 33.33, 27.5] → médiane = 39.16 ; médiane croissance = 0.25
    assert r.price_per_pt_growth == pytest.approx(39.166, rel=1e-3)
    # gap clampé à max-median = 0.40-0.25 = 0.15
    assert r.growth_gap == pytest.approx(0.15)
    assert r.growth_delta == pytest.approx(39.166 * 0.15, rel=1e-3)
    assert r.median_now == pytest.approx(9.5)


def test_growth_auto_omitted_few_comps():
    inp = ValuationInput(mode="A", comp_multiples=[10.0, 12.0], comp_growths=[0.2, 0.3],
                         target_growth_now=0.5)
    r = run_valuation(inp)
    assert r.growth_delta == 0.0
    assert any("delta_croissance_omis" in f for f in r.flags)


def test_growth_auto_omitted_no_target_growth():
    mults = [8.0, 9.0, 10.0, 11.0]
    grows = [0.10, 0.20, 0.30, 0.40]
    r = run_valuation(ValuationInput(mode="A", comp_multiples=mults, comp_growths=grows))
    assert r.growth_delta == 0.0
    assert any("croissance cible non saisie" in f for f in r.flags)


def test_flag_priced_faible():
    inp = ValuationInput(mode="A", comp_multiples=[10.0] * 5, comp_growths=_none(5))
    r = run_valuation(inp)
    assert any("panel_priced_faible" in f for f in r.flags)


def test_no_flag_priced_ok():
    inp = ValuationInput(mode="A", comp_multiples=[10.0] * MIN_PRICED, comp_growths=_none(MIN_PRICED))
    r = run_valuation(inp)
    assert not any("panel_priced_faible" in f for f in r.flags)
