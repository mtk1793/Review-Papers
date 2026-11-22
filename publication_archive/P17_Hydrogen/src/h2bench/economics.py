"""Explicit cash-flow accounting; never silently equate operating reward with NPV.
Economics remain scenario-based unless costs, offtake, and price traces verified.
"""
from math import floor

def npv_from_annual_cashflows(capex_usd, annual_cashflows, discount_rate,
                             stack_replacement_usd=0., annual_eq_hours=None,
                             eq_life_hours=60000.):
    if capex_usd<0 or discount_rate<0:raise ValueError('capex/rate must be >=0')
    if eq_life_hours<=0:raise ValueError('stack design life must be >0')
    flows=list(annual_cashflows)
    if annual_eq_hours is not None and len(annual_eq_hours)!=len(flows):
        raise ValueError('aging series must match horizon')
    aging=0.;replacement_count=0
    discounted=-float(capex_usd);cashledger=[]
    for t,cash in enumerate(flows,1):
        replacements=0
        if annual_eq_hours is not None:
            aging+=float(annual_eq_hours[t-1])
            while aging>=eq_life_hours:
                replacements+=1;aging-=eq_life_hours
        replacement_cost=stack_replacement_usd*replacements
        discounted+=(float(cash)-replacement_cost)/(1+discount_rate)**t
        replacement_count+=replacements
        cashledger.append({'year':t,'operating_cash_usd':float(cash),
            'replacement_cost_usd':float(replacement_cost),
            'discounted_net_usd':(float(cash)-replacement_cost)/(1+discount_rate)**t})
    return {'npv_usd':discounted,'discount_rate':discount_rate,
       'replacement_count':replacement_count,'cash_ledger':cashledger,
       'not_validated_technoeconomics':True}
