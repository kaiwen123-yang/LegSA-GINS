from pathlib import Path
import csv
import json
import shutil

ROOT = Path(__file__).resolve().parent
PREV = ROOT.parent / 'V3正文精修_20261013_R5'
R4 = ROOT.parent / 'V3正文精修_20261013_R4'
keep = {1, 2, 5, 6, 7, 9, 10}
records = []
for row in csv.DictReader((PREV/'MAIN_FIGURE_CATALOG.csv').open(encoding='utf-8-sig')):
    if int(row['figure']) not in keep:
        continue
    paths = {row[k] for k in ['preview', 'pdf', 'svg', 'png']}
    paths.add(str(Path(row['png']).with_suffix('.tiff')))
    for rel in sorted(paths):
        source = PREV/rel
        if not source.exists():
            continue
        dest = ROOT/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        records.append({'figure': int(row['figure']), 'path': rel.replace('\\','/'),
                        'source_revision': 'R5', 'identical': source.read_bytes()==dest.read_bytes()})
for rel in ['schematics/F02_矢量放大查看.html', 'schematics/figures/F02_method_8K.png',
            'schematics/figures/F02_method_4K.png', 'schematics/figures/F02_method_reading.pdf',
            'schematics/editable/F02_method_traced.svg']:
    dest=ROOT/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(PREV/rel,dest)
stem='F04_absolute_direction_relative_motion'
for rel in [f'observability/{stem}.{e}' for e in ['pdf','svg','png','tiff']] + [f'observability/preview/{stem}.png']:
    source=R4/rel
    dest=ROOT/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,dest)
    records.append({'figure':4,'path':rel,'source_revision':'R4','identical':source.read_bytes()==dest.read_bytes()})
(ROOT/'RETAINED_FIGURES.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print({'retained':[1,2,5,6,7,9,10],'figure4_restored_from':'R4','identical':all(r['identical'] for r in records)})
