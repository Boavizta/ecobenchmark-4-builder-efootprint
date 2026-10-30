# Agent guide

This repository produces benchmark evidence for web-application design decisions
and e-footprint resource models. It is not a programming-language competition.

## Read by task

- **Scope or modeling decisions:** read [project scope](docs/context/project-scope.md).
- **Measurement, analysis, or exporter changes:** read
  [evidence rules](docs/context/evidence-rules.md), then the relevant workflow in
  [benchmark/README.md](benchmark/README.md).
- **Continuing prior work or looking for artifacts:** read the dated
  [evidence snapshot](docs/context/evidence-status.md). Verify local availability;
  ignored results are not included in a fresh clone.
- **e-footprint integration or contribution history:** read the pinned
  [consumer contract research](benchmark/research/e-footprint-contract.md).
  Current upstream contracts take precedence over historical field names in the
  root README; verify upstream before changing the integration.
- **Service implementations or SQL:** read [CONTRIBUTING.md](CONTRIBUTING.md),
  [service/specs.md](service/specs.md), and the implementation's own README.

## Working rules

- Preserve raw evidence and failed attempts. Keep measured, simulated,
  unavailable, and unverified quantities distinct, with explicit units.
- Existing campaigns are frozen evidence. Ask before running a new timed campaign,
  retrying a timed observation, or resetting a benchmark database. Output generation
  is an offline operation and needs no benchmark rerun.
- Keep orchestration/export code dependency-free where practical. Notebook plotting
  and the optional e-footprint runtime belong in separate environments. If a
  dependency is unsupported, explain replacement options before adopting one.
- Preserve API/SQL/schema comparability across services. Treat changed indexes,
  fixtures, protocols, or query designs as distinct use cases.

## Validation and delivery

1. Add regression coverage for behavior changes; run `make test` and
   `git diff --check`. Report skipped integration tests separately.
2. For exporter changes, exercise existing evidence into a **new** output directory;
   check validity counts, units, provenance, and failed-run exclusions. Run the
   notebook when modifying its executable cells; distinguish syntax checks from
   execution and mocked adapters from upstream integration tests.
3. Use emoji-prefixed conventional commits, e.g. `📊 feat: ...` or `📝 docs: ...`.
   The project owner's standing preference is to validate, commit, and push task
   changes without another confirmation unless a significant issue arises.
4. Keep generated results and credentials out of commits. For downloadable artifacts,
   verify the actual delivery URL; workspace paths and session-local localhost links
   are not durable public links.

When these rules, consumer contracts, or evidence availability change, update their
authoritative context file rather than appending another session transcript here.
