# trace: ADDR-014
# MiniCommerce アプリケーションのコンテナイメージ（ADDR-014 4.3 の3・6）。
# - ベースイメージはタグとダイジェストで固定する（取得元は Docker Hub の公式イメージ）。
# - 依存は pip-tools で生成したハッシュ付きの requirements.txt を --require-hashes で取得する。
# - 起動は全環境で Gunicorn（runserver を起動構成に含めない）。静的ファイルは起動時に collectstatic で集め WhiteNoise が配信する。
# - INSTALL_DEV=true のときだけ自動テスト・静的解析の依存（requirements-dev.txt）を追加する（ENV-01 用）。
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ARG INSTALL_DEV=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Tokyo \
    LANG=C.UTF-8 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /srv/minicommerce/app

COPY app/requirements.txt app/requirements-dev.txt /srv/minicommerce/app/
RUN pip install --require-hashes -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install --require-hashes -r requirements-dev.txt; fi

RUN groupadd --system minicommerce && useradd --system --gid minicommerce --home-dir /srv/minicommerce minicommerce \
    && mkdir -p /srv/minicommerce/staticfiles \
    && chown minicommerce:minicommerce /srv/minicommerce /srv/minicommerce/staticfiles

COPY app/ /srv/minicommerce/app/

USER minicommerce
EXPOSE 8000

CMD ["sh", "-c", "python manage.py collectstatic --noinput --verbosity 0 && exec gunicorn --config gunicorn.conf.py"]
