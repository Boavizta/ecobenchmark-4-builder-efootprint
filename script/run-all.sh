#!/bin/bash

set -xe

# run <service> <use_case>
function run_once() {
  run_id=$(date +%s)
  extra_vars="server_application_host=$SERVER_APPLICATION_HOST"
  extra_vars="$extra_vars server_application_user=$SERVER_APPLICATION_USER"
  extra_vars="$extra_vars server_database_host=$SERVER_DATABASE_HOST"
  extra_vars="$extra_vars server_database_user=$SERVER_DATABASE_USER"
  extra_vars="$extra_vars server_runner_host=$SERVER_RUNNER_HOST"
  extra_vars="$extra_vars server_runner_user=$SERVER_RUNNER_USER"
  ansible-playbook \
    -i script/hosts \
    -i script/inventory-$1 \
    script/site.yml \
    --skip-tags install \
    --extra-vars "$extra_vars service=$1 scenario=$2 output_directory=$PWD/results run_id=$run_id"
}

function run() {
  for i in {1..10}; do
    run_once $1 $2
  done
}


function run_init() {
  run_id=$(date +%s)
  extra_vars="server_application_host=$SERVER_APPLICATION_HOST"
  extra_vars="$extra_vars server_application_user=$SERVER_APPLICATION_USER"
  extra_vars="$extra_vars server_database_host=$SERVER_DATABASE_HOST"
  extra_vars="$extra_vars server_database_user=$SERVER_DATABASE_USER"
  extra_vars="$extra_vars server_runner_host=$SERVER_RUNNER_HOST"
  extra_vars="$extra_vars server_runner_user=$SERVER_RUNNER_USER"
  ansible-playbook \
    -i script/hosts \
    -i script/inventory-$1 \
    script/site.yml \
    --skip-tags install \
    --extra-vars "$extra_vars service=$1 scenario=$2 output_directory=$PWD/results run_id=$run_id"
}


function run_all_services() {
  folder_path=../service
  folder_names=$(find $folder_path -mindepth 1 -maxdepth 1 -type d -exec basename {} \;)
  for folder_name in $folder_names; do
    if [[ $folder_name != *mysql ]]; then #temp patch
      #eval "run $folder_name"
      run_init $folder_name INIT
      run $folder_name DATA_WRITE
      run $folder_name DATA_LIST
      run $folder_name DATA_SIMPLE_ANALYTIC
    fi
  done
}

run_all_services
