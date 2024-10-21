#!/bin/bash

set -xe

# run <service> <use_case>
function run_test() {
  run_id=$(date +%s)
  extra_vars="server_application_host=$SERVER_APPLICATION_HOST"
  extra_vars="$extra_vars server_application_user=$SERVER_APPLICATION_USER"
  extra_vars="$extra_vars server_database_host=$SERVER_DATABASE_HOST"
  extra_vars="$extra_vars server_database_user=$SERVER_DATABASE_USER"
  extra_vars="$extra_vars server_runner_host=$SERVER_RUNNER_HOST"
  extra_vars="$extra_vars server_runner_user=$SERVER_RUNNER_USER"
  ansible-playbook \
    -u debian \
    -i hosts \
    -i inventory-$1 \
    -v \
    site-test-runner.yml \
    --skip-tags install \
    --extra-vars "$extra_vars service=$1 scenario=$2 output_directory=$PWD/results run_id=$run_id"
}

# run <service> <use_case>
function run_init_env() {
  run_id=$(date +%s)
  extra_vars="server_application_host=$SERVER_APPLICATION_HOST"
  extra_vars="$extra_vars server_application_user=$SERVER_APPLICATION_USER"
  extra_vars="$extra_vars server_database_host=$SERVER_DATABASE_HOST"
  extra_vars="$extra_vars server_database_user=$SERVER_DATABASE_USER"
  extra_vars="$extra_vars server_runner_host=$SERVER_RUNNER_HOST"
  extra_vars="$extra_vars server_runner_user=$SERVER_RUNNER_USER"
  ansible-playbook \
    -u debian \
    -i hosts \
    -i inventory-$1 \
    site-init-env.yml \
    --skip-tags install \
    --extra-vars "$extra_vars service=$1 scenario=$2 output_directory=$PWD/results run_id=$run_id"
}

function run() {
  for i in {1..4}; do #was 10
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
    -u debian \
    -i hosts \
    -i inventory-$1 \
    -v \
    site-init-runner.yml \
    --skip-tags install \
    --extra-vars "$extra_vars service=$1 scenario=$2 output_directory=$PWD/results run_id=$run_id"
}


function run_all_services() {
  folder_path=../service
  folder_names=$(find $folder_path -mindepth 1 -maxdepth 1 -type d -exec basename {} \;)
  for folder_name in $folder_names; do
    if [[ $folder_name != *mysql ]]; then #temp patch
      #eval "run $folder_name"
      #run_init_env $folder_name #deploy architecture
      run_init $folder_name INIT #Init account
      run_test $folder_name DATA_WRITE #Run test 1
      run_test $folder_name DATA_LIST #Run test 1
      run_test $folder_name DATA_SIMPLE_ANALYTIC #Run test 1
    fi
  done
}

run_all_services
