#!/usr/bin/env python3

import paramiko
import os
from time import sleep
from util import *
from config_remote import *
import sys
from datetime import datetime

################################
### Experiemnt Configuration ###
################################

# Server overload algorithm (protego, breakwater, seda, dagor, nocontrol)
OVERLOAD_ALG = sys.argv[1]

# The number of client connections
NUM_CONNS = int(sys.argv[2])

# Average service time (in us)
ST_AVG = int(sys.argv[3])

BW_TARGET = int(sys.argv[4])
BW_THRESHOLD = int(sys.argv[4]) * 2
print("modifying bw_config.h values for target and threshold")
cmd = "sed -i \'s/#define SBW_DELAY_TARGET.*/#define SBW_DELAY_TARGET\\t\\t\\t{:d}/g\'"\
        " configs/bw_config.h".format(BW_TARGET)
execute_local(cmd)
cmd = "sed -i \'s/#define SBW_DROP_THRESH.*/#define SBW_DROP_THRESH\\t\\t\\t{:d}/g\'"\
        " configs/bw_config.h".format(BW_THRESHOLD)
execute_local(cmd)

# Service time distribution
#    exp: exponential
#    const: constant
#    bimod: bimodal
ST_DIST = sys.argv[5]

# List of offered load
# OFFERED_LOADS = [int(sys.argv[6])]
OFFERED_LOADS = [400000, 700000, 800000, 900000, 1000000, 1100000, 1200000, 1300000, 1400000, 1500000, 1600000, 1700000, 1800000, 2000000, 3000000]


ENABLE_DIRECTPATH = True
SPIN_SERVER = int(sys.argv[8])
DISABLE_WATCHDOG = False

NUM_CORES_SERVER = int(sys.argv[9])
NUM_CORES_LC = int(sys.argv[10])
NUM_CORES_LC_GUARANTEED = int(sys.argv[11])
NUM_CORES_CLIENT = 16

ERIC_CSV_NAMING = True
CSV_NAME_DIR = True

############################
### End of configuration ###
############################

# SLO = 10 * (average RPC processing time + network RTT)
# slo = (ST_AVG + NET_RTT) * 10
slo = int(sys.argv[13])

# Verify configs #
if OVERLOAD_ALG not in ["breakwater", "seda", "dagor", "nocontrol"]:
    print("Unknown overload algorithm: " + OVERLOAD_ALG)
    exit()

if ST_DIST not in ["exp", "const", "bimod"]:
    print("Unknown service time distribution: " + ST_DIST)
    exit()

cmd = "sed -i \'s/#define SBW_RTT_US.*/#define SBW_RTT_US\\t\\t\\t{:d}/g\'"\
        " configs/bw_config.h".format(NET_RTT)
execute_local(cmd)

### Function definitions ###
def generate_shenango_config(is_server ,conn, ip, netmask, gateway, num_cores,
        directpath, spin, disable_watchdog):
    config_name = ""
    config_string = ""
    if is_server:
        config_name = "server.config"
        config_string = "host_addr {}".format(ip)\
                      + "\nhost_netmask {}".format(netmask)\
                      + "\nhost_gateway {}".format(gateway)\
                      + "\nruntime_kthreads {:d}".format(num_cores)
    else:
        config_name = "client.config"
        config_string = "host_addr {}".format(ip)\
                      + "\nhost_netmask {}".format(netmask)\
                      + "\nhost_gateway {}".format(gateway)\
                      + "\nruntime_kthreads {:d}".format(num_cores)

    if spin:
        config_string += "\nruntime_spinning_kthreads {:d}".format(num_cores)

    if directpath:
        config_string += "\nenable_directpath 1"

    if disable_watchdog:
        config_string += "\ndisable_watchdog 1"

    cmd = "cd ~/{} && echo \"{}\" > {} "\
            .format(ARTIFACT_PATH,config_string, config_name)

    return execute_remote([conn], cmd, True)
### End of function definition ###

NUM_AGENT = len(AGENTS)

# configure Shenango IPs for config
server_ip = "192.168.1.200"
client_ip = "192.168.1.100"
agent_ips = []
netmask = "255.255.255.0"
gateway = "192.168.1.1"

for i in range(NUM_AGENT):
    agent_ip = "192.168.1." + str(101 + i)
    agent_ips.append(agent_ip)

k = paramiko.RSAKey.from_private_key_file(KEY_LOCATION)
# connection to server
server_conn = paramiko.SSHClient()
server_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
server_conn.connect(hostname = SERVERS[0], username = USERNAME, pkey = k)

# connection to client
client_conn = paramiko.SSHClient()
client_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client_conn.connect(hostname = CLIENT, username = USERNAME, pkey = k)

# connections to agents
agent_conns = []
for agent in AGENTS:
    agent_conn = paramiko.SSHClient()
    agent_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    agent_conn.connect(hostname = agent, username = USERNAME, pkey = k)
    agent_conns.append(agent_conn)
print ("number of agents: {:d}".format(NUM_AGENT))
# Clean-up environment
print("Cleaning up machines...")
cmd = "sudo killall -9 netbench & sudo killall -9 iokerneld"
execute_remote([server_conn, client_conn] + agent_conns,
               cmd, True, False)
sleep(1)

# Remove temporary output
cmd = "cd ~/{} && rm output.csv output.json".format(ARTIFACT_PATH)
execute_remote([client_conn], cmd, True, False)

# Distribuing config files
print("Distributing configs...")
# - server
cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no configs/*"\
        " {}@{}:~/{}/shenango/breakwater/src/ >/dev/null"\
        .format(KEY_LOCATION, USERNAME, SERVERS[0], ARTIFACT_PATH)
execute_local(cmd)
# - client
cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no configs/*"\
        " {}@{}:~/{}/shenango/breakwater/src/ >/dev/null"\
        .format(KEY_LOCATION, USERNAME, CLIENT, ARTIFACT_PATH)
execute_local(cmd)
# - agents
for agent in AGENTS:
    cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no configs/*"\
            " {}@{}:~/{}/shenango/breakwater/src/ >/dev/null"\
            .format(KEY_LOCATION, USERNAME, agent, ARTIFACT_PATH)
    execute_local(cmd)

# Generating config files
print("Generating config files...")
generate_shenango_config(True, server_conn, server_ip, netmask, gateway,
                         NUM_CORES_LC, ENABLE_DIRECTPATH, SPIN_SERVER, DISABLE_WATCHDOG)
generate_shenango_config(False, client_conn, client_ip, netmask, gateway,
                         NUM_CORES_CLIENT, ENABLE_DIRECTPATH, True, False)
for i in range(NUM_AGENT):
    generate_shenango_config(False, agent_conns[i], agent_ips[i], netmask,
                             gateway, NUM_CORES_CLIENT, ENABLE_DIRECTPATH, True, False)

# - server
cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no replace/netbench.cc"\
        " {}@{}:~/{}/{}/breakwater/apps/netbench/ >/dev/null"\
        .format(KEY_LOCATION, USERNAME, SERVERS[0], ARTIFACT_PATH, KERNEL_NAME)
execute_local(cmd)
# - client
cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no replace/netbench.cc"\
        " {}@{}:~/{}/{}/breakwater/apps/netbench/ >/dev/null"\
        .format(KEY_LOCATION, USERNAME, CLIENT, ARTIFACT_PATH, KERNEL_NAME)
execute_local(cmd)
# - agents
for agent in AGENTS:
    cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no replace/netbench.cc"\
        " {}@{}:~/{}/{}/breakwater/apps/netbench/ >/dev/null"\
        .format(KEY_LOCATION, USERNAME, agent, ARTIFACT_PATH, KERNEL_NAME)
    execute_local(cmd)

# Rebuild Shanango
print("Building Shenango...")
cmd = "cd ~/{}/shenango && make clean && make && make -C bindings/cc"\
        .format(ARTIFACT_PATH)
execute_remote([server_conn, client_conn] + agent_conns,
               cmd, True)

# Build Breakwater
print("Building Breakwater...")
cmd = "cd ~/{}/shenango/breakwater && make clean && make && make -C bindings/cc"\
        .format(ARTIFACT_PATH)
execute_remote([server_conn, client_conn] + agent_conns,
                 cmd, True)

# Build Netbench
print("Building netbench...")
cmd = "cd ~/{}/shenango/breakwater/apps/netbench && make clean && make"\
        .format(ARTIFACT_PATH)
execute_remote([server_conn, client_conn] + agent_conns,
                cmd, True)

# Execute IOKernel
iok_sessions = []
print("Executing IOKernel...")
cmd = "cd ~/{}/shenango && sudo ./iokerneld > iokernel.node-0.log".format(ARTIFACT_PATH)
iok_sessions += execute_remote([server_conn], cmd, False)
cmd = "cd ~/{}/shenango && sudo ./iokerneld > iokernel.node-1.log".format(ARTIFACT_PATH)
iok_sessions += execute_remote([client_conn] + agent_conns, cmd, False)

sleep(1)

for offered_load in OFFERED_LOADS:
    print("Load = {:d}".format(offered_load))
    # Execute netbench application
    # - server
    print("\tExecuting server...")
    cmd = "cd ~/{} && sudo ./shenango/breakwater/apps/netbench/netbench"\
            " {} server.config server >stdout.out 2>&1"\
            .format(ARTIFACT_PATH, OVERLOAD_ALG)
    server_session = execute_remote([server_conn], cmd, False)
    server_session = server_session[0]
    
    sleep(1)

    # - client
    # print("\tExecuting client...")
    # client_agent_sessions = []
    # cmd = "cd ~/{} && sudo ./shenango/breakwater/apps/netbench/netbench"\
    #         " {} client.config client {:d} {} {:d} {} {:d} {:d} {:d}"\
    #         " >stdout.out 2>&1".format(ARTIFACT_PATH, OVERLOAD_ALG, NUM_CONNS,
    #                 server_ip, ST_AVG, ST_DIST, slo ,NUM_AGENT, offered_load)
    # client_agent_sessions += execute_remote([client_conn], cmd, False)
    print("\tExecuting client...")
    client_agent_sessions = []
    cmd = "cd ~/{} && sudo ./shenango/breakwater/apps/netbench/netbench"\
            " {} client.config client {:d} {:f} {} {:d} {:d} {:d} {:d} {} {:d}"\
            " >stdout.out 2>&1".format(ARTIFACT_PATH, OVERLOAD_ALG, NUM_CONNS,
                    ST_AVG, ST_DIST, slo ,NUM_AGENT, offered_load, 0, server_ip, 1) # the 0 is for no loadshifts
    client_agent_sessions += execute_remote([client_conn], cmd, False)

    sleep(1)
    
    # - agent
    print("\tExecuting agents...")
    cmd = "cd ~/{} && sudo ./shenango/breakwater/apps/netbench/netbench"\
            " {} client.config agent {} 0 >stdout.out 2>&1"\
            .format(ARTIFACT_PATH, OVERLOAD_ALG, client_ip)
    client_agent_sessions += execute_remote(agent_conns, cmd, False)

    # Wait for client and agents
    print("\tWaiting for client and agents...")
    for client_agent_session in client_agent_sessions:
        client_agent_session.recv_exit_status()

    # Kill server
    cmd = "sudo killall -9 netbench"
    execute_remote([server_conn], cmd, True)

    # Wait for server to be killed
    server_session.recv_exit_status()

    sleep(1)

# Kill IOKernel
cmd = "sudo killall -9 iokerneld"
execute_remote([server_conn, client_conn] + agent_conns, cmd, True)

# Wait for IOKernel sessions
for iok_session in iok_sessions:
    iok_session.recv_exit_status()

# Close connections
server_conn.close()
client_conn.close()
for agent_conn in agent_conns:
    agent_conn.close()

# Create output directory
if not os.path.exists("outputs"):
    os.mkdir("outputs")

# Move output.csv and output.json
print("Collecting outputs...")
cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no {}@{}:~/{}/output.csv ./"\
        " >/dev/null".format(KEY_LOCATION, USERNAME, CLIENT, ARTIFACT_PATH)
execute_local(cmd)

output_prefix = "{}".format(OVERLOAD_ALG)
eric_prefix = "{}".format(OVERLOAD_ALG)

if OVERLOAD_ALG == "breakwater":
    eric_prefix += "_{:d}_{:d}".format(BW_TARGET, BW_THRESHOLD)
    output_prefix += "_{:d}_{:d}".format(BW_TARGET, BW_THRESHOLD)

if SPIN_SERVER or NUM_CORES_LC_GUARANTEED > 0:
    eric_prefix += "_guaranteed"

if SPIN_SERVER:
    output_prefix += "_spin"
    eric_prefix += "_spinning"

if DISABLE_WATCHDOG:
    output_prefix += "_nowd"

output_prefix += "_{}_{:d}_nconn_{:d}".format(ST_DIST, ST_AVG, NUM_CONNS)
eric_prefix += "_{:d}k".format(int(OFFERED_LOADS[0] / 1000))
eric_prefix += "_{:d}conns".format(NUM_CONNS)
eric_prefix += "_{:d}nodes".format(len(AGENTS) + 2)

# Print Headers
# Print Headers
header = "num_clients,offered_load,throughput,goodput,cpu"\
        ",min,mean,p50,p90,p99,p999,p9999,max"\
        ",reject_min,reject_mean,reject_p50,reject_p99"\
        ",p1_credit,mean_credit,p99_credit"\
        ",p1_q,mean_q,p99_q,mean_stime,p99_stime,server:rx_pps,server:tx_pps"\
        ",server:rx_bps,server:tx_bps,server:rx_drops_pps,server:rx_ooo_pps"\
        ",server:cupdate_rx_pps,server:ecredit_tx_pps,server:credit_tx_cps"\
        ",server:req_rx_pps,server:req_drop_rate,server:resp_tx_pps"\
        ",client:min_tput,client:max_tput"\
        ",client:ecredit_rx_pps,client:cupdate_tx_pps"\
        ",client:resp_rx_pps,client:req_tx_pps"\
        ",client:credit_expired_cps,client:req_dropped_rps"
# cmd = "echo \"{}\" > outputs/{}.csv".format(header, output_prefix)
# execute_local(cmd)

# cmd = "cat output.csv >> outputs/{}.csv".format(output_prefix)
# execute_local(cmd)

# # Remove temp outputs
# cmd = "rm output.csv"
# execute_local(cmd, False)

# print("Output generated: outputs/{}.csv".format(output_prefix))
# print("Done.")

curr_date = datetime.now().strftime("%m_%d_%Y")
curr_time = datetime.now().strftime("%H-%M-%S")
output_dir = "outputs/{}".format(curr_date)
if not os.path.isdir(output_dir):
   os.makedirs(output_dir)

run_dir = output_dir + "/" + curr_time
if not os.path.isdir(run_dir):
   os.makedirs(run_dir)

cmd = "echo \"{}\" > {}/{}.csv".format(header, run_dir, curr_time + "-" + output_prefix)
execute_local(cmd)

cmd = "cat output.csv >> {}/{}.csv".format(run_dir, curr_time + "-" + output_prefix)
execute_local(cmd)

if ERIC_CSV_NAMING:
    cmd = "mv {}/{}.csv {}/{}.csv".format(run_dir, curr_time + "-" + output_prefix, run_dir, eric_prefix)
    execute_local(cmd)

# Remove temp outputs
cmd = "rm output.csv"
execute_local(cmd, False)


print("stdout node 0")
cmd = "rsync -azh --info=progress2 -e \"ssh -i {} -o StrictHostKeyChecking=no -o"\
        " UserKnownHostsFile=/dev/null\" {}@{}:~/{}/stdout.out {}/ >/dev/null".format(KEY_LOCATION, USERNAME, SERVERS[0], ARTIFACT_PATH, run_dir)
execute_local(cmd)


cmd = "mv {}/stdout.out {}/stdout_server.out".format(run_dir, run_dir)
execute_local(cmd)

print("iokernel log node 1")
cmd = "rsync -azh --info=progress2 -e \"ssh -i {} -o StrictHostKeyChecking=no -o"\
        " UserKnownHostsFile=/dev/null\" {}@{}:~/{}/shenango/iokernel.node-1.log {}/ >/dev/null".format(KEY_LOCATION, USERNAME, CLIENT, ARTIFACT_PATH, run_dir)
execute_local(cmd)

print("stdout client node 1")
cmd = "rsync -azh --info=progress2 -e \"ssh -i {} -o StrictHostKeyChecking=no -o"\
        " UserKnownHostsFile=/dev/null\" {}@{}:~/{}/stdout.out {}/ >/dev/null".format(KEY_LOCATION, USERNAME, CLIENT, ARTIFACT_PATH, run_dir)
execute_local(cmd)

print("gathering config options for this experiment")
config_dir = run_dir + "/config"
if not os.path.isdir(config_dir):
   os.makedirs(config_dir)

cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no {}@{}:~/{}/server.config {}/"\
        " >/dev/null".format(KEY_LOCATION, USERNAME, SERVERS[0], ARTIFACT_PATH, config_dir)
execute_local(cmd)
cmd = "scp -P 22 -i {} -o StrictHostKeyChecking=no {}@{}:~/{}/client.config {}/"\
        " >/dev/null".format(KEY_LOCATION, USERNAME, CLIENT, ARTIFACT_PATH, config_dir)
execute_local(cmd)

cmd = "cp configs/bw_config.h {}/".format(config_dir)
execute_local(cmd)
script_config = "overload algorithm: {}\n".format(OVERLOAD_ALG)
script_config += "number of nodes: {}\n".format(len(NODES))
script_config += "number of connections: {}\n".format(NUM_CONNS)
script_config += "service time distribution: {}\n".format(ST_DIST)
script_config += "average service time: {}\n".format(ST_AVG)
script_config += "offered load: {}\n".format(OFFERED_LOADS[0])
script_config += "server cores: {}\n".format(NUM_CORES_SERVER)
script_config += "LC cores: {}\n".format(NUM_CORES_LC)
script_config += "LC guaranteed cores: {}\n".format(NUM_CORES_LC_GUARANTEED)
if SPIN_SERVER:
    script_config += "server cores spinning for LC\n"
script_config += "client cores: {}\n".format(NUM_CORES_CLIENT)
script_config += "RTT: {}\n".format(NET_RTT)
script_config += "SLO: {}\n".format(slo)
script_config += "Connections: {:d}\n".format(NUM_CONNS)

cmd = "echo \"{}\" > {}/script.config".format(script_config, config_dir)
execute_local(cmd)

if CSV_NAME_DIR:
    os.chdir(output_dir)
    if os.path.isdir(eric_prefix):
        print("error, desired directory name is already an output directory")
        exit()
    os.rename(curr_time, eric_prefix)
    os.chdir("..")

print("Done.")
# TODO make sure the output stuff is consistent across run scripts
