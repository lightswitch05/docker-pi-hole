#!/usr/bin/env python3
""" Dockerfile.py - generates and build dockerfiles

Usage:
  Dockerfile.py [-v] [-t] [--no-build] [--no-cache] [--fail-fast]

Options:
    --no-build           Skip building the docker images
    --no-cache           Build without using any cache data
    --fail-fast          Exit on first build error
    -v                   Print docker's command output     [default: False]
    -t                   Print docker's build time         [default: False]

Examples:
"""
import json
import typing
from docopt import docopt
import os
import sys
import subprocess
from dotenv import dotenv_values

FTL_VERSION: typing.Optional[str] = None
BUILD_VARS: typing.Optional[dict] = None
BAKE_CONFIG_FILE = 'docker-bake.hcl'
ARCH_MAP = {
    "amd64": "linux/amd64",
    "armel": "linux/arm/v6",
    "armhf": "linux/arm/v7",
    "arm64": "linux/arm64/v8",
    "i386": "linux/386"
}


def read_pihole_versions():
    global FTL_VERSION
    dot = os.path.abspath('.')
    config = dotenv_values('{}/VERSIONS'.format(dot))
    FTL_VERSION = config['FTL_VERSION'].replace('/', '-')


def read_build_vars():
    global BUILD_VARS
    with open('build-vars.json', 'r') as file:
        contents = file.read()
    BUILD_VARS = json.loads(contents)


def write_bake_config(archs: list, debian_version: str) -> None:
    platforms = []
    for arch in archs:
        if arch not in ARCH_MAP:
            raise ValueError(f'{arch} is not in the list of supported {ARCH_MAP}')
        platforms.append(ARCH_MAP[arch])
    with open(BAKE_CONFIG_FILE, 'w') as file:
        platforms_str = str(platforms).replace("'", '"')
        tags_str = str(get_image_tags(archs, debian_version)).replace("'", '"')
        file.write('target "pihole-multiarch" {\n')
        file.write(f"     platforms = {platforms_str}\n")
        file.write(f"     tags = {tags_str}\n")
        file.write("      args = {\n")
        file.write(f'          PIHOLE_BASE = "debian:{debian_version}-slim"\n')
        file.write("      }\n")
        file.write("}\n\n")
        for arch in archs:
            platform = ARCH_MAP[arch]
            tags_str = str(get_image_tags([arch], debian_version)).replace("'", '"')
            file.write(f'target "pihole-{arch}-{debian_version}" {{\n')
            file.write('     inherits = ["pihole-multiarch"]\n')
            file.write(f"    tags = {tags_str}\n")
            file.write(f'    platforms = ["{platform}"]\n')
            file.write("}\n\n")


def get_image_tags(archs: list, debian_version: str) -> list:
    tags = []
    base = f"docker.io/{BUILD_VARS['docker_hub_repo']}/{BUILD_VARS['docker_hub_image_name']}"
    release = f"{base}:{BUILD_VARS['git_branch_or_tag']}"
    if len(archs) == 1:
        # single image - not multi-arch
        tags.append(f"{release}-{archs[0]}-{debian_version}")
        if debian_version == BUILD_VARS['default_debian_version']:
            tags.append(f"{release}-{archs[0]}")
        return tags
    # more then 1 arch - so this is multi-arch image
    tags.append(f"{release}-{debian_version}")
    if debian_version == BUILD_VARS['default_debian_version']:
        tags.append(f"{release}")
    if BUILD_VARS['latest_tag'] == BUILD_VARS['git_branch_or_tag']:
        tags.append(f"{base}:latest")
    # TODO if doing a tagged version build, setup generic version tags here
    return tags


def build_dockerfiles(args) -> bool:
    all_success = True
    if args['-v']:
        print(args)
    if args['--no-build']:
        print(" ::: Skipping Dockerfile building")
        return all_success

    run_and_stream_command_output('docker buildx create --use --name pihole-build', os.environ.copy(), True)
    for debian_version in BUILD_VARS['debian_versions']:
        all_success = build('pihole', debian_version, args['-t'], args['--no-cache'], args['-v']) and all_success
        if not all_success and args['--fail-fast']:
            return False
    return all_success


def run_and_stream_command_output(command: str, environment_vars: dict, verbose: bool) -> bool:
    print("Running", command)
    build_result = subprocess.Popen(command.split(), env=environment_vars, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
    if verbose:
        while build_result.poll() is None:
            for line in build_result.stdout:
                print(line, end='')
    build_result.wait()
    if build_result.returncode != 0:
        print("     ::: Error running: {}".format(command))
        print(build_result.stderr)
    return build_result.returncode == 0


def build(docker_repo: str, debian_version: str, show_time: bool, no_cache: bool, verbose: bool) -> bool:
    create_tag = f'{docker_repo}:{FTL_VERSION}-{debian_version}'
    print(f' ::: Building {create_tag}')
    time_arg = 'time' if show_time else ''
    cache_arg = '--no-cache' if no_cache else ''
    build_env = os.environ.copy()
    build_env['PIHOLE_VERSION'] = FTL_VERSION
    build_env['DEBIAN_VERSION'] = debian_version
    write_bake_config(BUILD_VARS['archs'], debian_version)
    print(f' ::: Building {create_tag}')
    build_command = f'{time_arg} docker buildx bake --file build.yml --file {BAKE_CONFIG_FILE} {cache_arg}'
    run_and_stream_command_output(build_command + ' --print', build_env, verbose)
    success = run_and_stream_command_output(build_command, build_env, verbose)
    if verbose:
        print(build_command, '\n')
    #if success and hub_tag:
    #    hub_tag_command = f'{time_arg} docker tag {create_tag} {hub_tag}'
    #    print(f' ::: Tagging {create_tag} into {hub_tag}')
    #    success = run_and_stream_command_output(hub_tag_command, build_env, verbose)
    return success


if __name__ == '__main__':
    args = docopt(__doc__, version='Dockerfile 1.1')
    read_pihole_versions()
    read_build_vars()
    success = build_dockerfiles(args)
    exit_code = 0 if success else 1
    sys.exit(exit_code)
