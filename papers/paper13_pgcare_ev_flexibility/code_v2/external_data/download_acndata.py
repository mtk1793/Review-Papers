"""Optional ACN-Data downloader for measured external validation.
Requires an ACN token in environment variable ACN_TOKEN. No measured ACN data are bundled
or claimed in the v2 manuscript because the public API requires user registration/token.
"""
import os,requests,json,time
from pathlib import Path
TOKEN=os.environ.get('ACN_TOKEN');
if not TOKEN: raise SystemExit('Set ACN_TOKEN to your personal ACN-Data API token.')
site=os.environ.get('ACN_SITE','caltech'); out=Path(__file__).resolve().parents[2]/'external_data'; out.mkdir(exist_ok=True)
url=f'https://ev.caltech.edu/api/v1/sessions/{site}'; page=1; sessions=[]
while True:
    r=requests.get(url,auth=(TOKEN,''),params={'page':page},timeout=60); r.raise_for_status(); j=r.json(); sessions.extend(j.get('_items',[]))
    if 'next' not in j.get('_links',{}): break
    page+=1; time.sleep(.15)
(out/f'acndata_{site}_sessions.json').write_text(json.dumps(sessions))
print('saved',len(sessions),'sessions')
