"""Render scientific formulae for slides; source LaTeX is retained verbatim."""
from pathlib import Path
import json, os
import matplotlib
from matplotlib.mathtext import math_to_image
from matplotlib.font_manager import FontProperties

OUT = Path(os.environ.get('LEGSA_PPT_EQ_OUT','/mnt/c/Users/ykw/.codex/tmp/legsa_paper_deck_20261004/.build/equations'))
OUT.mkdir(exist_ok=True)
matplotlib.rcParams['mathtext.fontset'] = 'stix'
FORMULAE = {
    'baseline': r'$\mathbf{b}^{n}=\mathbf{p}_{2}^{n}-\mathbf{p}_{1}^{n}$',
    'heading': r'$\psi_b=\operatorname{atan2}(b_E,b_N)+90^{\circ}$',
    'sensitivity': r'$\delta\psi\simeq\delta b_{\perp}/\|\mathbf{b}_{H}\|$',
    'residual': r'$r_{\psi}=\operatorname{wrap}(\psi_{\mathrm{pred}}-\psi_{\mathrm{obs}})$',
    'state': r'$\delta\mathbf{x}=[\delta\mathbf{p},\delta\mathbf{v},\delta\boldsymbol{\theta},\delta\mathbf{b}_{g},\delta\mathbf{b}_{a}]^{T}$',
    'covariance': r'$\mathbf{P}^{-}=\boldsymbol{\Phi}\mathbf{P}^{+}\boldsymbol{\Phi}^{T}+\mathbf{Q}$',
    'innovation': r'$\mathbf{S}=\mathbf{H}\mathbf{P}^{-}\mathbf{H}^{T}+\mathbf{R}$',
    'gain': r'$\mathbf{K}=\mathbf{P}^{-}\mathbf{H}^{T}\mathbf{S}^{-1}$',
    'correction': r'$\delta\mathbf{x}^{+}=\delta\mathbf{x}^{-}+\mathbf{K}\mathbf{r}$',
    'hv': r'$\mathbf{v}_{H}^{n}=\boldsymbol{\Pi}_{H}\widehat{\mathbf{C}}\,k_{\mathrm{HV}}\mathbf{v}_{\mathrm{SDK}}^{\mathrm{FLU}}$',
    'difference': r'$\mathbf{d}=\widehat{\mathbf{x}}-\mathbf{x}_{\mathrm{ref}}$',
    'baseline_cov': r'$\mathbf{C}_{b}=\mathbf{C}_{p_1}+\mathbf{C}_{p_2}-\mathbf{C}_{12}-\mathbf{C}_{12}^{T}$',
    'heading_jac': r'$\mathbf{J}_{\psi}=[-b_E,\ b_N]/(b_N^2+b_E^2)$',
    'heading_cov': r'$u_{\psi}^{2}\simeq\mathbf{J}_{\psi}\mathbf{C}_{b,NE}\mathbf{J}_{\psi}^{T}$',
    'gum': r'$\mathbf{C}_{y}\simeq\mathbf{J}\mathbf{C}_{z}\mathbf{J}^{T}$',
    'ref_cov': r'$\mathbf{C}_{d}=\mathbf{C}_{\hat{x}}+\mathbf{C}_{\mathrm{ref}}-\mathbf{C}_{\hat{x},\mathrm{ref}}-\mathbf{C}_{\hat{x},\mathrm{ref}}^{T}$',
    'timing': r'$\delta\mathbf{b}_{t}\simeq\mathbf{v}\,\Delta t$',
    'rotation': r'$\delta\mathbf{v}^{n}\simeq\mathbf{C}_{b}^{n}\delta\mathbf{v}^{b}-\mathbf{C}_{b}^{n}[\mathbf{v}^{b}]_{\times}\delta\boldsymbol{\alpha}^{b}$',
    'coverage': r'$\widehat{c}=\#\{e\in\mathcal{I}_{p}\}/N$',
}
for name, expr in FORMULAE.items():
    for fmt in ('png', 'svg'):
        math_to_image(expr, OUT / f'{name}.{fmt}', prop=FontProperties(size=32), dpi=240, format=fmt, color='#024282')
(OUT / 'formulae.json').write_text(json.dumps(FORMULAE, ensure_ascii=False, indent=2)+'\n')
print(f'Rendered {len(FORMULAE)} formulae, PNG and SVG.')
