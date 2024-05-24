# Eco benchmark 4 builder e-footprint

## Goal

This project aim to provide data driven builder for [e-footprint project](https://github.com/Boavizta/e-footprint).

e-footprint builder are technical compounds of full user journey modelized within e-footprint python API. It will allow designers to setup language, framework or db in the e-foootprint user journey and see the environnemtal impacts (direct energy or indirect manufacturing impact by saturating existing servers).

The project is the next step of the original [eco-benchmark project](https://github.com/Boavizta/ecobenchmark-applicationweb-backend)


## How does it works?

This repository contains  different benchmarking scenario to try to compare the energy consumption and server saturation for several set of languages, frameworks and db.

The different scenario will be the following, for each set of languages, frameworks and db:

- default, optimised but not extremely.

The repository :
- **IS NOT** a language competition,
- so **DON'T** provide expert/ninja tuning Pull Request, except it's a well known practice.

![Eco Benchmark diagram](eco-benchmark-boavizta.drawio.svg)


## What data we should get from the benchmark ?

To fill a e-footprint builder, we need to gather this data by builder :

- job_type
- technologies
- data_upload
- data_download
- cpu_needed
- ram_needed
- request_duration

Data is input as a set of value and unit in the builder, so all data should go with a unit.

## e-footprint builder scope

This project is here to provide date for the following job types builders :

- DATA_READ
- DATA_WRITE
- DATA_LIST
- DATA_SIMPLE_ANALYTIC
- TRANSACTION
- NOTIFICATION

[See the job model](https://github.com/Boavizta/e-footprint/blob/main/efootprint/core/usage/job.py)

## evaluated technology scope

Available in folder [/service](/service)

Name are built like this :

language-framework[-framework][-framework][-framework]-db

Exemple : 
- node-express-sequelize-mysql
- python-fastapi-pg
- php-symfony-apache2-dev-pg

## Contributing

Everybody is more than welcome to contribute to this benchmark! Please check out the [Contributing guide](CONTRIBUTING.md) for guidelines about how to proceed.

You can also [join us](https://boavizta.org/en/contact) and become a member of the non-profit French association.

## License

The eco-benchmark is released under the [AGPL-3.0 license](LICENSE).
