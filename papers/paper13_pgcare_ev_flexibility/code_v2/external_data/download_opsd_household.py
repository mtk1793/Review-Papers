"""Optional downloader/preprocessor for OPSD measured 15-min household load/PV data.
The dataset is not bundled because it is ~58 MB and the current execution environment blocks
external binary downloads. The URL is stable and documented by Open Power System Data.
"""
from pathlib import Path
import pandas as pd, urllib.request
URL='https://data.open-power-system-data.org/household_data/2020-04-15/household_data_15min_singleindex.csv'
out=Path(__file__).resolve().parents[2]/'external_data'; out.mkdir(exist_ok=True); raw=out/'household_data_15min_singleindex.csv'
if not raw.exists(): urllib.request.urlretrieve(URL,raw)
df=pd.read_csv(raw)
cols=[c for c in df.columns if ('residential' in c.lower() and ('grid_import' in c.lower() or c.lower().endswith('_pv')))]
df[['utc_timestamp']+cols].to_csv(out/'opsd_residential_load_pv_15min.csv',index=False)
print('saved',len(df),'rows and',len(cols),'measured residential load/PV channels')
