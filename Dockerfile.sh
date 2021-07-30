#!/usr/bin/env bash

set -eux
./Dockerfile.py -v --no-cache
docker images

# TODO: Add junitxml output and have something consume it
# 2 parallel max b/c race condition with docker fixture (I think?)
#py.test --help
#py.test -vv -n 2 -k "${ARCH}" ./test/
