#!/usr/bin/env bash
set -ex

# Script ran by Github actions for tests
#
# @environment ${ARCH}              The architecture to build. Example: amd64.
# @environment ${DEBIAN_VERSION}    Debian version to build. ('buster' or 'stretch').
# @environment ${ARCH_IMAGE}        What the Docker Hub Image should be tagged as. Example: pihole/pihole:master-amd64-buster

# setup qemu/variables
docker run --rm --privileged multiarch/qemu-user-static:register --reset > /dev/null
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
    --env ARCH="${ARCH}" \
    --env ARCH_IMAGE="${ARCH_IMAGE}" \
    --env DEBIAN_VERSION="${DEBIAN_VERSION}" \
    ${enter} image_pipenv

mkdir -p ".gh-workspace/${DEBIAN_VERSION}/"
echo "${ARCH_IMAGE}" | tee "./.gh-workspace/${DEBIAN_VERSION}/${ARCH}"

TARGET_FILE="./.gh-workspace/${DEBIAN_VERSION}/${ARCH}.json"
echo '{}' | jq ".image=\"${ARCH_IMAGE}\"" > image.json
jq ".debian_version=\"${DEBIAN_VERSION}\"" image.json > image.tmp && mv image.tmp "${TARGET_FILE}"
jq ".arch=\"${ARCH}\"" "${TARGET_FILE}" > image.tmp && mv image.tmp "${TARGET_FILE}"
jq ".docker_hub_repo=\"${DOCKER_HUB_REPO}\"" "${TARGET_FILE}" > image.tmp && mv image.tmp "${TARGET_FILE}"
jq ".docker_hub_image_name=\"${DOCKER_HUB_IMAGE_NAME}\"" "${TARGET_FILE}" > image.tmp && mv image.tmp "${TARGET_FILE}"
jq ".git_branch=\"${GIT_BRANCH}\"" "${TARGET_FILE}" > image.tmp && mv image.tmp "${TARGET_FILE}"
jq ".git_tag=\"${GIT_TAG}\"" "${TARGET_FILE}" > image.tmp && mv image.tmp "${TARGET_FILE}"
jq ".multiarch_image=\"${MULTIARCH_IMAGE}\"" "${TARGET_FILE}" > image.tmp && mv image.tmp "${TARGET_FILE}"
jq ".latest_image=\"${LATEST_IMAGE}\"" "${TARGET_FILE}" > image.tmp && mv image.tmp "${TARGET_FILE}"
# Replace all empty strings with null
jq '(..|select(type=="string")) |= if .=="" then null else . end' "${TARGET_FILE}" image.tmp && mv image.tmp "${TARGET_FILE}"
cat "${TARGET_FILE}"
