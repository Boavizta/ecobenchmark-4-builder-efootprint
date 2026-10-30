# Project scope

## Purpose

Provide evidence-backed ecodesign guidance for ordinary management and SaaS web
applications: application servers, databases, storage, and their resource needs.
The intended audience includes architects, developers, product teams, and technical
leaders. Representative community practices matter more than expert-only tuning.

This scope is distilled from the owner's supplied French brief,
`brief-evaluer-impact-application-web.md`. The attachment originally lived in
workspace-local `.baton-files/`; this tracked summary is usable without that folder.

## Boundaries

- Focus on CPU, RAM, network, storage, and workload behavior rather than assuming
  bandwidth alone predicts application impact.
- Specialized content, ML, and mobile concerns may require separate models.
- Hyperscale streaming systems and specialized AI/LLM systems are outside the
  intended model's validity; avoid extrapolating these benchmark results to them.
- Software/architecture “boost” factors are a research goal: they would modify
  infrastructure requirements, which an infrastructure model can translate into
  impacts. The illustrative `boost_coeff: 2.4` in the brief is not a measured factor
  or an implemented current e-footprint field.

## Two outputs, one evidence pipeline

Normalize raw observations once, then maintain separate adapters:

1. **Eco-benchmark presentation:** reproducible tables, repeat statistics, charts,
   and a notebook. Results describe the measured workload/environment, not universal
   framework rankings.
2. **e-footprint data:** sourced resource observations and, only when justified,
   calibrated service/job requirements. Export explicit readiness blockers when
   evidence cannot identify a requirement.

Target research labels include `DATA_READ`, `DATA_WRITE`, `DATA_LIST`,
`DATA_SIMPLE_ANALYTIC`, `TRANSACTION`, and `NOTIFICATION`. They express intended
coverage, not six measured isolated workloads or fields on current upstream `Job`.

## Source references

- [Original benchmark](https://github.com/Boavizta/ecobenchmark-applicationweb-backend)
  and [pinned notebook](https://github.com/Boavizta/ecobenchmark-applicationweb-backend/blob/aeea2451de2e4fb83333d9cc8b7090e27b5ba022/results/ecobenchmark.ipynb).
- [Presentation slides](https://docs.google.com/presentation/d/15piYZbxdp_6H0mann5auFir79TZ6XfrwLZ13xHf53vE/edit).
- [Video](https://youtu.be/fGM1aJWLNXI): no transcript was obtained during the
  October 2026 investigation; do not attribute unverified claims to it.
- [e-footprint](https://github.com/Boavizta/e-footprint) is the downstream consumer.
  See the [contract research](../../benchmark/research/e-footprint-contract.md)
  for pinned current/legacy interfaces and verified historical authorship.
