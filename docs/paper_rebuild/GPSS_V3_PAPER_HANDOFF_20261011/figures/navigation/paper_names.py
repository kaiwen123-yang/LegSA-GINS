"""Reader-facing names; data keys remain the original recording identifiers."""
import re

SCENARIOS = {
    'BY2': {'panel': 'Nominal walking', 'en': 'nominal walking', 'zh': '常规行走'},
    'BY2H': {'panel': 'Large body motion', 'en': 'large body motion', 'zh': '大幅机身运动'},
    'BY2O': {'panel': 'Antenna obstruction', 'en': 'single-antenna obstruction', 'zh': '单侧天线遮挡'},
}
LEGENDS = {
    'IEKF-LIT': 'IEKF (literature)', 'IEKF-S': 'IEKF (calibrated)',
    'OiSAM': 'OiSAM-FGO',
    'V0': 'Original', 'V0E': 'Alt. eph.', 'V1': 'Multi-GNSS', 'V2': 'Fix-and-hold',
}

def scenario_label(key):
    return SCENARIOS.get(key, {}).get('panel', key)

def caption_names(text, language):
    if language == 'en':
        text = text.replace('on BY2, BY2H and BY2O',
                            'during nominal walking, large body motion and single-antenna obstruction')
    for key in ('BY2H', 'BY2O', 'BY2'):
        text = re.sub(r'(?<![A-Za-z0-9_])'+key+r'(?![A-Za-z0-9_])',
                      SCENARIOS[key][language], text)
    return text

def apply_figure_names(fig):
    from matplotlib.text import Text
    for item in fig.findobj(Text):
        text = item.get_text()
        if text in LEGENDS:
            item.set_text(LEGENDS[text])
