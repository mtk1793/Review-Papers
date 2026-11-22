from pathlib import Path
import pandas as pd
import pytest
from h2bench.ingest import load_nrel_wind_csv,validate_coverage,enforce_temporal_splits

def test_metadata_nrel_csv(tmp_path):
    c='SiteID,Site Timezone,Data Timezone,Longitude,Latitude,Country\n10,-4,-4,-61.5,45.38,Canada\nYear,Month,Day,Hour,Minute,wind speed at 100m (m/s)\n2020,1,1,0,0,10.0\n2020,1,1,0,15,12.0\n'
    p=tmp_path/'data.csv';p.write_text(c)
    d=load_nrel_wind_csv(p);assert len(d)==2
    q=validate_coverage(d);assert q['nonconsecutive_steps']==0

def test_missing_year_fail_closed(tmp_path):
    c='Year,Month,Day,Hour,Minute,wind speed at 100m (m/s)\n2020,1,1,0,0,10.0\n2020,1,1,0,15,12.0\n'
    p=tmp_path/'data.csv';p.write_text(c)
    d=load_nrel_wind_csv(p)
    with pytest.raises(ValueError,match='MISSING REAL YEARS'):
        enforce_temporal_splits(d)
