#!/usr/bin/env python
# trace: ADDR-004
"""MiniCommerce の管理コマンド入口。"""
import os
import sys


def main() -> None:
    """Django の管理コマンドを実行する。"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
