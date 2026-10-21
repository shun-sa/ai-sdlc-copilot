# trace: ADDR-001
"""WSGI エントリポイント（本番は WSGI サーバーから読み込む。NFR-EN-08）。"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
