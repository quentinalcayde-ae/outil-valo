"""Tests P2 — méthode de valo agrégat-agnostique."""
import pytest

from valo.method.valuation import ValuationInput, compute_multiple, run_valuation


def test_compute_multiple_basic():
    assert compute_multiple(ev=100, aggregate=10) == pytest.approx(10.0)


def test_compute_multiple_zero_aggregate():
    assert compute_multiple(ev=100, aggregate=0) is None


def test_compute_multiple_none():
    assert compute_multiple(ev=None, aggregate=10) is None


def test_run_valuation_mode_a():
    inp = ValuationInput(
        mode="A",
        m_entry_aggregate=8.0,
        m_market_entry=10.0,
        comp_multiples=[9.0, 11.0, 12.0],
        retention_factor=1.0,
    )
    result = run_valuation(inp)
    # median_now = 11.0 ; drift = 11/10 = 1.1 ; m_final = 8 * 1.1 * 1 = 8.8
    assert result.median_now == pytest.approx(11.0)
    assert result.drift_ratio == pytest.approx(1.1)
    assert result.m_final == pytest.approx(8.8)


def test_run_valuation_empty_panel():
    inp = ValuationInput(
        mode="B",
        m_entry_aggregate=8.0,
        m_market_entry=10.0,
        comp_multiples=[],
    )
    with pytest.raises(ValueError, match="Panel vide"):
        run_valuation(inp)


def test_run_valuation_direct_mode_no_anchor():
    # Pas d'ancre → M_final = médiane × rétention
    inp = ValuationInput(mode="A", comp_multiples=[10.0, 12.0, 14.0], retention_factor=1.0)
    result = run_valuation(inp)
    assert result.calibrated is False
    assert result.drift_ratio is None
    assert result.median_now == pytest.approx(12.0)
    assert result.m_final == pytest.approx(12.0)


def test_run_valuation_direct_mode_with_retention():
    inp = ValuationInput(mode="A", comp_multiples=[10.0], retention_factor=1.1)
    result = run_valuation(inp)
    assert result.m_final == pytest.approx(11.0)  # 10 × 1.1


def test_run_valuation_with_retention():
    inp = ValuationInput(
        mode="A",
        m_entry_aggregate=8.0,
        m_market_entry=10.0,
        comp_multiples=[10.0],
        retention_factor=1.2,
    )
    result = run_valuation(inp)
    # m_final = 8 * 1.0 * 1.2 = 9.6
    assert result.m_final == pytest.approx(9.6)
