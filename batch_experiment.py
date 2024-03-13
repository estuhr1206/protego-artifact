#!/usr/bin/env python3

import paramiko
import os
from time import sleep
from util import *
from config_remote import *
from datetime import datetime
import random

conns = [100]
loads = [850000, 1500000]
breakwater_targets = [10, 30, 50, 80]
algorithms = ["breakwater", "nocontrol"]

algorithm = "breakwater"
connections = 100
service_time = 10
breakwater_target = 10
service_distribution = "exp"
offered_load = 850000
loadshift = 0
spin_server = 0
num_cores_server = 18
num_cores_lc = 16
num_cores_lc_guaranteed = 16
caladan_threshold = 10
slo = 200
count = 1

# 1 is true, 0 is false
avoid_large_downloads = 1

def call_experiment():
    global count
    print("experiment number: {}".format(count))
    # if count < 16:
    #     count += 1
    #     return
    count += 1
    os.system("python3 param_synthetic_antagonist.py {} {:d} {:d} {:d} {} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:d}".format(
              algorithm, connections, service_time, breakwater_target, service_distribution, offered_load,
              loadshift, spin_server, num_cores_server, num_cores_lc, num_cores_lc_guaranteed, caladan_threshold,
              slo, avoid_large_downloads))
    print("sleeping for 5 seconds before next connection")
    sleep(5)
    # just for testing
    # exit()

def main():
    global algorithm
    global connections
    global service_time
    global breakwater_target
    global service_distribution
    global offered_load
    global loadshift
    global spin_server
    global num_cores_server
    global num_cores_lc
    global num_cores_lc_guaranteed
    global caladan_threshold
    global slo

    for a in algorithms:
        algorithm = a
        for c in conns:
            connections = c
            for l in loads:
                offered_load = l
                for i in range(2):
                    if i == 0:
                        spin_server = 0
                        num_cores_lc_guaranteed = 0
                    else:
                        spin_server = 1
                        num_cores_lc_guaranteed = 16
                    if algorithm != "breakwater":
                        call_experiment()
                        continue
                    for t in breakwater_targets:
                        breakwater_target = t
                        call_experiment()

if __name__ == "__main__":
    main()




