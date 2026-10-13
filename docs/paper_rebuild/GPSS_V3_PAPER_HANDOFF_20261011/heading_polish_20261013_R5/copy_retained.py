from pathlib import Path
import csv
import json
import shutil

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'V3正文精修_20261013_R4'
KEEP = {1, 2, 5, 6, 7, 9, 10}
records = []
for row in csv.DictReader((OLD / 'MAIN_FIGURE_CATALOG.csv').open(encoding='utf-8-sig')):
    if int(row['figure']) not in KEEP:
        continue
    paths = {row[k] for k in ('preview', 'pdf', 'svg', 'png')}
    paths.add(str(Path(row['png']).with_suffix('.tiff')))
    for rel in sorted(paths):
        src = OLD / rel
        if not src.exists():
            continue
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        records.append({'figure': int(row['figure']), 'path': rel,
                        'identical_to_R4': src.read_bytes() == dst.read_bytes()})
for rel in ['schematics/F02_矢量放大查看.html',
            'schematics/figures/F02_method_8K.png',
            'schematics/figures/F02_method_4K.png',
            'schematics/figures/F02_method_reading.pdf',
            'schematics/editable/F02_method_traced.svg']:
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OLD / rel, dst)
(ROOT / 'RETAINED_FIGURES.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print({'retained_figures': sorted(KEEP), 'files': len(records),
       'identical': all(r['identical_to_R4'] for r in records)})
