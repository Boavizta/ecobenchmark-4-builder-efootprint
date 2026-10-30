# Evidence snapshot — 2026-10-30

This is a dated handoff, not a live test report. Implementation baseline:
`3e9f4c9` (`safe-pass`). Check the working tree, current code, and locally available
artifacts before continuing. Results below are ignored by Git and may be absent in
another checkout; their absence is not authorization to rerun measurements.

## Existing measurements

- `results/full-benchmark-20261029/`: 20 services, exactly one timed run each,
  60 seconds, 2 VUs, application and database each limited to 1 CPU / 1 GiB.
  There are **19 valid local observations**.
- PHP/MySQL failed 1,967 of 30,239 HTTP requests with
  `SQLSTATE[HY000] [2002] Cannot assign requested address`. Connection/address
  pressure is a hypothesis, not a confirmed diagnosis. No timed retry was made.
- The campaign uses `runner/scenario.js`: a completed mixed journey has 672 HTTP
  requests (1 account creation, 30 list writes, 600 task writes, 31 paginated list
  reads, 10 statistics reads). It is distinct from the 10-request smoke journey
  in `benchmark/service_smoke.js` and the one-GET reference workload in
  `benchmark/scenario.js`.
- `results/full-benchmark-20261029.zip` contains the archived campaign evidence.
  The campaign has no physical-energy measurements.

## Scaphandre simulation

- `results/scaphandre-simulation-20261029-attempt-5/` is the successful collector-only
  test; earlier failed attempts were retained separately.
- Pinned upstream Scaphandre v1.0.3 processed generated RAPL counters representing
  40 W package + 10 W DRAM. It reported about 50.012 W (0.025% difference), with
  14 valid samples. These validate the software pipeline, not hardware energy.
- `results/scaphandre-SIMULATED-20261029.zip` bundles that evidence. It supplies no
  production energy or footprint factors. Implementation: `benchmark/scaphandre.py`
  and `benchmark/scaphandre_sim/`.

## Outputs implemented

- `benchmark/output_data.py`: raw evidence normalization for full-service campaigns
  and two-host reference runs, integrity/validity handling, resource units.
- `benchmark/export_outputs.py`: offline CLI producing presentation CSV, normalized
  JSON, repeat statistics, CPU SVG charts, notebook, provenance, and ZIP.
- `benchmark/footprint_output.py`: provisional profiles/readiness, legacy-shaped
  research CSV, and an optional current `Job` construction interface for separately
  calibrated inputs. The integration tests mock e-footprint, not its full runtime.
- `results/outputs-20261030-final/` and its sibling ZIP are the validated delivery:
  20 observations / 19 valid. Its notebook was executed with charts embedded in an
  isolated `uv` environment. Earlier output directories are development attempts,
  not the final delivery.
- At this baseline, `make test` ran 56 tests: 53 passed, 3 opt-in SSH tests skipped.
  Future changes require fresh validation; these counts are historical.

## Remaining work and blockers

1. Agree a calibration campaign for isolated jobs, idle baselines, server-side
   duration, dynamic RAM/concurrency, and durable storage growth. The mixed data
   currently exports blockers, not usable independent `DATA_*` coefficients.
2. Obtain a compatible real Linux x86/RAPL target and explicitly authorize a new
   synchronized energy campaign before implementing physical-energy ingestion.
3. Validate the optional adapter against an installed/pinned e-footprint runtime
   before claiming end-to-end upstream integration.
4. For handoff outside the local workspace, publish artifacts through an authorized
   durable delivery mechanism. Previous `127.0.0.1` download links depended on a
   session-local server and must be rechecked or replaced.
