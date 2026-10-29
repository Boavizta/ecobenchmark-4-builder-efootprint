FROM hubblo/scaphandre:1.0.3@sha256:cd1d8c27d359d0e5add0cf8bcced5ca2bf6699aa212b03999a6a9b131fdc4416 AS build
USER root
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*
COPY fixture_reads.c /tmp/fixture_reads.c
RUN gcc -Wall -Wextra -Werror -shared -fPIC -o /tmp/scaphandre-simulation.so /tmp/fixture_reads.c -ldl

FROM hubblo/scaphandre:1.0.3@sha256:cd1d8c27d359d0e5add0cf8bcced5ca2bf6699aa212b03999a6a9b131fdc4416
RUN apt-get update && apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=build /tmp/scaphandre-simulation.so /usr/local/lib/scaphandre-simulation.so
COPY generate.py /opt/scaphandre-simulation/generate.py
LABEL org.boavizta.scaphandre.simulation="true"
ENV LD_PRELOAD=/usr/local/lib/scaphandre-simulation.so SCAPHANDRE_SIMULATION=1
