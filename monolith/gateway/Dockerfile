FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GATEWAY_DATA_DIR=/data

# tzdata: OMRON timestamps are local time, interpreted in $TZ.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY omron_ble ./omron_ble
COPY aivin_gateway ./aivin_gateway
COPY tests ./tests

# Runs as root: BlueZ's D-Bus policy on the host only lets root (or the
# bluetooth group, which has no stable GID inside the container) use the adapter.
VOLUME /data
ENTRYPOINT ["python", "-m", "aivin_gateway"]
CMD ["run"]
