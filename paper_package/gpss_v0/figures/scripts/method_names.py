"""Reader-facing names only; never alters scientific selectors or numbers."""
from pathlib import Path
import csv,json,re
P=Path(__file__).resolve().parents[2]
IDENTITY=json.loads((P/'METHOD_IDENTITY.json').read_text())
ADDENDUM=json.loads((P/'BASELINE_READER_NAMES.json').read_text())
DISPLAY=dict(ADDENDUM['internal_display_names'])
LEGEND={row['internal_code']:row['legend_name'] for row in IDENTITY['mapping']}
for row in ADDENDUM['baseline_mapping']:
 DISPLAY[row['internal_code']]=row['display_name'];LEGEND[row['internal_code']]=row['legend_name']
for alias,canonical in ADDENDUM['internal_aliases'].items():
 DISPLAY[alias]=DISPLAY[canonical];LEGEND[alias]=LEGEND[canonical]
CODES='|'.join(re.escape(k) for k in sorted(DISPLAY,key=len,reverse=True))
PATTERN=re.compile(r'(?<![A-Za-z0-9_])('+CODES+r')(?![A-Za-z0-9_])')
PAIR_PATTERN=re.compile(r'(?<![A-Za-z0-9_])('+CODES+')-('+CODES+r')(?![A-Za-z0-9_])')
def reader_text(text,legend=False):
 mapping=LEGEND if legend else DISPLAY
 text=str(text).replace('_minus_',' minus ').replace('-minus-',' minus ').replace('-to-',' to ')
 text=PAIR_PATTERN.sub(lambda m:mapping[m.group(1)]+' minus '+mapping[m.group(2)],text)
 return PATTERN.sub(lambda m:mapping[m.group()],text)
def source_prose(text):
 return ''.join(part if part.startswith('[[') else reader_text(part) for part in re.split(r'(\[\[[^\]]+\]\])',text))
def legend_name(code):return LEGEND.get(code,code)
def table_rows(rows):
 # Reproduction locators retain their original scientific/source identity.
 keep={'source_id','source_path','run_id','case_id','sha256','input_sha256'}
 result=[]
 for row in rows:
  result.append({('Method' if k=='method_id' else reader_text(k)):v if k in keep else reader_text(v) for k,v in row.items()})
 return result
