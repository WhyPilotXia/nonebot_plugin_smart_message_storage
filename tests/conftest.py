# python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

import nonebot


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "tests" / ".runtime"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        nonebot.get_driver()
        return
    except ValueError:
        pass

    nonebot.init(
        localstore_data_dir=RUNTIME_DIR / "localstore",
        message_db_url=f"sqlite:///{(RUNTIME_DIR / 'test_messages.db').as_posix()}",
    )
