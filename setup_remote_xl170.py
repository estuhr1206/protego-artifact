#!/usr/bin/env python3
import os
import paramiko
from util import *
from config_remote import *

k = paramiko.RSAKey.from_private_key_file(KEY_LOCATION)

# config check
if len(NODES) < 1:
    print("[ERROR] There is no server to configure.")
    exit()

# change default shell to bash
print("Changing default shell to bash...")
conns = []
for server in NODES:
    server_conn = paramiko.SSHClient()
    server_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    server_conn.connect(hostname = server, username = USERNAME, pkey = k)
    conns.append(server_conn)

execute_remote(conns, "sudo usermod -s /bin/bash {}".format(USERNAME), True, False)

for conn in conns:
    conn.close()

# connections to servers
conns = []
for server in NODES:
    server_conn = paramiko.SSHClient()
    server_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    server_conn.connect(hostname = server, username = USERNAME, pkey = k)
    conns.append(server_conn)

# clean up machines
print("Cleaning up machines...")
cmd = "sudo killall -9 cstate"
execute_remote(conns, cmd, True, False)

cmd = "sudo killall -9 iokerneld"
execute_remote(conns, cmd, True, False)

cmd = "sudo rm -rf ~/{}".format(ARTIFACT_PATH)
execute_remote(conns, cmd, True, False)

# distributing code-base
print("Distributing sources...")
repo_name = (os.getcwd().split('/'))[-1]
# - server
for server in NODES:
    cmd = "rsync -azh -e \"ssh -i {} -o StrictHostKeyChecking=no"\
            " -o UserKnownHostsFile=/dev/null\" --progress ../{}/"\
            " {}@{}:~/{} >/dev/null"\
            .format(KEY_LOCATION, repo_name, USERNAME, server, ARTIFACT_PATH)
    execute_local(cmd)

# install sub-modules
print("Building submodules... (it may take a few mintues)")
cmd = "cd ~/{}/shenango && make submodules -j16".format(ARTIFACT_PATH)
execute_remote(conns, cmd, True)

# build shenango
print("Building Shenango...")
cmd = "cd ~/{}/shenango && make clean && make -j16 && make -C bindings/cc"\
        .format(ARTIFACT_PATH)
execute_remote(conns, cmd, True)

# settting up machines
print("Setting up machines...")
cmd = "cd ~/{}/shenango/breakwater && sudo ./scripts/setup_machine.sh"\
        .format(ARTIFACT_PATH)
execute_remote(conns, cmd, True)

print("Building Breakwater...")
cmd = "cd ~/{}/shenango/breakwater && make clean && make -j16 &&"\
        " make -C bindings/cc".format(ARTIFACT_PATH)
execute_remote(conns, cmd, True)

print("Setting up memcahced...")
cmd = "cd ~/{}/shenango-memcached && ./version.sh && autoreconf -i"\
        " && ./configure --with-shenango=../shenango"\
        .format(ARTIFACT_PATH)
execute_remote(conns, cmd, True)

print("Done.")
