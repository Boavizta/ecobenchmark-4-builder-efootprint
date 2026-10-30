# e-footprint benchmark consumer contract: current and historical

Research date: 2026-10-30. Read-only inspection of GitHub source/API and a full clone (all advertised branches and tags); no benchmarks or application changes. This is the delegated research deliverable, not an implemented exporter.

## Executive conclusion

**Current e-footprint has no active ecobenchmark CSV consumer or web-application technology/task builder.** Exporting the old CSV is not an integration with current main. The usable current seam is `Job` with explicitly dimensioned resource requirements, or a future agreed service/job builder. Preserve the mixed-workload observations as provisional research data; do not manufacture six task coefficients, hardware-independent boost factors, physical energy, or production calibration from them.

Pinned current main: [`d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6`](https://github.com/Boavizta/e-footprint/commit/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6). Pinned last inspected legacy snapshot: [`dab810742fc4f3fc0d1163804398d28b4607931c`](https://github.com/Boavizta/e-footprint/tree/dab810742fc4f3fc0d1163804398d28b4607931c), parent of the removal commit. Sources below distinguish current behavior, historical behavior, and recommendations/inferences.

## 1. Current consumer: resources, not task enums or energy coefficients

[`efootprint/core/usage/job.py`, current lines 97–138, 374–431](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/core/usage/job.py#L97-L138) defines `JobBase`, `DirectServerJob`, and concrete `Job`. `Job(name, server: Server, data_transferred, data_stored, request_duration, compute_needed, ram_needed)` accepts quantities, not a benchmark filename, `boost_coeff`, technology selector, or `job_type`.

| Input | Current meaning and unit | Current default (hypothesis, not benchmark evidence) |
| --- | --- | --- |
| `name` | String identifying the job | Caller supplied |
| `server` | A `Server` object; serialization references its object ID | Caller supplied |
| `data_transferred` | Upload **plus** download per invocation, information quantity (`B`, `kB`, `MB`) | `150 kB` |
| `data_stored` | Nonnegative net stored-data addition per invocation, **storage** dimension (`B_stored`, `kB_stored`) | `100 kB_stored` |
| `request_duration` | Elapsed duration per invocation (`s`); drives concurrency | `1 s` |
| `compute_needed` | CPU cores held for the request duration (`cpu_core`), **not CPU seconds** | `0.1 cpu_core` |
| `ram_needed` | RAM held per invocation for its duration (`MB_ram`, converted internally to `MB_ram`) | `50 MB_ram` |

The defaults and constructor are [current `job.py` lines 400–431](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/core/usage/job.py#L400-L431). [Custom units](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/constants/custom_units.txt#L1-L65) make `cpu_core`, ordinary information, RAM information, and stored information distinct dimensions; mega is decimal `10^6`. Convert measured MiB using `MiB * 2^20 / 10^6` to MB, then attach the RAM dimension. Plain `MB` is not the current `MB_ram` input type.

### Service/builder seam

[`Service`](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/builders/services/service_base_class.py) is abstract, with `name`, `server: ServerBase`, `base_ram_consumption`, and `base_compute_consumption`. Base resource consumption is **per server instance**, independent of traffic. [`ServiceJob`](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/builders/services/service_job_base_class.py) is abstract and adds `service` to the five job quantities; its server comes from `service.server`. `installable_on()` / `compatible_services()` inspect constructor type annotations, not fuzzy technology strings.

An existing builder example, [`VideoStreaming` / `VideoStreamingJob`](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/builders/services/video_streaming.py), derives `request_duration`, `data_transferred`, `compute_needed`, and `ram_needed` from service parameters. Its CPU coefficient is `static_delivery_cpu_cost` in `cpu_core / (GB/s)`, multiplied by dynamic bitrate; it is **not** a web-app calibration contract and must not be reused for CRUD workloads. It illustrates how a future web-app builder could derive resource needs while keeping provenance.

### How resource demand reaches footprint

1. Journey-step job multiplicities and usage-pattern traffic yield hourly occurrences. `compute_nb_avg_hourly_occurrences(..., request_duration)` converts them into mean concurrent invocations. Network/storage quantities are divided by duration and multiplied by concurrency: [`job.py` lines 177–241](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/core/usage/job.py#L177-L241).
2. Server demand is `sum(job.hourly_avg_occurrences_across_usage_patterns * job.compute_needed)` and the equivalent for RAM. Server/service baselines reduce usable per-instance capacities. Required instances are the **maximum** of CPU-based and RAM-based requirements, not a sum: [`server_base.py` lines 200–287](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/core/hardware/server_base.py#L200-L287).
3. Energy is modeled separately from server idle/active power, PUE, and instance counts; use-phase carbon multiplies by carbon intensity: [`server_base.py` lines 289–329](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/core/hardware/server_base.py#L289-L329). Resource measurements therefore do not need to pretend to be measured joules, and resource ratios do not establish an equal carbon ratio.

### Validation and persistence

Actual current checks: input annotation/type; dimensional homogeneity with declared/default units; negative quantities rejected (zero generally passes this generic check); authorized choices where lists are declared. See [`modeling_object.py` lines 368–445](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/abstract_modeling_classes/modeling_object.py#L368-L445). Server remaining CPU and RAM after utilization/baselines must be **strictly positive**, otherwise `InsufficientCapacityError` ([server guards](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/core/hardware/server_base.py#L245-L267)).

Exporter-side requirements (recommendations beyond those generic checks): finite numeric values; positive invocation count, observation interval and duration; synchronized resource/workload windows; compatible hardware and workload provenance; unknowns remain missing rather than fabricated zero. Use positive duration because exchange calculations divide by it. Nonnegative `data_stored` means deletions belong to storage retention modeling, not negative per-job storage ([field documentation](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/core/usage/job.py#L108-L120)).

`SourceValue(quantity, source, label, confidence, comment)` supports `low`/`medium`/`high` confidence and explicit sources; it otherwise defaults to a hypothesis ([source wrappers](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/abstract_modeling_classes/source_objects.py)). Prefer constructing validated objects and using upstream serialization. The loader explicitly says arbitrary untrusted JSON is not supported as an external schema ([`json_to_system.py` lines 159–188](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/api_utils/json_to_system.py#L159-L188)).

Canonical quantity shape is `{ "value": 0.1, "unit": "cpu_core", "label": "...", "source": "hypothesis" }`; `Job` objects are keyed by ID, have matching `id`, and reference `server` by ID. See [real `simple_system.json` lines 186–220](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/tests/integration_tests/simple_system.json#L186-L220). This is a system persistence example, not a standalone benchmark-upload endpoint.

## 2. Historical ecobenchmark CSV and technology matching

The last pre-removal [`efootprint/builders/services/web_application.py`](https://github.com/Boavizta/e-footprint/blob/dab810742fc4f3fc0d1163804398d28b4607931c/efootprint/builders/services/web_application.py) loads a bundled CSV at module import via `csv.DictReader`. It defines:

- `WebApplication(name, server: Server, technology: ExplainableObject)`, default `technology = "php-symfony"`.
- `WebApplicationJob(name, service: WebApplication, data_transferred, data_stored, implementation_details)`, default `implementation_details = "default"`, `data_transferred = 2.2 MB`, `data_stored = 100 kB`.
- Derived `request_duration`, `compute_needed`, `ram_needed`; **no task-type constructor argument** in this final legacy version.
- Lookup is exact equality on `(row['service'], row['use_case']) == (service.technology.value, implementation_details.value)`. No aliases, language/framework decomposition, database inference, case folding, fallback, or interpolation. `next(...)` takes the first match; missing pairs can raise `StopIteration`. Each selector list is generated independently, so an individually listed technology and use case need not form an available pair. A safe producer must require exactly one row per pair and explicitly validate pair availability. `DictReader` returns strings: any revived adapter must explicitly parse and validate numeric columns rather than treating this historical implementation as a robust interchange spec.

Exact [CSV columns and examples](https://github.com/Boavizta/e-footprint/blob/dab810742fc4f3fc0d1163804398d28b4607931c/efootprint/builders/services/ecobenchmark_analysis/ecobenchmark_data_for_job_defaults.csv):

```text
service,use_case,iterations,http_reqs,nb_requests_in_parallel,avg_ram_in_MB,avg_cpu_cores,avg_ram_per_request_in_MB,avg_cpu_core_per_request
```

Only `service`, `use_case`, `avg_ram_per_request_in_MB`, `avg_cpu_core_per_request` drive the legacy runtime resource lookup. The other columns are analysis intermediates/counts. Technologies: `go-pgx`, `jvm-kotlin-spring`, `node-express-sequelize`, `php-symfony`, `rust-actix-sqlx`. Use cases: `default`, `aggregation-code-side`, `mysql`, `no-index`, `no-pagination`, `orm-loop`; `rust-actix-sqlx/mysql` is absent. These are stack/implementation variants, **not** `DATA_*` task labels.

Example: `go-pgx/default` has `avg_ram_per_request_in_MB = 0.6661532331715496`, `avg_cpu_core_per_request = 0.004639055240432362`. These are historical modeled resources under a one-second duration hypothesis, not validated constants to reuse in new measurements. [Tests](https://github.com/Boavizta/e-footprint/blob/dab810742fc4f3fc0d1163804398d28b4607931c/tests/builders/services/test_web_application.py) mock a row with CPU `0.5`, RAM `512`, and test exact lookup and unsupported-technology rejection.

### Historical analysis assumptions and defects: do not perpetuate

[`ecobenchmark_data_analysis.py`](https://github.com/Boavizta/e-footprint/blob/dab810742fc4f3fc0d1163804398d28b4607931c/efootprint/builders/services/ecobenchmark_analysis/ecobenchmark_data_analysis.py) pins raw input to [original benchmark CSV at `628f86a7e5816a49670b0837fa7507cf2e620531`](https://github.com/Boavizta/ecobenchmark-applicationweb-backend/blob/628f86a7e5816a49670b0837fa7507cf2e620531/results/results/20220628-193500.csv) and computes:

```text
assumed_request_duration = 1 second
assumed_benchmark_duration = 600 seconds
avg_ram_in_MB = (application_ram_avg + database_ram_avg) / 1e6
avg_cpu_cores = application_cpu_avg * 8 + database_cpu_avg * 8
nb_requests_in_parallel = http_reqs * 1 / 600
group means by (service, use_case)
avg_ram_per_request_in_MB = grouped_avg_ram_in_MB / grouped_nb_requests_in_parallel
avg_cpu_core_per_request = grouped_avg_cpu_cores / grouped_nb_requests_in_parallel
```

The source declares application CPU count `24` but actually multiplies **both** CPU averages by database CPU count `8`; TODOs explicitly mark hardware counts, duration, and one-second request duration as assumptions needing checks. It aggregates application **and database** resources into one job demand. If exporting similarly, do not also attach the same DB demand to a separately modeled DB job/server. Legacy RAM units were ordinary `MB`/`GB`; current RAM has its own dimension. This script does not calculate `boost_coeff`, joules/request, or operation-specific factors.

## 3. Task/job types: exact strings, historical status

These names were a plain constants class `JobTypes`, **not** a Python `Enum`. At introduction, [`core/usage/job.py` at `2951b1936d2076a8d9bb8fa206081f86c2fb90fd`](https://github.com/Boavizta/e-footprint/blob/2951b1936d2076a8d9bb8fa206081f86c2fb90fd/efootprint/core/usage/job.py) accepted `job_type=JobTypes.UNDEFINED`; the [original `ecobenchmark_job(...)`](https://github.com/Boavizta/e-footprint/blob/2951b1936d2076a8d9bb8fa206081f86c2fb90fd/efootprint/builders/usage/job_ecobenchmark/jobs_defaults.py) passed it through but did **not** use it in the CSV lookup.

| Requested constant | Exact historical value |
| --- | --- |
| `DATA_READ` | `data_read` |
| `DATA_WRITE` | `data_write` |
| `DATA_LIST` | `data_list` |
| `DATA_SIMPLE_ANALYTIC` | `data_simple_analytic` |
| `TRANSACTION` | `transaction` |
| `NOTIFICATION` | `notification` |

Other constants were `AUTH=auth`, `DATA_STREAM=data_stream`, `TRANSACTION_STRONG=transaction_strong`, `ANALYTIC_DATA_LOADING=analytic_data_loading`, `ANALYTIC_READING_PREPARED=analytic_reading_prepared`, `ANALYTIC_READING_ON_THE_FLY=analytic_reading_on_the_fly`, `ML_RECOMMENDATION=ml_reco`, `ML_LLM=ml_llm`, `ML_DEEPLEARNING=ml_dl`, `ML_REGRESSION=ml_regression`, `ML_CLASSIFIER=ml_classifier`, `UNDEFINED=undefined`. They survived as an unused constants class in [the last legacy `web_application.py`](https://github.com/Boavizta/e-footprint/blob/dab810742fc4f3fc0d1163804398d28b4607931c/efootprint/builders/services/web_application.py). Current main's `Job` has neither that class nor `job_type`. Preserve such labels as benchmark metadata if useful, not as a claimed current consumer discriminator.

## 4. History, moved paths, and authorship audit

| Exact commit | Verified change / attribution |
| --- | --- |
| [`2951b1936d2076a8d9bb8fa206081f86c2fb90fd`](https://github.com/Boavizta/e-footprint/commit/2951b1936d2076a8d9bb8fa206081f86c2fb90fd) | Initial Job + ecobenchmark builders; authored `olivier <odelcroi@gmail.com>` (GitHub `odelcroi`), committed by Vincent Villet. `builders/usage/job_ecobenchmark/jobs_defaults.py`; old resource names `cpu_needed`, `data_upload`, `data_download`, quantities per `u.uj`. Do not apply these obsolete dimensions to current jobs. |
| [`87543463971d4edf6a24c5fd2203a1c6c26f3f11`](https://github.com/Boavizta/e-footprint/commit/87543463971d4edf6a24c5fd2203a1c6c26f3f11) | Vincent Villet, V2.0.0; consumer at `builders/usage/job_ecobenchmark/ecobenchmark_job_builder.py`; pandas lookup takes `.iloc[0]` and rejects empty matches. |
| [`4f6e360210570f853f6d7ff074f83d2076e84232`](https://github.com/Boavizta/e-footprint/commit/4f6e360210570f853f6d7ff074f83d2076e84232) | Vincent Villet; service refactor creates `builders/services/web_application.py`, moves analysis/data into `builders/services/ecobenchmark_analysis/`, deletes old job builder. |
| [`6aacc903d7cf1dcc90886b2537e40a4d39f94af1`](https://github.com/Boavizta/e-footprint/commit/6aacc903d7cf1dcc90886b2537e40a4d39f94af1) | VincentVillet, 2025-12-22; removes WebApplication services and all bundled ecobenchmark analysis/data. |

Current [`suppressed_efootprint_classes.py`](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/api_utils/suppressed_efootprint_classes.py) contains abstract compatibility placeholders only. The [v15 → v16 migration](https://github.com/Boavizta/e-footprint/blob/d69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6/efootprint/api_utils/version_upgrade_handlers.py#L238-L275) deletes WebApplication services and converts their jobs to generic `Job`: network/storage values survive, **duration, CPU and RAM are replaced with `Job.default_values`**. Therefore exporting a legacy WebApplication document and loading it in current e-footprint would not preserve benchmark calibration.

### What can be attributed to Youen Chéné (`youenchene`)

No e-footprint commits/PRs authored by this GitHub identity were found: [repository author-filtered commits API](https://api.github.com/repos/Boavizta/e-footprint/commits?author=youenchene&per_page=100), [author issue/PR search](https://api.github.com/search/issues?q=repo%3ABoavizta%2Fe-footprint%20author%3Ayouenchene&per_page=100), and [all PRs](https://api.github.com/repos/Boavizta/e-footprint/pulls?state=all&per_page=100) returned no matching authored contribution. Local `git log --all --author='[Yy]ouen'` also returned none across advertised refs; `main` and `dev` both point to the pinned current SHA. This does not rule out unlinked identities, deleted forks, or unadvertised/unmerged history. **Do not attribute the consumer implementation to Youen without additional evidence.**

There is, however, substantial verified authorship in the **upstream benchmark repository actually consumed by e-footprint**, not in the consumer itself:

- [`4880b81c0daa7e199e802271ad96672c1f981765`](https://github.com/Boavizta/ecobenchmark-applicationweb-backend/commit/4880b81c0daa7e199e802271ad96672c1f981765), GitHub author `youenchene`: result SQL schema and `results/doc.md`.
- [`3f491cb436618861f5e7db74d4f07a1c479fdfa0`](https://github.com/Boavizta/ecobenchmark-applicationweb-backend/commit/3f491cb436618861f5e7db74d4f07a1c479fdfa0), `youenchene`: first results and `results/ecobenchmark.ipynb` analysis notebook.
- [PR #36, Conformity test](https://github.com/Boavizta/ecobenchmark-applicationweb-backend/pull/36), authored `youenchene`, merge `177d6c014cc64d85e3802671de52130675d79299`.
- [PR #23, three PHP variants](https://github.com/Boavizta/ecobenchmark-applicationweb-backend/pull/23), authored `youenchene`, merge **`628f86a7e5816a49670b0837fa7507cf2e620531`**, exactly the source revision pinned by the legacy e-footprint analysis. This establishes the historical producer/consumer link, not authorship of e-footprint's resource conversion.

## 5. Exportability of our existing mixed-workload observations

Local evidence is pinned at this repository's inspected HEAD `c26d77ed112c617d1689fbd32c6cc61f24eb886c`: [Docker collector](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/collect.py), the current 20-service campaign's [full mixed journey in `runner/scenario.js`](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/runner/scenario.js) selected and snapshotted by [`benchmark/full_services.py`](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/full_services.py#L139-L140), and [analysis validity/warnings](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/analyze_full_services.py). This campaign is distinct from the ten-request [smoke journey](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/service_smoke.js) and the two-host reference [`benchmark/scenario.js`](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/scenario.js), which performs one GET per iteration for `DATA_LIST` or `DATA_SIMPLE_ANALYTIC`. The collector emits cumulative CPU seconds (`total_usage / 1e9`) and sampled cgroup usage bytes. Analysis explicitly sets `sufficient_for_footprint_calibration = False`; one shared-hardware run with a growing DB cannot establish confidence intervals, independent rankings, energy, or calibration factors.

The following are mathematical/experimental-design conclusions from those observations and the current consumer equations, **not a new upstream export schema**:

| Observed/derived datum | Honest export and limitations |
| --- | --- |
| Docker cumulative CPU seconds | Export bracketing deltas separately for app and DB, their scope, sample/window metadata, and overhead caveats. `CPU_seconds / completed_requests` is exploratory **core-seconds per HTTP request**, not `compute_needed` cores. Failed-run observations cannot become valid factors. |
| Average CPU occupancy | `CPU_seconds / elapsed_seconds` is average occupied cores over the measured window. It does not require multiplying by a guessed host core count. Keep this distinct from per-request demand. |
| CPU mapping to a current generic job | If boundaries, CPU scope and mean server duration `d` align: `compute_needed = CPU_seconds / (N * d) cpu_core`. For steady mean arrival rate `N/T`, resulting concurrency is `N*d/T`, reproducing measured average CPU occupancy. This is a **conditional same-workload fit**, not validation or portability; end-to-end k6 latency includes effects outside server execution. A p95 is not the required arithmetic mean. |
| Sampled cgroup memory | Export timestamped bytes, sample count, sampled peak, and explicitly computed time-weighted mean if available. Includes cache; not process RSS, exact peak, per-request allocation, or a measured service idle baseline. Do **not** divide sampled peak by request count or assign it to every concurrent job. |
| Memory mapping to a job | Only a new controlled experiment could separate `base_ram_consumption` from incremental workload RAM. A provisional fit `dynamic_mean_RAM / mean_concurrency` requires that decomposition and valid concurrency; current mixed observations do not establish it. Never charge the same baseline both per-instance and per-request. |
| k6 HTTP bytes | If summary counters include uploaded and downloaded bytes with aligned invocation counts, export their sum per matching HTTP invocation, stating measurement layer and coverage. It does not measure all app↔DB/internal traffic or storage growth. |
| k6 latency | Export observed mean/percentiles in ms (convert mean ms / 1000 for an explicitly qualified seconds estimate). A mixed-run global percentile is not a specific operation's duration; do not infer CPU demand from latency alone. |
| Stored data | Unknown: request payload size is not net durable storage growth including indexes/overhead. Do not silently export an observed zero. |
| Task-specific factors | **Not identifiable** from one aggregate mixed run per service. One resource total is a weighted combination of multiple operation costs plus baselines, with insufficient independent observations to solve them. HTTP timings/tags alone cannot allocate aggregate Docker CPU/RAM. The journey exercises writes, listing/pagination, and statistics; it supplies no isolated `DATA_READ`, `TRANSACTION`, or `NOTIFICATION` calibration. |
| Whole-journey resources | May be retained as one experimental mixed-profile record with exact workload definition and count boundary. A completed iteration of the current campaign's [`runner/scenario.js`](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/runner/scenario.js#L23-L58) performs **672 HTTP requests**: one account creation, 30 list writes, 600 task writes, 31 paginated-list GETs, and ten stats GETs. HTTP-request and successful-journey denominators are different; partial iterations can also contribute requests, so do not assume total requests equal 672 times completed iterations. The separate [`service_smoke.js`](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/service_smoke.js#L54-L95) format performs ten requests (six POSTs, three list GETs, one stats GET) plus sleep/checking; the two-host reference [`benchmark/scenario.js`](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/scenario.js#L24-L36) performs one GET per iteration. Do not conflate these workload formats or present aggregate resources as identical per-operation measurements. |
| Relative/boost coefficients | Exploratory same-hardware, same-workload CPU-service-demand ratios may be reported with named baseline, direction, metric, DB scope and one-run warning. No demonstrated universal language/framework factor, task factor, architectural factor, or single combined CPU/RAM/energy boost can be exported. Current e-footprint does not directly consume a generic `boost_coeff`. |
| Physical energy / carbon | **Unavailable.** CPU time and cgroup memory do not establish joules or emissions. [Scaphandre simulation](https://github.com/Boavizta/ecobenchmark-4-builder-efootprint/blob/c26d77ed112c617d1689fbd32c6cc61f24eb886c/benchmark/scaphandre_sim/generate.py#L1-L39) deliberately synthesizes fixed 40 W package and 10 W DRAM counters. Its output is test-fixture evidence only and must **never** be emitted as measured energy, resource calibration, or production coefficients. |

### Recommended boundary for subsequent implementation (not implemented here)

1. Export a provenance-rich **observation dataset**, explicitly `mixed_workload`, local hardware/container settings, service revision, DB scope/schema, workload hash, elapsed window, counts/errors, units, and validity status. Preserve unknown/missing values and quarantine invalid runs. A new producer schema must be named/versioned separately from the historical upstream CSV.
2. Keep the historical `(service, use_case)` CSV as an optional documented legacy projection only; do not rename `use_case` to a task type, assume current compatibility, invent missing technology rows, or reuse the old 1 s/600 s/8-core assumptions.
3. Before production task/resource factors, collect isolated, repeatable operation workloads, aligned resource/latency windows, idle baselines, app/DB attribution, payload/data-size/concurrency sweeps, and uncertainty. Agree with current e-footprint maintainers whether to instantiate generic `Job` objects or introduce a new service builder.
4. Respect the supplied [local brief](../../.baton-files/brief-evaluer-impact-application-web.md#L79-L122): coefficients alter infrastructure needs for ordinary management/SaaS applications; do not claim validity for hyperscale or AI-specialized systems ([brief scope/limits](../../.baton-files/brief-evaluer-impact-application-web.md#L19-L52)). This is project intent, not evidence that a `boost_coeff` interface currently exists upstream.
