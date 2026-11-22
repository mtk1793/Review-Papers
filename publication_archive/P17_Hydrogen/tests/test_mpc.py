import numpy as np
from h2bench.physics import HydrogenEnv
from h2bench.mpc import solve_lp_mpc,evaluate_lp_mpc

def test_mpc_solver_is_feasible():
    e=HydrogenEnv()
    a=solve_lp_mpc([200,350,400,180,0],e,horizon=5)
    assert 0<=a['desired_electrolyzer_mw']<=50
    assert -10<=a['battery_request_mw']<=10

def test_mpc_preserves_energy_in_actual_dispatch():
    a=evaluate_lp_mpc(np.array([300.,400.,480.,0.,90.,130.]),horizon=4)
    assert abs(a.balance_error_mw).max()<1e-7
    assert 0<=a.battery_soc_mwh.min() and a.battery_soc_mwh.max()<=20
