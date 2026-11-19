#!/usr/bin/env python
# trace: ADDR-012, ADDR-010
"""Django の管理コマンドの起動点（app/ を作業ディレクトリとして実行する）。"""

import os
import sys


# trace: ADDR-012, ADDR-010
def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
