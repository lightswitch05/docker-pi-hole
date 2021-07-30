#!/usr/bin/env bash
set -a

# @environment ${DEBIAN_VERSION}          Debian version to build. Defaults to 'buster'.
# @environment ${DOCKER_HUB_REPO}         The docker hub repo to tag images for. Defaults to 'pihole'.
# @environment ${DOCKER_HUB_IMAGE_NAME}   The name of the resulting image. Defaults to 'pihole'.

GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD | sed "s/\//-/g")
GIT_TAG=$(git describe --tags --exact-match 2> /dev/null || true)

DEFAULT_DEBIAN_VERSION="buster"

if [[ -z "${ARCH}" ]]; then
    ARCH="amd64"
    echo "Defaulting arch to ${ARCH}"
fi

if [[ -z "${DEBIAN_VERSION}" ]]; then
    DEBIAN_VERSION="${DEFAULT_DEBIAN_VERSION}"
    echo "Defaulting DEBIAN_VERSION to ${DEBIAN_VERSION}"
fi

if [[ -z "${DOCKER_HUB_REPO}" ]]; then
    DOCKER_HUB_REPO="pihole"
    echo "Defaulting DOCKER_HUB_REPO to ${DOCKER_HUB_REPO}"
fi

if [[ -z "${DOCKER_HUB_IMAGE_NAME}" ]]; then
    DOCKER_HUB_IMAGE_NAME="pihole"
    echo "Defaulting DOCKER_HUB_IMAGE_NAME to ${DOCKER_HUB_IMAGE_NAME}"
fi

BASE_IMAGE="${DOCKER_HUB_REPO}/${DOCKER_HUB_IMAGE_NAME}"

GIT_TAG_OR_BRANCH="${GIT_TAG:-$GIT_BRANCH}"
MULTIARCH_IMAGE="${BASE_IMAGE}:${GIT_TAG_OR_BRANCH}"



# To get latest released, cut a release on https://github.com/pi-hole/docker-pi-hole/releases (manually gated for quality control)
latest_tag='UNKNOWN'
if ! latest_tag=$(curl -sI https://github.com/pi-hole/docker-pi-hole/releases/latest | grep --color=never -i Location: | awk -F / '{print $NF}' | tr -d '[:cntrl:]'); then
    print "Failed to retrieve latest docker-pi-hole release metadata"
fi

TARGET_FILE="./build-vars.json"
echo '{}' | jq ".docker_hub_repo=\"${DOCKER_HUB_REPO}\"" > "${TARGET_FILE}"
jq ".docker_hub_image_name=\"${DOCKER_HUB_IMAGE_NAME}\"" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
jq ".git_branch=\"${GIT_BRANCH}\"" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
jq ".git_tag=\"${GIT_TAG}\"" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
jq ".git_branch_or_tag=\"${GIT_TAG_OR_BRANCH}\"" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
jq ".latest_tag=\"${latest_tag}\"" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
jq ".default_debian_version=\"${DEFAULT_DEBIAN_VERSION}\"" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"

for target in ${ARCH}
do
    jq ".archs += [\"${target}\"]" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
done

for target in ${DEBIAN_VERSION}
do
    jq ".debian_versions += [\"${target}\"]" "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
done

# Replace all empty strings with null
jq '(..|select(type=="string")) |= if .=="" then null else . end' "${TARGET_FILE}" > "${TARGET_FILE}".tmp && mv "${TARGET_FILE}".tmp "${TARGET_FILE}"
cat "${TARGET_FILE}"

set +a
