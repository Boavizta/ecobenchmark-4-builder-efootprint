# Evidence rules

Read before changing collection, analysis, or output semantics. Operational commands
and file formats live in [benchmark/README.md](../../benchmark/README.md).

## Provenance and validity

- Preserve raw k6/resource samples, metadata, source/schema hashes, image identity,
  environment, and failure status. Derived outputs go into a new directory.
- Retain failed runs for diagnosis while excluding them from valid comparisons and
  coefficient fitting. Missing measurements are unavailable, not zero cost.
- Compare equivalent workloads, schemas, dataset/load settings, allocations, and
  environments. Separate cohorts before aggregating independent repeats.
- One timed observation has no repeat uncertainty estimate. Show its value and
  count; leave sample standard deviation unavailable rather than inventing bounds.
- Local Docker/Lima observations share host resources. SSH transport alone does not
  establish dedicated hardware or a noise-free measurement environment.

## Quantities and attribution

- CPU counters are cumulative CPU-seconds. Mean cores require dividing a counter
  delta by its elapsed interval. Include application **and database**, rather than
  adding application CPU twice as the historical notebook did.
- Cgroup RAM includes cache; it is not process RSS. Aggregate memory on aligned
  timestamps. Summing independent peaks does not produce an observed joint peak.
  A sampled/interpolated peak is not a guaranteed true peak.
- State whether an operation is a request, isolated job, or mixed journey. Equal
  iteration/request counts alone do not prove task attribution. Keep workload
  declarations and source provenance with observations.
- Client HTTP latency is not measured server execution duration. Collector windows
  and in-flight work may extend outside completed k6 iteration accounting.

## Energy

- Keep physical measurements, synthetic fixtures, unverified values, and absent
  data separate. Synthetic Scaphandre results retain `simulation=true`,
  `measured_energy_available=false`, and `joules=null`.
- CPU time is not measured energy. Historical resource campaigns cannot acquire
  physical energy retrospectively.
- Scaphandre JSON power is in microwatts. Energy integration requires timestamps,
  compatible domains, and provenance; summing power samples is not sufficient.
  Avoid double-counting the host aggregate and its socket/domain breakdown.
- RAPL domain energy is not whole-machine wall power; process allocations are
  estimates. Physical energy ingestion in the output normalizer remains unsupported
  until a synchronized provenance contract exists.

## Resource calibration

- Mixed journeys cannot identify independent task costs or universal boost factors.
- Service idle CPU/RAM belongs to a per-instance baseline, independent of traffic.
  Job RAM needs attribution and concurrency evidence, not peak RAM/request count.
- Conditional CPU fitting needs an attributed CPU delta, operation count, and
  server-side duration: CPU-seconds / (count × duration) yields cores. Baseline and
  measurement-window assumptions must be explicit.
- Storage requires durable growth evidence; transferred HTTP bytes are not stored
  bytes. Keep network direction and scope explicit.
- For current e-footprint units, construction interfaces, and removed legacy
  assumptions, use the [consumer contract research](../../benchmark/research/e-footprint-contract.md)
  as the detailed reference. An observation marked blocked is not a calibrated Job.
