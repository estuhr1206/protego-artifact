#!/bin/sh

set -e

# Initialize submodules
git submodule init
git submodule update --init

# Cloudlab patches to Shenango
echo Applying patch to Shenango
cd shenango
git apply ../connectx-4.patch
git apply ../cloudlab_xl170.patch
cd ..

echo checking out breakwater branch in memcached
cd shenango-memcached
git checkout breakwater
cd ..

echo Done.
