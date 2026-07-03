"""Tests méthode — base marché (médiane dérive) + deltas société manuels + flags. β supprimé (Option A)."""
import pytest

from valo.method.valuation import MIN_PRICED, ValuationInput, compute_multiple, run_valuation


def test_compute_multiple_basic():
    assert compute_multiple(ev=100, aggregate=10) == pytest.approx(10.0)


def test_compute_multiple_zero_aggregate():
    assert compute_multiple(ev=100, aggregate=0) is None


def test_compute_multiple_none():
    assert compute_multiple(ev=None, aggregate=10) is None


def _mults(n, val=10.0):
    return [val] * n


def test_delta_base_no_deltas():
    inp = ValuationInput(mode="A", comp_multiples=[9.0, 11.0, 12.0],
                         m_entry_aggregate=8.0, m_market_entry=10.0)
    r = run_valuation(inp)
    assert r.calibrated is True
    assert r.median_now == pytest.approx(11.0)
    assert r.drift_ratio == pytest.approx(1.1)
    assert r.base == pytest.approx(8.8)
    assert r.m_final == pytest.approx(8.8)


def test_direct_base_no_deltas():
    inp = ValuationInput(mode="A", comp_multiples=[10.0, 12.0, 14.0])
    r = run_valuation(inp)
    assert r.calibrated is False
    assert r.median_now == pytest.approx(12.0)
    assert r.m_final == pytest.approx(12.0)


def test_deltas_additifs():
    inp = ValuationInput(mode="A", comp_multiples=[10.0], m_entry_aggregate=8.0, m_market_entry=10.0,
                         growth_delta=1.0, other_deltas=0.5)
    r = run_valuation(inp)
    # base = 8 × 1.0 = 8 ; + 1.0 + 0.5 = 9.5
    assert r.m_final == pytest.approx(9.5)
    assert r.deltas_total == pytest.approx(1.5)


def test_floor_at_zero():
    inp = ValuationInput(mode="A", comp_multiples=[10.0], other_deltas=-20.0)
    r = run_valuation(inp)
    assert r.m_final == 0.0
    assert any("planch" in f for f in r.flags)


def test_empty_panel_raises():
    with pytest.raises(ValueError, match="Panel vide"):
        run_valuation(ValuationInput(mode="B", comp_multiples=[]))


def test_flag_priced_faible():
    inp = ValuationInput(mode="A", comp_multiples=_mults(5))  # < 8
    r = run_valuation(inp)
    assert r.n_priced == 5
    assert any("panel_priced_faible" in f for f in r.flags)


def test_no_flag_when_enough_priced():
    inp = ValuationInput(mode="A", comp_multiples=_mults(MIN_PRICED))
    r = run_valuation(inp)
    assert not any("panel_priced_faible" in f for f in r.flags)


def test_flag_deltas_eleves():
    # base 10, deltas +5 (>40%) → flag
    inp = ValuationInput(mode="A", comp_multiples=_mults(9, 10.0), other_deltas=5.0)
    r = run_valuation(inp)
    assert any("deltas_societe_eleves" in f for f in r.flags)


def test_winsor_mean_present():
    inp = ValuationInput(mode="A", comp_multiples=[5.0, 10.0, 10.0, 10.0, 50.0])
    r = run_valuation(inp)
    # la moyenne winsorisée écrête le 50 → proche de 10, bien < moyenne brute (17)
    assert r.winsor_mean < 17.0
