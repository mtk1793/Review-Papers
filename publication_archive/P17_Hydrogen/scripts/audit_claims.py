#!/usr/bin/env python3
"""Deterministic arithmetic audit of numerical contradictions in rejected paper."""
import json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'results'/'hard_feasibility_audit.json'
annual_max_mwh=50*8760
curtail_mwh=1126*1000
report={
 'calculation_status':'analytic consistency checks, not empirical replication',
 'electrolyzer_50mw_absolute_upper_bound_annual_gwh':annual_max_mwh/1000,
 'claimed_available_curtailment_gwh':1126,
 'max_curtailment_fraction_50mw_no_loss':annual_max_mwh/curtail_mwh,
 'claimed_78_2_percent_of_1126gwh_gwh':1126*.782,
 '78_2_percent_claim_exceeds_absolute_50mw_input_cap':1126*.782>annual_max_mwh/1000,
 'claimed_30_6_percent_of_1126_gwh_gwh':1126*.306,
 'lifetime_relative_improvement_17500_to_19100_pct':100*(19100/17500-1),
 'lifetime_relative_improvement_60000_to_72800_pct':100*(72800/60000-1),
 'bess_20_mwh_support_hours_at_40pct_50mw':20/(.4*50),
 'bess_needed_mwh_for_36h_at_40pct_50mw_before_losses':36*.4*50,
 'electricity_cost_100kg_h2_at_52kwh_kg_180usd_mwh':100*.052*180,
 'h2_production_from_340gwh_kg_at_52kwh_per_kg':340*1000/.052,
 'plant_800kg_per_day_offtake_annual_kg':800*365,
 'plant_800kg_per_day_offtake_annual_electrolysis_gwh':800*365*.052/1000,
 'offtake_fraction_of_340gwh_claim':800*365*.052/(340*1000),
 'qualification':'Full operational results require actual data, time-varying market/plant validation and re-runs'}
out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
