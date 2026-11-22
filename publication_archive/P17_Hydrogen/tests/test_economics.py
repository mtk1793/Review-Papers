import pytest
from h2bench.economics import npv_from_annual_cashflows

def test_npv_discounting():
    x=npv_from_annual_cashflows(100,[110,110],.10)
    assert x['npv_usd']==pytest.approx(-100+100+110/1.21)

def test_replacement_occurs_at_threshold_only():
    x=npv_from_annual_cashflows(0,[10,10,10],0,stack_replacement_usd=100,annual_eq_hours=[5,5,5],eq_life_hours=10)
    assert x['replacement_count']==1
    assert x['npv_usd']==-70
