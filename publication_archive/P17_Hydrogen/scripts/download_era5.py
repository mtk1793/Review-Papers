#!/usr/bin/env python3
"""API-key-free real ERA5 reanalysis robustness dataset (hourly; not NREL NOW-23).
Download source: https://open-meteo.com/en/docs/historical-weather-api
No interpolation or relabeling to 5/15-minute resolution is performed.
"""
import os,sys,json,hashlib,math
from pathlib import Path
import pandas as pd
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from h2bench.physics import wind_to_power
from h2bench.ingest import validate_coverage

def main():
    root=Path(__file__).resolve().parents[1]
    out=root/'data'/'era5';out.mkdir(parents=True,exist_ok=True)
    frames=[];sources=[]
    for year in [2017,2018,2019,2020]:
        args={'latitude':45.38,'longitude':-61.50,'start_date':f'{year}-01-01',
            'end_date':f'{year}-12-31','hourly':'wind_speed_100m',
            'wind_speed_unit':'ms','models':'era5','timezone':'UTC'}
        r=requests.get('https://archive-api.open-meteo.com/v1/archive',params=args,timeout=120)
        r.raise_for_status();v=r.json()
        if v.get('error'):raise ValueError(v)
        if 'hourly' not in v:raise ValueError('No hourly data: '+r.text[:300])
        d=pd.DataFrame({'timestamp_utc':pd.to_datetime(v['hourly']['time'],utc=True),
            'wind_speed_100m_ms':pd.to_numeric(v['hourly']['wind_speed_100m'],errors='coerce')})
        if d.wind_speed_100m_ms.isna().any():raise ValueError('missing ERA5 weather; must investigate')
        d['wind_mw']=d.wind_speed_100m_ms.map(wind_to_power);d['year']=year
        frames.append(d)
        fname=f'ERA5_{year}_hourly.json';(out/fname).write_bytes(r.content)
        sources.append({'year':year,'rows':len(d),'sha256':hashlib.sha256(r.content).hexdigest(),
                        'file':fname,'source_grid_lat':v.get('latitude'),'source_grid_lon':v.get('longitude')})
    series=pd.concat(frames,ignore_index=True).sort_values('timestamp_utc')
    qc=validate_coverage(series,expected_interval_minutes=60)
    if qc['nonconsecutive_steps'] or qc['missing_values']:raise ValueError('ERA5 QC failed: '+str(qc))
    series.to_csv(out/'wind_normalized.csv',index=False)
    prov={'provider':'Open-Meteo ERA5 reanalysis','dataset_url':'https://open-meteo.com/en/docs/historical-weather-api',
          'type':'modelled real meteorological historical data, NOT historical wind farm output',
          'site_lat':45.38,'site_lon':-61.50,'interval_minutes':60,'quality':qc,'files':sources}
    (out/'provenance.json').write_text(json.dumps(prov,indent=2))
    print('Downloaded real hourly ERA5 reanalysis. NOT equivalent to NREL 15-minute dataset.')
if __name__=='__main__':main()
