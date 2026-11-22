#!/usr/bin/env python3
"""Download NLR NOW-23 North Atlantic 15-min wind from legitimate official API.

Requires NLR_API_KEY and NLR_EMAIL in environment (not included in ZIP).
Provider may NOT cover requested Nova Scotia site: distance gate rejects nearest-site
substitutions rather than silently treating a U.S. coastal point as Guysborough.
"""
import argparse,hashlib,json,math,os,sys
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from h2bench.ingest import load_nrel_wind_csv,validate_coverage
import pandas as pd

BASE='https://developer.nlr.gov/api/wind-toolkit/v2/wind/offshore-north-atlantic-download.csv'
def haversine(lat1,lon1,lat2,lon2):
    r=6371.;a=math.radians(lat2-lat1)/2;b=math.radians(lon2-lon1)/2
    h=math.sin(a)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(b)**2
    return 2*r*math.asin(math.sqrt(h))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lat',type=float,default=45.38)
    ap.add_argument('--lon',type=float,default=-61.50);ap.add_argument('--years',nargs='+',type=int,default=[2017,2018,2019,2020])
    ap.add_argument('--max-site-offset-km',type=float,default=20.);args=ap.parse_args()
    key=os.getenv('NLR_API_KEY');email=os.getenv('NLR_EMAIL')
    if not key or not email:raise SystemExit('DATA NOT DOWNLOADED: set NLR_API_KEY and NLR_EMAIL; no fallback data are invented')
    root=Path(__file__).resolve().parents[1];out=root/'data';out.mkdir(exist_ok=True)
    records=[];frames=[]
    for year in args.years:
        params={'api_key':key,'wkt':f'POINT({args.lon} {args.lat})',
            'attributes':'windspeed_100m','names':str(year),'utc':'true','leap_day':'true',
            'interval':'15','email':email,'full_name':'Research Replication'}
        r=requests.get(BASE,params=params,timeout=180);r.raise_for_status()
        if 'Year,Month,Day,Hour,Minute' not in r.text:
            raise RuntimeError('Provider did not return time-series CSV; first 300 chars: '+r.text[:300])
        lines=r.text.splitlines();idx=next(i for i,l in enumerate(lines) if l.startswith('Year,Month,Day,Hour,Minute'))
        site=lines[:idx]
        lat,lon=None,None
        for j,line in enumerate(site[:-1]):
            if 'Longitude' in line and 'Latitude' in line:
                cols=[c.strip().lower() for c in line.split(',')];vals=site[j+1].split(',')
                try:lon=float(vals[cols.index('longitude')]);lat=float(vals[cols.index('latitude')])
                except (ValueError,IndexError):pass
        if lat is None or lon is None:raise ValueError('Site coordinate metadata unavailable; refusing unverifiable site')
        distance=haversine(args.lat,args.lon,lat,lon)
        if distance>args.max_site_offset_km:
            raise ValueError(f'NEAREST SITE NOT VALID: requested ({args.lat},{args.lon}), provider ({lat},{lon}), distance={distance:.1f}km')
        path=out/f'NOW23_{year}_100m_15min.csv';path.write_bytes(r.content)
        d=load_nrel_wind_csv(path)
        if d.year.unique().tolist()!=[year]:raise ValueError(f'Unexpected year for {path}')
        frames.append(d)
        records.append({'year':year,'sha256':hashlib.sha256(r.content).hexdigest(),
                        'file':path.name,'rows':len(d),'site_lat':lat,'site_lon':lon,'site_distance_km':distance})
    merged=pd.concat(frames,ignore_index=True).sort_values('timestamp_utc')
    report=validate_coverage(merged)
    # gaps between years are okay only if leap years and adjacent years match exact cadence.
    if report['nonconsecutive_steps']:raise ValueError('Data time gaps found; investigate before training: '+str(report))
    merged.to_csv(out/'wind_normalized.csv',index=False)
    manifest={'provider':'NLR/NREL NOW-23 North Atlantic','dataset_url':'https://developer.nlr.gov/docs/wind/wind-toolkit/offshore-north-atlantic-download/',
              'requested_lat':args.lat,'requested_lon':args.lon,'requested_years':args.years,
              'source_status':'real modelled meteorological resource, not measured power/curtailment',
              'quality':report,'files':records,'api_key_or_email_in_manifest':False}
    (out/'provenance.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
