# trace: ADDR-011
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    TZ=Asia/Tokyo

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/ /app/

# 静的ファイルを収集し、WhiteNoise で app プロセスから配信する（ADDR-011 DD-003）。
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# 既定の起動は Gunicorn（WSGI・同期ワーカー）。開発用サーバーは使用しない（ADDR-011 INV-001）。
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
