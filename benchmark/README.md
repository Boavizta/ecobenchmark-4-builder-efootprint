# Benchmark harness

One lifecycle for local Lima VMs and dedicated Linux servers over SSH. The controller
requires Python 3.9+ on macOS or Linux; no Python packages or host Docker daemon.
Only the Go/PostgreSQL reference service and two read workloads are integrated so far.

The database image is pinned to PostgreSQL 18.6. PostgreSQL 18 uses a versioned
data directory, so the Compose volume is mounted at `/var/lib/postgresql` rather
than `/var/lib/postgresql/data`. Existing PostgreSQL 14 data cannot be reused
directly: back it up and migrate with dump/restore or `pg_upgrade` into a separate
volume before using PostgreSQL 18. Changing an image tag does not migrate data.

## Local VMs

Requires Apple Silicon macOS, Lima 2.0+ (`brew install lima`), and an external volume
mounted at `/Volumes/Extension`.

```sh
python3 benchmark/ecobench.py up
python3 benchmark/ecobench.py prepare
python3 benchmark/ecobench.py run
python3 benchmark/ecobench.py run --scenario DATA_SIMPLE_ANALYTIC --duration 60 --repeat 3
python3 benchmark/ecobench.py stop
```

VM disks, container images, and Lima state live in
`/Volumes/Extension/ecobench-vms` via `LIMA_HOME`. Lima also keeps a shared download
cache in `~/Library/Caches/lima` (hardcoded by Lima on macOS); this is not an active
VM disk. Override the VM storage with the global
`--storage /path` argument **before** the subcommand. Never disconnect the external
volume while VMs are running. `stop` preserves disks. `status` lists their state.
Initial provisioning needs Internet access and may take several minutes.

Two native ARM64 Linux VMs use Apple's virtualization framework:

| VM | Allocation | Role |
| --- | --- | --- |
| ecobench-target | 2 CPUs, 3 GiB RAM, 20 GiB sparse disk | App (1 CPU/512 MiB) + PostgreSQL (1 CPU/1 GiB) |
| ecobench-runner | 2 CPUs, 3 GiB RAM, 20 GiB sparse disk | k6 |

They communicate over Lima's private `user-v2` network. No writable host mounts,
host Docker contexts, or host port forwards are created. The target API is reachable
from other VMs on that Lima network; do not attach untrusted workloads to it.
Only these named VMs and the `ecobench` Compose project are managed by this tool.

## Dedicated Linux servers over SSH

Rent/provision **two existing Linux hosts**: a target (application + database) and a
separate load generator. The CLI does not rent servers, manage OVH accounts, change
firewalls, or power off remote machines. Native ARM64 and x86-64 builds are supported.
Keep SSH configuration and credentials on the controller, outside the repository.

1. Configure key-based SSH access and verify each host key using a trusted source
   such as the provider's console. Establish trusted entries in `known_hosts` before
   running automation; unknown/changed keys and password prompts are rejected.
2. Use a trusted account with noninteractive root privileges (`sudo -n`). Docker
   and bootstrap administration are root-equivalent access. No passwords are stored
   or sent by the harness, and SSH agent forwarding is disabled.
3. Copy `benchmark/hosts.example.json` to `benchmark/hosts.local.json` (ignored by Git),
   or keep the hosts file outside the repository. Replace hostnames, addresses,
   and identity paths. For example:

```json
{
  "target": {"host": "benchmark@target.example.com", "address": "10.0.0.10"},
  "runner": {"host": "benchmark@load.example.com"},
  "ssh_config": "~/.ssh/config"
}
```

`host` accepts a hostname, IPv4 address, SSH alias, or `user@hostname`. Each host
can optionally specify `port` and `identity_file`. SSH config supports aliases,
ProxyJump, and custom known-hosts files; command-line security options remain enforced.
Paths expand `~`; relative paths are resolved against the hosts file's directory.
The active hosts file and `hosts.local.json` are excluded from source uploads/hashes.
Keep private keys outside all project source directories.

`target.address` must be an IPv4 address **assigned to the target and reachable from
the runner**. Prefer OVH vRack/private networking if available and configured. The
API binds only to this address, port 8080. PostgreSQL is never published to the host.
Allow port 8080 only from the load generator using your provider/host firewall.
Docker-published ports can bypass UFW rules: use an appropriate upstream firewall
or Docker-aware filtering. The harness does not install firewall rules for you.

Run (global options go **before** the subcommand):

```sh
# Optional, explicit one-time system changes on Ubuntu 24.04/26.04:
python3 benchmark/ecobench.py --backend ssh --hosts benchmark/hosts.local.json bootstrap

# Check SSH/sudo, tools, Docker/Compose, separate host identities, and bind address:
python3 benchmark/ecobench.py --backend ssh --hosts benchmark/hosts.local.json doctor

# Upload source and build/pull images; no package installation:
python3 benchmark/ecobench.py --backend ssh --hosts benchmark/hosts.local.json prepare

python3 benchmark/ecobench.py --backend ssh --hosts benchmark/hosts.local.json run --duration 60 --repeat 3
python3 benchmark/ecobench.py --backend ssh --hosts benchmark/hosts.local.json stop
```

`bootstrap` installs Docker/Compose and missing prerequisites and enables Docker on
both hosts. It does not upgrade a working Docker installation. On other Linux
distributions, install Docker Engine + Compose v2, Python 3, curl, tar, iproute2,
procps, and util-linux manually, then run `doctor`. Locking requires `flock` and
`sudo` even before bootstrap (present on normal supported Ubuntu installations).

`prepare` transfers a source archive with **scp** to `/var/tmp/ecobench` on each host
and builds the application on the target. Commands and resource streaming use
**ssh**, with per-argument shell quoting, strict host-key verification, bounded
connection attempts, and keepalives. Regular experiments never reinstall packages.

`stop` in SSH mode removes only the benchmark project's containers/volume and
labelled k6 containers; it does **not** stop Docker, delete images, or shut down either
server. It requires a previous `prepare` (the Compose file must exist). Hosts and
their Docker caches remain ready for subsequent runs. `status` checks prerequisites
and displays running containers without changing them. Remote commands should be
used only on machines reserved for experiments, not production servers.

## Lifecycle

`prepare` copies the current source into both hosts, builds the Go/PostgreSQL
reference implementation natively, and pulls database/k6 images. Re-run it after
source changes. The separate Dockerfile avoids changing the historical service's
hardcoded AMD64 build. Existing service implementations remain intact. Re-running
`prepare` is required after source changes; stale source is rejected before database reset.

Each `run` repetition resets the benchmark database volume, loads versioned schema
and deterministic seed data (1 account, 30 lists, 600 tasks), waits for readiness,
validates a response, warms up, then measures a constant-arrival-rate workload.
The database reset deletes **only this benchmark project's database**. Read workloads
currently supported: `DATA_LIST` and `DATA_SIMPLE_ANALYTIC`. One iteration is one
HTTP request. Writes, mixed journeys, additional services, saturation sweeps, and
e-footprint exports are follow-up work, not yet implemented.

Defaults: 10 requests/s, 10-second warm-up, 30-second measurement, one repetition.
Use `--rate`, `--warmup`, `--duration`, and `--repeat` to change these. Responses must
be HTTP 2xx with nonempty JSON arrays (the historical Go list endpoint returns 201).
Failed checks, >=1% HTTP failures,
p95 >=1 second, or dropped iterations fail the run. These smoke checks are **not**
a replacement for the full API contract tests in `test/`.

`results/<unique-run-id>/` contains:

- `metadata.json`: success/failure, configuration, source hashes, Git state,
  actual image IDs/digests, host specifications, execution backend, and measurement timestamps.
- `resources.jsonl`: approximately 1 Hz cumulative CPU, sampled memory, and
  container-network counters for both application and database.
- `k6-summary.json`: latency, HTTP errors, throughput, and transfer totals.
- `validation.json` / `warmup.json`: separate pre-measurement k6 summaries.
- `summary.json`: CPU deltas and CPU-seconds per successful HTTP request, plus
  peak sampled cgroup memory. Written only for a successful measured run.
- `compose.log`: application and database logs, including on failure.
- `validation.log`, `warmup.log`, `measurement.log`: k6 console output for each phase reached.
- `collector.log`: resource collector / transport diagnostics.

Cleanup runs on success, exceptions, and Ctrl-C; abrupt host termination cannot
guarantee cleanup. The next run resets the project. Host-wide remote `flock` leases
on **both hosts** prevent independent controllers/users from running experiments or
changing deployment simultaneously, even with different inventories or backends.
Lima mode additionally uses a local storage lock. Locks release on normal exit or
connection loss; detected lock loss blocks further remote commands. If the controller
crashes or the network fails, inspect lingering collectors/containers before restarting;
locks are not a distributed recovery system. A failed repetition stops the
campaign; it is not silently retried or averaged away.
Cleanup failures are recorded in metadata and cause a nonzero exit, even if the
measured workload passed its thresholds. Optional phase artifacts are fetched only
for phases that started; already collected measurement summaries are not overwritten.

## Interpretation and limitations

**Lima runs are virtualized resource/performance experiments, not physical energy
measurements.** Both VMs share the same Mac CPU, cooling, memory, and external
storage. Separate guests isolate software environments, not physical resources.
Close competing workloads and keep the machine plugged in. Results are not directly
comparable with dedicated Linux hardware, x86 builds, or historical measurements.

For SSH campaigns, prefer bare-metal dedicated servers and record hardware, thermal
conditions, OS, topology, and background activity. SSH itself does not establish
that the host is dedicated or noise-free. Keep CPU/memory allocations and load
generator placement consistent between comparisons. Energy collection is not
implemented in either backend, even if the server has RAPL sensors.

Energy is explicitly unavailable (`joules: null`). Do not infer whole-machine energy
or environmental impact from guest CPU time. Memory means sampled cgroup usage,
including cache; it is not RSS or guaranteed to catch short-lived peaks. CPU deltas
include small k6 startup/stop overhead between collector samples. Network counters
include stack overhead; use k6 totals for HTTP-level bytes. Warm-up and measured
requests are separate; datasets are recreated between repetitions, not between them.

Image version tags are currently bootstrapping defaults, **not a digest-locked
reference campaign**. Exact resolved images are recorded. The Ubuntu base and
provisioned apt packages may evolve. Establish a digest/package lock before publishing
reference comparisons. No dashboard or background energy agent is installed.

## Scaphandre v1.0.3: simulated RAPL integration test

The previous benchmark campaigns contain **no Scaphandre energy measurements**.
The standalone test below validates the actual Scaphandre Linux x86-64 sensor and
JSON exporter against generated counter files. It is not yet a synchronized energy
collector for the Lima/SSH or full-service benchmark workflows above.

```sh
# Run on the actual target to report readable RAPL capability (no installation).
python3 benchmark/scaphandre.py doctor
# On this Mac, run an isolated amd64 container with synthetic RAPL inputs.
python3 benchmark/scaphandre.py simulate --duration 15 --output results/scaphandre-simulation
```

The official `hubblo/scaphandre:1.0.3` amd64 image is pinned by digest and checked
against source revision `b64443c447e24f25947111ec8611449f213eb0a5`. Upstream's
v1.0.3 OCI release retains a `1.0.2` executable/Cargo version string; both are recorded,
not silently confused. See the [release](https://github.com/hubblo-org/scaphandre/releases/tag/v1.0.3)
and [compatibility requirements](https://hubblo-org.github.io/scaphandre-documentation/compatibility.html).

Simulation supplies fake CPU topology, an empty module inventory, and monotonically
increasing fake RAPL energy counters representing **40 W package + 10 W DRAM**.
The counter generator runs inside Linux and writes to tmpfs, not the Mac shared
filesystem; this avoids inconsistent counter reads during host-file replacement.
The module fixture also avoids an upstream procfs 0.15 parsing failure on Docker
Desktop kernel module refcounts. A simulation-only `LD_PRELOAD` adapter redirects
reads of `/proc/cpuinfo` and `/proc/modules` to the fixtures. It leaves the upstream
Scaphandre binary and the host `/proc` unchanged. This is x86 userspace emulation on Apple Silicon,
not an Intel CPU performance model or physical meter. The container has no network,
no added capabilities, no host PID namespace, and read-only sensor fixtures.
Its only temporary workspace is a 64 MiB tmpfs, needed by x86 emulation.

Outputs preserve `scaphandre.json`, `synthetic-counters.jsonl`, fixture files,
collector logs, pinned image provenance, and a normalized `summary.json`.
All simulated reports have `simulation=true`, `measured_energy_available=false`,
`joules=null`; computed values are stored separately as `simulated_joules`.
The parser converts **microwatts** to watts, ignores startup/no-sensor placeholders,
and integrates only the host aggregate (never double-counting sockets/domains).
Neither simulated joules nor process power allocations are physical measurements.
Real collection requires a compatible RAPL target and a separately authorized run;
it cannot be reconstructed for historical benchmark campaigns.

## Service compatibility smoke benchmarks

With a local Docker daemon, run one short mixed write/list/statistics benchmark
against every implemented service image:

```sh
python3 benchmark/smoke_services.py --output results/service-smoke
# Rebuild and rerun only a failed service, preserving earlier attempts:
python3 benchmark/smoke_services.py --service go-pgx-pg --output results/service-smoke
```

Each service gets a fresh disposable PostgreSQL or MySQL database on a uniquely
named Docker network. Only the application's healthcheck port is exposed, on
localhost. Containers and their anonymous volumes are removed after each run;
existing databases, Compose projects, and volumes are not touched. Builds use
the service's real Dockerfile and runtime configuration from its Compose file.

The default is 10 seconds / 1 VU with strict HTTP and response-content checks,
including empty lists, persisted tasks, pagination, and fractional statistics.
Persisted task IDs, names, and descriptions must match the preceding writes.
`status.json` preserves every attempt, `summary.md` shows the latest status, and
per-attempt directories contain build/application/database/k6 logs and metrics.
Each attempt also saves its scenario and SHA-256 hash. The command exits nonzero
if any selected service fails. Do not run concurrent processes against the same
output directory; use separate directories for independent batches.
`ruby-rails-pg` is the Rails/PostgreSQL implementation adapted from upstream PR #37.
Only `ruby-ror-mysql` is excluded: that directory still contains no implementation.

These are **local functional load checks**, not comparable performance or energy
measurements. They are separate from the Lima/SSH reference benchmark lifecycle.
They do not replace exhaustive API conformance tests.

## Full local service inventory and one-run measurements

```sh
# Read-only inventory: every branch and PR, including merged/closed PRs.
python3 benchmark/inventory_services.py --output results/full-run/inventory
# Exactly one timed run per implemented HTTP service; no automatic retries.
python3 benchmark/full_services.py --output results/full-run
# Derive recaps and optionally bundle raw evidence; this runs no benchmark.
python3 benchmark/analyze_full_services.py results/full-run --bundle results/full-run.zip
```

The full local runner uses the original `runner/scenario.js` mixed journey,
2 VUs for 60 seconds, sequentially. Each service gets fresh PostgreSQL/MySQL
containers and the same untimed API validation/data preparation (2 accounts,
25 lists, 3 tasks). Both application and database are limited to 1 CPU / 1 GiB.
Validation checks empty/populated lists, unchanged task content and ownership,
fractional statistics, and zero-based 23-list pagination. The database must expose
only the shared `account`, `list`, and `task` tables; actual columns/indexes are saved.

`recap.md` and `status.json` are updated after every service. Per-service directories
preserve Docker build/application/database logs, `validation.json`, `schema.json`,
the workload snapshot, raw `k6-summary.json`, approximately 1 Hz `resources.jsonl`,
and normalized `summary.json` plus image/source/hardware metadata. CPU is cumulative
cgroup time; memory is sampled cgroup usage (including cache), not process RSS.
The collector connects to the active local Unix-socket Docker context.

Existing run manifests are refused rather than overwritten. A failed service is
reported, not silently rerun. An unsuccessful validation receives no timed run.
`usable=true` means a technically valid **local exploratory observation**, not an
e-footprint calibration or energy result. One run has no confidence interval;
hardware is shared and the mixed workload grows the database as it runs. Do not
rank frameworks or populate hardware-independent footprint factors from this alone.
The two-host Lima/SSH reference workflow above remains separate and Go-only.
The analyzer adds `analysis.md`, `analysis.json`, and `recap.csv` without modifying
the raw per-service measurements. Failed runs retain their counters but never
receive a usable per-request footprint factor.

## Tests

```sh
python3 -m unittest discover -s benchmark -p 'test_*.py' -v
```

Opt-in integration tests exercise real SSH/SCP against the **local Lima VMs only**,
including verified host keys, repeated runs, cleanup, and lock contention. They do
not connect to OVH or use your cloud credentials. Start the VMs first:

```sh
python3 benchmark/ecobench.py up
ECOBENCH_LIMA_SSH_TEST=1 python3 -m unittest discover -s benchmark -p test_ssh_integration.py -v
python3 benchmark/ecobench.py stop
```

For custom VM storage, also set `LIMA_HOME` when invoking the integration tests.
