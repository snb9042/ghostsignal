# Dockerfile — headless GNSS IQ generation (no live TX)
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/osqzss/gps-sdr-sim.git /opt/gps-sdr-sim && \
    gcc /opt/gps-sdr-sim/gpssim.c -lm -O3 -DUSER_MOTION_SIZE=36000 \
        -o /usr/local/bin/gps-sdr-sim
ENV GPS_SDR_SIM=/usr/local/bin/gps-sdr-sim
WORKDIR /app
COPY pyproject.toml /app/
COPY ghostsignal /app/ghostsignal
RUN pip install --no-cache-dir -e . --no-deps   # headless CLI has no hard Qt need
ENTRYPOINT ["ghostsignal-cli"]
CMD ["--help"]
