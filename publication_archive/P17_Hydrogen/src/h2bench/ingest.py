"""Normalize NREL/NOW-23 CSV with metadata headers and explicit temporal checks."""
import io
from pathlib import Path
import pandas as pd
import numpy as np
from .physics import wind_to_power

def load_nrel_wind_csv(path):
    raw=Path(path).read_text(encoding='utf-8-sig')
    lines=raw.splitlines()
    idx=next((i for i,line in enumerate(lines) if 'Year,Month,Day,Hour,Minute' in line), None)
    if idx is None: raise ValueError('NREL CSV must contain Year,Month,Day,Hour,Minute header')
    df=pd.read_csv(io.StringIO('\n'.join(lines[idx:])))
    speed=next((c for c in df if ('wind speed at 100m' in c.lower() or c.lower().strip()=='windspeed_100m')),None)
    if speed is None: raise ValueError('100m wind speed missing; request windspeed_100m')
    dt=pd.to_datetime(df[['Year','Month','Day','Hour','Minute']].rename(columns={
        'Year':'year','Month':'month','Day':'day','Hour':'hour','Minute':'minute'}),utc=True)
    out=pd.DataFrame({'timestamp_utc':dt,'wind_speed_100m_ms':pd.to_numeric(df[speed],errors='coerce')})
    out=out.dropna().sort_values('timestamp_utc').reset_index(drop=True)
    if out.timestamp_utc.duplicated().any():raise ValueError('duplicate timestamps')
    if len(out)<2:raise ValueError('at least two wind observations required')
    if (out.wind_speed_100m_ms<0).any():raise ValueError('negative wind speeds')
    out['wind_mw']=out.wind_speed_100m_ms.apply(wind_to_power)
    out['year']=out.timestamp_utc.dt.year
    return out

def validate_coverage(df, expected_interval_minutes=15):
    deltas=df.timestamp_utc.diff().dropna().dt.total_seconds()/60
    if not len(deltas):raise ValueError('not enough data')
    n_gaps=int((deltas!=expected_interval_minutes).sum())
    return {'observations':int(len(df)), 'years':sorted(df.year.unique().astype(int).tolist()),
            'duplicate_timestamps':int(df.timestamp_utc.duplicated().sum()),
            'nonconsecutive_steps':n_gaps, 'expected_interval_minutes':expected_interval_minutes,
            'missing_values':int(df[['wind_mw','wind_speed_100m_ms']].isna().sum().sum())}

def enforce_temporal_splits(df,train_years=(2017,2018),calibration_year=2019,test_year=2020):
    yrs=set(df.year.astype(int))
    required=set(train_years)|{calibration_year,test_year}
    if not required.issubset(yrs):
        raise ValueError('MISSING REAL YEARS: required %s; found %s'%(sorted(required),sorted(yrs)))
    if max(train_years)>=calibration_year or calibration_year>=test_year:
        raise ValueError('train/calibrate/test years not chronological')
    return (df[df.year.isin(train_years)],df[df.year==calibration_year],df[df.year==test_year])
