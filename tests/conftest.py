"""Test import path setup for the src-layout package.

中文说明：测试辅助模块只服务测试导入和合同验证，不依赖 raw data。
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
