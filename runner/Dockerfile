FROM grafana/xk6

RUN xk6 build v0.54.0 --with github.com/avitalique/xk6-file@latest

FROM grafana/k6

COPY --from=0 /xk6/k6 /usr/bin/k6

COPY scenario-INIT.js /config/scenario-INIT.js
COPY scenario-DATA_WRITE.js /config/scenario-DATA_WRITE.js
COPY scenario-DATA_LIST.js /config/scenario-DATA_LIST.js
COPY scenario-DATA_SIMPLE_ANALYTIC.js /config/scenario-DATA_SIMPLE_ANALYTIC.js

