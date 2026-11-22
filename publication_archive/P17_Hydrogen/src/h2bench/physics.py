"""Energy-conserving 15-min electrolyzer/BESS/grid surrogate.

This is a transparent engineering surrogate, not a validated PEM electrochemical model,
validated transmission network, dispatchable NS power market, or digital twin.
All monetary inputs, ramp wear and cold-start stress require sensitivity/calibration.
"""
from dataclasses import dataclass
import math

@dataclass
class Plant:
    wind_capacity_mw: float = 700.0
    electrolyzer_capacity_mw: float = 50.0
    electrolyzer_min_load_fraction: float = .10
    ramp_limit_mw_per_min: float = 5.0
    export_limit_mw: float = 300.0
    bess_energy_mwh: float = 20.0
    bess_power_mw: float = 10.0
    roundtrip_efficiency: float = .90
    h2_tank_capacity_kg: float = 500.0
    h2_specific_energy_mwh_per_kg: float = .052
    hydrogen_demand_kg_per_day: float = 800.0
    cold_start_equivalent_hours: float = 0.0
    ramp_wear_eq_hours_per_mw2: float = .0002
    thermal_wear_eq_hours_per_mw2: float = 0.0
    stack_design_life_eq_hours: float = 60000.0
    stack_replacement_usd: float = 15000000.0

@dataclass
class Market:
    h2_sale_price_usd_per_kg: float = 5.0
    energy_export_price_usd_per_mwh: float = 42.0
    energy_import_price_usd_per_mwh: float = 90.0
    h2_unmet_demand_penalty_usd_per_kg: float = .5

class HydrogenEnv:
    """Steady-state dispatch with hard projection; power quantities MW, energy MWh.

    Wind available first serves electrolyzer, then BESS charging, then exports up
    to the limit; remainder is curtailed. BESS can discharge to support
    electrolyzer only, not sell and produce in same step; no grid imports by
    default, avoiding unsupported electricity market access assumptions.
    Delivery removes hydrogen from store every timestep; production above
    storage/sale handling capacity is curtailed at electrolysis level by projected
    power. Carbon credits and replacement charges are not presumed revenue.
    """
    def __init__(self, plant=None, market=None, dt_hours=.25):
        self.p = plant or Plant(); self.m = market or Market(); self.dt = float(dt_hours)
        assert self.dt > 0
        self.reset()
    def reset(self, soc_fraction=.5, tank_kg=0.0):
        assert 0 <= soc_fraction <= 1
        self.soc_mwh = self.p.bess_energy_mwh * soc_fraction
        self.h2_kg = float(tank_kg)
        self.previous_mw = 0.0
        self.eq_aging_hours = 0.0
        self.num_starts = 0
        self.t = 0
        return self.state()
    def state(self):
        return {'soc_mwh':self.soc_mwh,'tank_kg':self.h2_kg,'electrolyzer_mw':self.previous_mw,'aging_equivalent_h':self.eq_aging_hours}
    def step(self, wind_mw, desired_electrolyzer_mw, battery_request_mw=0.0, market=None):
        p=self.p; m=market or self.m; dt=self.dt
        assert math.isfinite(wind_mw) and wind_mw >=0
        # positive battery request charges, negative request discharges.
        w=min(float(wind_mw),p.wind_capacity_mw)
        desired=max(0.,min(float(desired_electrolyzer_mw),p.electrolyzer_capacity_mw))
        delta=p.ramp_limit_mw_per_min*dt*60
        e=max(self.previous_mw-delta,min(self.previous_mw+delta,desired))
        if e < p.electrolyzer_capacity_mw*p.electrolyzer_min_load_fraction:
            e=0.
        # Hydrogen tank volume is a real operational limit, with continuous offtake
        # applied first so a small tank can serve demand incrementally.
        delivery_demand=p.hydrogen_demand_kg_per_day*dt/24
        delivered=min(self.h2_kg,delivery_demand)
        self.h2_kg -= delivered
        tank_room=p.h2_tank_capacity_kg-self.h2_kg
        # actual electrolyzer can supply remaining demand (direct offtake)
        e_h2_cap=(tank_room+delivery_demand-delivered)*p.h2_specific_energy_mwh_per_kg/dt
        e=min(e,e_h2_cap)
        if e < p.electrolyzer_capacity_mw*p.electrolyzer_min_load_fraction:
            e=0.
        # only physically available wind+BESS serves electrolyzer, with
        # requested discharge and SOC/power restrictions.
        eta=math.sqrt(p.roundtrip_efficiency)
        battery_discharge_cap=min(p.bess_power_mw,self.soc_mwh*eta/dt)
        deficit=max(0.,e-w)
        discharge=min(deficit,battery_discharge_cap,max(0.,-battery_request_mw))
        e=min(e,w+discharge)
        if e < p.electrolyzer_capacity_mw*p.electrolyzer_min_load_fraction:
            e=0.; discharge=0.
        self.soc_mwh-=discharge*dt/eta
        available=max(0.,w-e)
        charge_cap=min(p.bess_power_mw,(p.bess_energy_mwh-self.soc_mwh)/(dt*eta))
        charge=min(available,charge_cap,max(0.,battery_request_mw))
        self.soc_mwh+=charge*dt*eta
        exports=min(p.export_limit_mw,max(0.,available-charge))
        curtailed=max(0.,available-charge-exports)
        produced=e*dt/p.h2_specific_energy_mwh_per_kg
        shipped=min(produced,delivery_demand-delivered)
        self.h2_kg+=produced-shipped
        delivered+=shipped
        shortfall=max(0.,delivery_demand-delivered)
        started=int(self.previous_mw==0 and e>0)
        self.num_starts+=started
        wear=dt*(e/p.electrolyzer_capacity_mw if p.electrolyzer_capacity_mw else 0.)
        wear+=p.cold_start_equivalent_hours*started
        wear+=p.ramp_wear_eq_hours_per_mw2*(e-self.previous_mw)**2
        # thermal stress only if calibrated model has parameter >0
        wear+=p.thermal_wear_eq_hours_per_mw2*(e-self.previous_mw)**2
        self.eq_aging_hours+=wear
        depreciation=wear/p.stack_design_life_eq_hours*p.stack_replacement_usd
        cash=delivered*m.h2_sale_price_usd_per_kg + exports*dt*m.energy_export_price_usd_per_mwh
        cash-=shortfall*m.h2_unmet_demand_penalty_usd_per_kg
        net=cash-depreciation
        prev=self.previous_mw
        self.previous_mw=e
        self.t+=1
        record={'wind_mw':w,'electrolyzer_mw':e,'charge_mw':charge,
                'discharge_mw':discharge,'export_mw':exports,'curtail_mw':curtailed,
                'produced_kg':produced,'delivered_kg':delivered,'unmet_kg':shortfall,
                'battery_soc_mwh':self.soc_mwh,'tank_kg':self.h2_kg,'wear_eq_hours':wear,
                'cum_aging_hours':self.eq_aging_hours,'started':started,
                'cash_usd':cash,'wear_charge_usd':depreciation,'reward_usd':net,
                'balance_error_mw':w+discharge-e-charge-exports-curtailed,
                'ramp_mw':e-prev}
        assert abs(record['balance_error_mw'])<1e-7,record
        assert -1e-7<=self.soc_mwh<=p.bess_energy_mwh+1e-7
        assert -1e-7<=self.h2_kg<=p.h2_tank_capacity_kg+1e-7
        assert 0<=e<=p.electrolyzer_capacity_mw+1e-7
        return record

def wind_to_power(v_ms, nameplate_mw=700., cut_in=3., rated=12., cut_out=25.):
    """Explicit *illustrative* IEC-like power curve, not plant-specific calibrated CFD.
    Actual turbine manufacturer curve should replace this before submission.
    """
    v=float(v_ms)
    if v<cut_in or v>=cut_out:return 0.
    if v>=rated:return nameplate_mw
    return nameplate_mw*(v**3-cut_in**3)/(rated**3-cut_in**3)

def technical_upper_bound_annual_mwh(electrolyzer_mw=50., hours_per_year=8760.):
    return electrolyzer_mw*hours_per_year
