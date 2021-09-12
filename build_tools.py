#!/usr/bin/env python3

import argparse
import json
import logging
import os
import subprocess
import typing
import urllib.request

from dotenv import dotenv_values

DEBIAN_VERSIONS = [
    'bullseye',
    'buster',
    'stretch'
]
ARCH_MAP = {
    'amd64': 'linux/amd64',
    'armel': 'linux/arm/v6',
    'armhf': 'linux/arm/v7',
    'arm64': 'linux/arm64/v8',
    'i386': 'linux/386'
}
BAKE_CONFIG_FILENAME = 'docker-bake.hcl'
DEFAULT_DEBIAN_VERSION = 'buster'
DEFAULT_DOCKER_HUB_REPO = 'pihole'
DOCKER_HUB_IMAGE_NAME = 'pihole'
CACHE = {}


def main():
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), None))
    write_bake_config(args.arch, args.debian)
    if args.command == 'build':
        build(args.arch, args.debian, args.no_cache)
    elif args.command == 'test':
        test(args.arch, args.debian)
    else:
        print("Missing build command, see options with --help")


def parse_args():
    parser = argparse.ArgumentParser(description='Pi-hole build tools')
    parser.add_argument('command', choices=['build', 'test'], nargs='?', help='The main command action to take')
    parser.add_argument('--arch', choices=ARCH_MAP.keys(), default=ARCH_MAP.keys(), nargs='*')
    parser.add_argument('--debian', choices=DEBIAN_VERSIONS, default=DEBIAN_VERSIONS, nargs='*')
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--log-level', choices=['debug', 'info', 'error'], default='info', nargs='?')
    return parser.parse_args()


def git_branch() -> str:
    if 'git_branch' in CACHE:
        return CACHE['git_branch']
    process = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                             capture_output=True, check=True, universal_newlines=True)
    branch = process.stdout.replace('/', '-').replace('\n', '')
    CACHE['git_branch'] = branch
    return branch


def git_tag() -> typing.Optional[str]:
    if 'git_tag' in CACHE:
        return CACHE['git_tag']
    process = subprocess.run(['git', 'describe', '--tags', '--exact-match'],
                             capture_output=True, check=False, universal_newlines=True)
    if process.returncode != 0:
        return None
    tag = process.stdout.replace('\n', '')
    CACHE['git_tag'] = tag
    return tag


def latest_release_tag():
    if 'latest_release_tag' in CACHE:
        return CACHE['latest_release_tag']
    with urllib.request.urlopen('https://api.github.com/repos/pi-hole/docker-pi-hole/releases/latest') as socket:
        raw_response = socket.read().decode('utf-8')
        encoded_response = json.loads(raw_response)
        if 'tag_name' in encoded_response:
            CACHE['latest_release_tag'] = encoded_response['tag_name']
            return encoded_response['tag_name']
    return 'UNKNOWN'


def docker_hub_username():
    if 'DOCKER_HUB_REPO' in os.environ:
        return os.environ['DOCKER_HUB_REPO']
    return DEFAULT_DOCKER_HUB_REPO


def docker_hub_image_name():
    if 'DOCKER_HUB_IMAGE_NAME' in os.environ:
        return os.environ['DOCKER_HUB_IMAGE_NAME']
    return DOCKER_HUB_IMAGE_NAME


def get_branch_or_tag():
    tag = git_tag()
    return tag if tag else git_branch()


def pihole_versions() -> str:
    if 'pihole_versions' in CACHE:
        return CACHE['pihole_versions']
    dot = os.path.abspath('.')
    config = dotenv_values('{}/VERSIONS'.format(dot))
    ftl_version = config['FTL_VERSION'].replace('/', '-')
    CACHE['pihole_versions'] = ftl_version
    return ftl_version


def write_bake_config(arches:  typing.List[str], debian_versions: typing.List[str]) -> None:
    platforms = []
    pihole_version = pihole_versions()
    for arch in arches:
        if arch not in ARCH_MAP:
            raise ValueError(f'{arch} is not in the list of supported {ARCH_MAP}')
        platforms.append(ARCH_MAP[arch])
    with open(BAKE_CONFIG_FILENAME, 'w') as file:
        for debian_version in debian_versions:
            platforms_str = str(platforms).replace("'", '"')
            tags_str = str(get_image_tags(arches, debian_version)).replace("'", '"')
            file.write(f'target "{target_name(arches, debian_version)}" {{\n')
            file.write(f"     platforms = {platforms_str}\n")
            file.write(f"     tags = {tags_str}\n")
            file.write("      args = {\n")
            file.write(f'          PIHOLE_BASE = "debian:{debian_version}-slim"\n')
            file.write(f'          PIHOLE_VERSION = "{pihole_version}"\n')
            file.write("      }\n")
            file.write("}\n\n")
            if len(arches) > 1:
                for arch in arches:
                    platform = ARCH_MAP[arch]
                    tags_str = str(get_image_tags([arch], debian_version)).replace("'", '"')
                    file.write(f'target "{target_name([arch], debian_version)}" {{\n')
                    file.write(f'     inherits = ["pihole-{debian_version}"]\n')
                    file.write(f"    tags = {tags_str}\n")
                    file.write(f'    platforms = ["{platform}"]\n')
                    file.write("}\n\n")


def get_image_tags(arches: typing.List[str], debian_version: str) -> list:
    tags = []
    base = f"docker.io/{docker_hub_username()}/{docker_hub_image_name()}"
    release = f"{base}:{get_branch_or_tag()}"
    if len(arches) == 1:
        tags.extend(single_arch_image_tags(release, arches[0], debian_version))
        return tags
    tags.extend(multi_arch_image_tags(release, debian_version))
    return tags


def single_arch_image_tags(tag_base: str, arch: str, debian_version: str) -> typing.List[str]:
    # single image - not multi-arch
    tags = [f"{tag_base}-{arch}-{debian_version}"]
    if debian_version == DEFAULT_DEBIAN_VERSION:
        tags.append(f"{tag_base}-{arch}")
    return tags


def multi_arch_image_tags(tag_base: str, debian_version: str) -> typing.List[str]:
    tags = [f"{tag_base}-{debian_version}"]
    if debian_version == DEFAULT_DEBIAN_VERSION:
        tags.append(f"{tag_base}")
    if latest_release_tag() == get_branch_or_tag():
        tags.append(f"{tag_base}:latest")
    # TODO if doing a tagged version build, setup generic version tags here
    return tags


def target_name(arch: typing.List[str], debian_version: str) -> str:
    if len(arch) > 1:
        return f'pihole-{debian_version}'
    return f'pihole-{arch[0]}-{debian_version}'


def target_names(arch: typing.List[str], debian_version: typing.List[str]) -> typing.List[str]:
    targets = []
    for debian in debian_version:
        targets.append(target_name(arch, debian))
    return targets


def build(arch: typing.List[str], debian_versions: typing.List[str], no_cache: bool):
    subprocess.run(['docker', 'buildx', 'create', '--name', 'pihole-build'], check=False, capture_output=False,
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    subprocess.run(['docker', 'buildx', 'use', 'pihole-build'], check=True, capture_output=False)
    targets = target_names(arch, debian_versions)
    build_command = ['docker', 'buildx', 'bake', '--file', BAKE_CONFIG_FILENAME]
    if len(arch) == 1:
        build_command.append('--load')
    if no_cache:
        build_command.append('--no-cache')
    build_command.extend(targets)
    logging.info('Build command: %s', ' '.join(build_command))
    subprocess.run(build_command, check=True, universal_newlines=True)


def test(arches: typing.List[str], debian_versions: typing.List[str]):
    run_test(list(arches)[0], list(debian_versions)[0])


def run_test(arch: str, debian_version: str):
    image = get_image_tags([arch], debian_version)[0]
    cmd = ['pytest', '-vv']
    logging.info('Test command: %s', ' '.join(cmd))
    process = subprocess.run(cmd,
                             capture_output=False, check=True, universal_newlines=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    print(process.stdout)
    print(process.stderr)


if __name__ == '__main__':
    main()

