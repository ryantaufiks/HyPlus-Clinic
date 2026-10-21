FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system aivin && useradd --system --gid aivin --home /app aivin

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=aivin:aivin . .

# collectstatic needs settings to import; these build-time values are not used at runtime.
RUN SECRET_KEY=build-only FIELD_ENCRYPTION_KEY=$(python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())") \
    python manage.py collectstatic --noinput \
    && chown -R aivin:aivin /app/staticfiles \
    && mkdir -p /app/media && chown aivin:aivin /app/media

USER aivin

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "--config", "docker/gunicorn.conf.py", "health_kiosk.wsgi:application"]
