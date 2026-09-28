#!/usr/bin/env python3
"""Export-layout adjustment after actual HX-05 raster inspection; data unchanged."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
from legsa_gins.paper_rebuild.hext.hx05_common import paths, dump, sha, forbid_reference_open
from legsa_gins.paper_rebuild.hext import hx05_figures as figures
from legsa_gins.paper_rebuild.publication import style, qa


def main():
    forbid_reference_open(); p = paths()
    source = p['SCRATCH']/'MANUSCRIPT/MANUSCRIPT_DATA.json'
    data = json.loads(source.read_text())
    out = p['SCRATCH']/'FIGURES_ACCEPTED'; out.mkdir(exist_ok=False)
    checks = []; manifest = []; hashes = {}
    for name, fn in [('FIG02S', figures.fig02s), ('FIG02D', figures.fig02d), ('SFIG-HX', figures.sfig_hx)]:
        fig, bindings = fn(data)
        for ax in fig.axes:
            label = ax.get_xlabel()
            if label == 'Position drift (m) per 100 m':
                ax.set_xlabel('Position drift (m)\nper 100 m')
            elif label == 'Heading drift (°) per min':
                ax.set_xlabel('Heading drift (°)\nper min')
            elif label == 'Availability (%)':
                ax.set_xlim(-4, 105)
            for text in ax.texts:
                if text.get_text() in ('No valid heading', 'Diverged', 'Initialization stopped'):
                    text.set_bbox({'facecolor': 'white', 'edgecolor': 'none', 'pad': .4, 'alpha': .9})
        result = qa.check_figure(fig, name)
        checks.extend(result)
        files = style.save_figure(fig, out, name)
        checks.extend(qa.check_png(Path(files['png']), name))
        checks.append({'figure_id': name, 'check': 'legend_and_bound_panels', 'pass': bool(fig.legends) and all(b['no_empty_panel'] for b in bindings), 'detail': str(len(bindings))+' panels'})
        files['bindings'] = bindings; manifest.append(files)
        hashes[name] = qa.average_hash(Path(files['png']))
        plt.close(fig)
    duplicates = qa.duplicate_pairs(hashes)
    checks.append({'figure_id': 'ALL', 'check': 'no_duplicate_rasters', 'pass': not duplicates, 'detail': str(duplicates)})
    for row in checks: row['pass'] = bool(row['pass'])
    dump(out/'FIGURE_MANIFEST.json', {'data_sha256': sha(source), 'figures': manifest})
    dump(out/'MACHINE_QA.json', {'passed': all(r['pass'] for r in checks), 'checks': checks, 'actual_visual_review': 'PENDING'})
    (out/'CAPTIONS_HX05.md').write_text(figures.CAPTIONS)
    assert all(r['pass'] for r in checks)
    print(json.dumps({'passed': True, 'checks': len(checks), 'figures': len(manifest)}))


if __name__ == '__main__': main()
