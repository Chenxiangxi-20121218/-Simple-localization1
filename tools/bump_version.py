# -*- coding: utf-8 -*-
"""版本号管理。

版本号格式 ``x.y.z``：
* ``x`` 大版本 —— 仅用 ``--major`` 手动递增
* ``y`` 小更新 —— 一般不变，仅用 ``--minor`` 手动递增
* ``z`` 维护版 —— **每次更新自动递增**（默认行为）

用法::

    python tools/bump_version.py            # z += 1（每次更新默认执行）
    python tools/bump_version.py --show     # 只打印当前版本
    python tools/bump_version.py --minor    # y += 1, z = 0
    python tools/bump_version.py --major    # x += 1, y = 0, z = 0
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PY = ROOT / "app" / "state.py"
PATTERN = re.compile(r'^APP_VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)


def read_version() -> tuple[int, int, int]:
    m = PATTERN.search(STATE_PY.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("未在 app/state.py 中找到 APP_VERSION")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def write_version(v: tuple[int, int, int]) -> None:
    text = STATE_PY.read_text(encoding="utf-8")
    text = PATTERN.sub(f'APP_VERSION = "{v[0]}.{v[1]}.{v[2]}"', text, count=1)
    STATE_PY.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    major, minor, patch = read_version()

    if "--show" in argv:
        print(f"{major}.{minor}.{patch}")
        return 0

    if "--major" in argv:
        major, minor, patch = major + 1, 0, 0
    elif "--minor" in argv:
        major, minor, patch = major, minor + 1, 0
    else:
        patch += 1        # 默认：维护版每次更新递增

    write_version((major, minor, patch))
    print(f"{major}.{minor}.{patch}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
