PYTHON ?= python3
BENCHMARK_ARGS ?=
RUN_ARGS ?=
.DEFAULT_GOAL := help

.PHONY: help benchmark-up benchmark-prepare benchmark-run benchmark-stop test

help:
	@printf '%s\n' 'Targets: benchmark-up benchmark-prepare benchmark-run benchmark-stop test' 'See benchmark/README.md for SSH deployment and configuration.'

benchmark-up:
	$(PYTHON) benchmark/ecobench.py $(BENCHMARK_ARGS) up

benchmark-prepare:
	$(PYTHON) benchmark/ecobench.py $(BENCHMARK_ARGS) prepare

benchmark-run:
	$(PYTHON) benchmark/ecobench.py $(BENCHMARK_ARGS) run $(RUN_ARGS)

benchmark-stop:
	$(PYTHON) benchmark/ecobench.py $(BENCHMARK_ARGS) stop

test:
	$(PYTHON) -m unittest discover -s benchmark -p 'test_*.py' -v
