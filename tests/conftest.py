"""テスト実行時に app/ を import 可能にする設定（後続のテスト工程が利用する）。"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = (REPO_ROOT / "app", Path("/app"))

for candidate in CANDIDATES:
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
