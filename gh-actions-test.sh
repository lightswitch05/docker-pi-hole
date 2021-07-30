#!/usr/bin/env bash
set -ex

# Script ran by Github actions for tests
#
# @environment ${DEBIAN_VERSION}    Debian version(s) to build. ('buster' or 'stretch' or 'buster stretch')
# @environment ${ARCH}              What architecture(s) to build. ('amd64' or 'arm64' or 'amd64 arm64'

# setup qemu/variables
. gh-actions-vars.sh

if [[ "$1" == "enter" ]]; then
    enter="-it --entrypoint=sh"
fi

# generate and build dockerfile
docker build --tag image_pipenv --file Dockerfile_build .
docker run --rm \
    --volume /var/run/docker.sock:/var/run/docker.sock \
    --volume "$(pwd):/$(pwd)" \
    --workdir "$(pwd)" \
    --env PIPENV_CACHE_DIR="$(pwd)/.pipenv" \
    ${enter} image_pipenv
