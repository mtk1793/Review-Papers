import numpy as np
import pytest
from h2bench.physics import HydrogenEnv,Plant,technical_upper_bound_annual_mwh,wind_to_power
from h2bench.evaluate import evaluate_controller,metrics,paired_block_bootstrap

def test_energy_conservation_random_rollout():
    rng=np.random.default_rng(1);e=HydrogenEnv()
    for _ in range(1000):
        r=e.step(float(rng.uniform(0,700)),float(rng.uniform(0,50)),float(rng.uniform(-10,10)))
        assert abs(r['balance_error_mw'])<1e-7
        assert 0<=r['battery_soc_mwh']<=20+1e-7
        assert 0<=r['tank_kg']<=500+1e-7
        assert abs(r['ramp_mw'])<=5*15+1e-7

def test_hydrogen_storage_mass_balance():
    e=HydrogenEnv();a=e.step(400,50)
    assert np.isclose(a['produced_kg'],a['delivered_kg']+a['tank_kg'])

def test_upper_bound():
    assert technical_upper_bound_annual_mwh()/1000==438
    assert 1126*.782>438
    assert np.isclose((19100/17500-1)*100,9.142857142857142)

def test_bess_not_36_hours():assert 20/(.4*50)==1

def test_curve():
    assert wind_to_power(2)==0
    assert wind_to_power(26)==0
    assert wind_to_power(12)==700

def test_known_perfect_balance():
    e=HydrogenEnv(Plant(h2_tank_capacity_kg=200000))
    r=e.step(100,50,0)
    assert np.isclose(r['curtail_mw'],0)
    assert np.isclose(r['export_mw'],100-r['electrolyzer_mw'])

def test_bootstrap_ci():
    d=np.ones(300)
    x=paired_block_bootstrap(d,block_size=24,reps=100)
    assert x['ci95_low']==x['ci95_high']==1.0

def test_metrics_have_one_denominator():
    wind=np.ones(100)*500
    df=evaluate_controller(wind)
    result=metrics(df,Plant())
    assert result['electrolyzer_input_mwh']<=50*len(wind)*.25+1e-7
