import pytest
from app.domain.enums import BreachStatus, ConcentrationType
from app.domain.models.audit import RiskLimits
from app.domain.rules.concentration_rules import (
    _check_concentration,
    check_issuer_concentration,
    check_sector_concentration,
    check_geography_concentration,
    check_asset_class_concentration,
    run_all_concentration_checks,
)

def test_check_concentration():
    # Test OK status (well under limit)
    res = _check_concentration("EntityA", 5.0, 10.0, 2.0, ConcentrationType.ISSUER)
    assert res.status == BreachStatus.OK
    assert res.excess_pct == 0
    assert res.buffer_pct == 5.0

    # Test Warning status (within warning buffer, e.g. limit=10.0, buffer=2.0 -> warning range is [8.0, 10.0])
    res_warning = _check_concentration("EntityB", 8.5, 10.0, 2.0, ConcentrationType.ISSUER)
    assert res_warning.status == BreachStatus.WARNING
    assert res_warning.excess_pct == 0
    assert res_warning.buffer_pct == 1.5

    # Test Breach status (exceeding limit)
    res_breach = _check_concentration("EntityC", 11.5, 10.0, 2.0, ConcentrationType.ISSUER)
    assert res_breach.status == BreachStatus.BREACH
    assert res_breach.excess_pct == 1.5
    assert res_breach.buffer_pct == 0


def test_check_issuer_concentration():
    positions = [
        {"name": "Apple", "market_value": 40.0},
        {"name": "Microsoft", "market_value": 30.0},
        {"name": "Google", "market_value": 30.0},
    ]
    total_nav = 100.0
    limit = 35.0
    warning_buffer = 5.0

    checks = check_issuer_concentration(positions, total_nav, limit, warning_buffer)
    # Check Apple (40%) -> BREACH
    # Check Microsoft (30%) -> WARNING (since 30% is within [30.0, 35.0])
    # Check Google (30%) -> WARNING
    apple_check = next(c for c in checks if c.entity == "Apple")
    assert apple_check.status == BreachStatus.BREACH
    assert apple_check.nav_pct == 40.0

    microsoft_check = next(c for c in checks if c.entity == "Microsoft")
    assert microsoft_check.status == BreachStatus.WARNING
    assert microsoft_check.nav_pct == 30.0

    # Test empty list or 0 NAV
    assert check_issuer_concentration([], 100.0, limit, warning_buffer) == []
    assert check_issuer_concentration(positions, 0.0, limit, warning_buffer) == []


def test_check_sector_concentration():
    positions = [
        {"sector": "Tech", "market_value": 60.0},
        {"sector": "Finance", "market_value": 40.0},
    ]
    total_nav = 100.0
    limit = 50.0
    warning_buffer = 10.0

    checks = check_sector_concentration(positions, total_nav, limit, warning_buffer)
    tech_check = next(c for c in checks if c.entity == "Tech")
    assert tech_check.status == BreachStatus.BREACH
    
    finance_check = next(c for c in checks if c.entity == "Finance")
    assert finance_check.status == BreachStatus.WARNING # 40% is within [40.0, 50.0]

    # Test empty / 0 NAV
    assert check_sector_concentration([], 100.0, limit, warning_buffer) == []
    assert check_sector_concentration(positions, 0.0, limit, warning_buffer) == []


def test_check_geography_concentration():
    positions = [
        {"country": "US", "market_value": 80.0},
        {"country": "UK", "market_value": 20.0},
    ]
    total_nav = 100.0
    limit = 75.0
    warning_buffer = 10.0

    checks = check_geography_concentration(positions, total_nav, limit, warning_buffer)
    us_check = next(c for c in checks if c.entity == "US")
    assert us_check.status == BreachStatus.BREACH

    uk_check = next(c for c in checks if c.entity == "UK")
    assert uk_check.status == BreachStatus.OK # 20% is below 65%

    assert check_geography_concentration([], 100.0, limit, warning_buffer) == []
    assert check_geography_concentration(positions, 0.0, limit, warning_buffer) == []


def test_check_asset_class_concentration():
    positions = [
        {"asset_class": "Equity", "market_value": 90.0},
        {"asset_class": "Fixed_Income", "market_value": 10.0},
    ]
    total_nav = 100.0
    limit = 80.0
    warning_buffer = 5.0

    checks = check_asset_class_concentration(positions, total_nav, limit, warning_buffer)
    equity_check = next(c for c in checks if c.entity == "Equity")
    assert equity_check.status == BreachStatus.BREACH

    # Test empty / 0 NAV
    assert check_asset_class_concentration([], 100.0, limit, warning_buffer) == []
    assert check_asset_class_concentration(positions, 0.0, limit, warning_buffer) == []


def test_run_all_concentration_checks():
    positions = [
        {"name": "Apple", "sector": "Tech", "country": "US", "asset_class": "Equity", "market_value": 45.0},
        {"name": "Microsoft", "sector": "Tech", "country": "US", "asset_class": "Equity", "market_value": 35.0},
        {"name": "Shell", "sector": "Energy", "country": "UK", "asset_class": "Equity", "market_value": 20.0},
    ]
    limits = RiskLimits(
        single_issuer_max=40.0,
        sector_max=70.0,
        geography_max=90.0,
        asset_class_max=95.0
    )
    warning_buffer = 5.0

    results = run_all_concentration_checks(
        positions=positions,
        total_nav=100.0,
        limits=limits,
        warning_buffer=warning_buffer
    )

    # single_issuer_max = 40.0, buffer = 5.0 (warning threshold = 35.0)
    # Apple (45.0) -> BREACH
    # Microsoft (35.0) -> WARNING
    # Shell (20.0) -> OK
    assert results.total_breaches > 0
    assert results.total_warnings > 0
