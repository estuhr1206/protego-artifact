import os
import sys
import shutil
import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib
import matplotlib.backends.backend_pdf
import math

second_in_us = 1000000

def main():
    antagonist = int(sys.argv[1])
    exp_start = int(sys.argv[2])
    exp_end = int(sys.argv[3])
    pdf = matplotlib.backends.backend_pdf.PdfPages("time_series_plots.pdf")
    for current_dir in os.listdir():
        if current_dir == "overall_csvs" or os.path.isfile(current_dir):
           continue
        print("plotting dir: {}".format(current_dir))
        graph_one(pdf, current_dir, antagonist, exp_start, exp_end)
    pdf.close()

def graph_one(pdf, dir, antagonist, exp_start, exp_end, granularity=5000):
    df = pd.read_csv("{}/all_tasks.csv".format(dir))
    Data = df[['start_us', 'duration_us']]
    completed_tasks_data = np.array(Data)
    completed_tasks_data_us = np.array(Data)
    completed_tasks_data[:,0] /= second_in_us

    latency_99 = completed_tasks_data.copy()
    # sort by second column
    # a[a[:, 1].argsort()]
    latency_99 = latency_99[latency_99[:,1].argsort()]
    idx = int(len(latency_99) * 0.99)
    latency_99 = latency_99[idx:]
    # resort back by timestamp
    latency_99 = latency_99[latency_99[:,0].argsort()]

    df = pd.read_csv("{}/netbench_cores.csv".format(dir))
    Data = df[['time(s)', 'cores']]
    # df = df[['time(s)', 'cores']]
    # Data = df[df['time(s)'] > start_time]
    netbench_cores = np.array(Data)
    if antagonist:
      df = pd.read_csv("{}/antagonist_cores.csv".format(dir))
      Data = df[['time(s)', 'cores']]
      # df = df[['time(s)', 'cores']]
      # Data = df[df['time(s)'] > start_time]
      antagonist_cores = np.array(Data)


    df = pd.read_csv("{}/all_tasks.csv".format(dir))
    Data = df[['tsc', 'start_us']]
    first_tsc_all_tasks = Data['tsc'].iloc[0]
    start_time_all_tasks = Data['start_us'].iloc[0] / second_in_us

    with open("{}/iokernel.node-0.log".format(dir)) as f:
            tsc = 0
            for line in f:
                if "time:" in line:
                  line_items = line.split()
                  ticks = int(line_items[6])
                if "tsc" in line:

                    line_items = line.split()
                    time = float(line_items[2][:-1])

                    tsc =  int(line_items[7])

                    if tsc > first_tsc_all_tasks:
                      break

    sync_adjustment_us = (tsc / ticks) - (first_tsc_all_tasks / ticks)
    sync_adjustment = sync_adjustment_us / second_in_us

    cores_time_diff = time - sync_adjustment - start_time_all_tasks

    netbench_cores[:,0] -= cores_time_diff
    if antagonist:
      antagonist_cores[:,0] -= cores_time_diff
     
     
    df = pd.read_csv("{}/client_drop_tasks.csv".format(dir))
    Data = df[['start_us', 'duration_us']]
    client_drop_data = np.array(Data)
    client_drop_data = client_drop_data[client_drop_data[:,0].argsort()]
    # client_drop_data[:,0] /= second_in_us

    df = pd.read_csv("{}/server_drop_tasks.csv".format(dir))
    Data = df[['start_us', 'duration_us']]
    server_drop_data = np.array(Data)
    server_drop_data = server_drop_data[server_drop_data[:,0].argsort()]
    # server_drop_data[:,0] /= second_in_us

    increment = granularity # us
    curr_time = increment
    prev_time = 0
    total_time = int(exp_end * 1e6)

    server_drop_count = []
    client_drop_count = []
    throughput_over_time = []
    latency_over_time = []

    while curr_time <= total_time:
      server_mask1 = (server_drop_data[:,0] < curr_time)
      server_mask2 = (server_drop_data[:,0] > prev_time)
      m = np.logical_and(server_mask1, server_mask2)
      # don't need latency (aka duration aka col 1). Just need how many rows match criteria = number of drops
      server_drop_count.append((curr_time, server_drop_data[m, :].shape[0] / increment)) # this should give drop per microsecond

      client_mask1 = (client_drop_data[:,0] < curr_time)
      client_mask2 = (client_drop_data[:,0] > prev_time)
      m = np.logical_and(client_mask1, client_mask2)
      client_drop_count.append((curr_time, client_drop_data[m, :].shape[0] / increment))

      # throughput
      throughput_mask1 = (completed_tasks_data_us[:,0] < curr_time)
      throughput_mask2 = (completed_tasks_data_us[:,0] > prev_time)
      m = np.logical_and(throughput_mask1, throughput_mask2)
      throughput_over_time.append((curr_time, completed_tasks_data_us[m, :].shape[0] / increment))

      # latency
      latency_over_time.append((curr_time, np.average(completed_tasks_data_us[m, 1])))

      prev_time = curr_time
      curr_time += increment


    server_drop_count = np.array(server_drop_count)
    client_drop_count = np.array(client_drop_count)
    throughput_over_time = np.array(throughput_over_time)
    latency_over_time = np.array(latency_over_time)

    temp_server_drop_count = server_drop_count.copy()
    temp_client_drop_count = client_drop_count.copy()
    temp_throughput_over_time = throughput_over_time.copy()

    # produce drops per second
    temp_server_drop_count[:,1] *= second_in_us
    temp_client_drop_count[:,1] *= second_in_us
    temp_throughput_over_time[:,1] *= second_in_us
    # convert from us to s
    temp_server_drop_count[:,0] /= second_in_us
    temp_client_drop_count[:,0] /= second_in_us
    temp_throughput_over_time[:,0] /= second_in_us

    # print(client_drop_data)
    total_drop_count = temp_server_drop_count + temp_client_drop_count
    # fix the doubling of the time column, and converting from us to s
    total_drop_count[:,0] /= 2
    
    rasterize = False
    # start_time = cores_start_time
    # end_time = start_time + (exp_end - exp_start)
    # end_time = 20
    close_up = False
    close_up_min = 2.42
    close_up_max = 2.47
    """
    PLOTTING
    """
    if antagonist:
      fig, (plt1, plt2, plt3, plt4, plt5, plt6) = plt.subplots(6, 1, figsize=(20,20))
    else:
      fig, (plt1, plt2, plt3, plt4, plt5) = plt.subplots(5, 1, figsize=(20,20))

    fig.suptitle(dir, fontsize=22, y=1.0)

    x_range = [3.9, 8.5]
    """
    PLOT 1
    """
    plt1.tick_params(axis='both', which='major', labelsize=18)

    # plt1.axis(xmin=x_range[0], xmax=x_range[1])
    # plt1.axis(ymin=50, ymax=101)
    plt1.grid(which='major', color='black', linewidth=1.0)
    plt1.grid(which='minor', color='grey', linewidth=0.2)
    plt1.minorticks_on()
    # plt.ylim(ymin=0)


    # plt1.plot(completed_tasks_data[:,0], completed_tasks_data[:,1], rasterized=rasterize)
    plt1.plot(latency_over_time[:,0] / second_in_us, latency_over_time[:,1])

    # plt1.axis(ymin=0, ymax=500)
    if close_up:
      plt1.axis(xmin=close_up_min, xmax=close_up_max)
    plt1.set_xlabel('Time (s)', fontsize=18)
    plt1.set_ylabel('latencies (us)', fontsize=18)
    # plt1.legend(fontsize=18)


    """
    PLOT 2
    """
    plt2.tick_params(axis='both', which='major', labelsize=18)

    # plt2.axis(xmin=x_range[0], xmax=x_range[1])

    plt2.grid(which='major', color='black', linewidth=1.0)
    plt2.grid(which='minor', color='grey', linewidth=0.2)
    plt2.minorticks_on()
    # plt.ylim(ymin=0)


    # plt2.scatter(latency_99[:,0], latency_99[:,1], rasterized=rasterize, alpha=0.2)
    plt2.plot(latency_99[:,0], latency_99[:,1], rasterized=rasterize)

    # plt2.axis(ymin=0, ymax=500)
    if close_up:
      plt2.axis(xmin=close_up_min, xmax=close_up_max)
    plt2.set_xlabel('Time (s)', fontsize=18)
    plt2.set_ylabel('99th latency (us)', fontsize=18)
    #plt2.legend(fontsize=18)

    """
    PLOT 3
    """
    plt3.tick_params(axis='both', which='major', labelsize=18)


    plt3.grid(which='major', color='black', linewidth=1.0)
    plt3.grid(which='minor', color='grey', linewidth=0.2)
    plt3.minorticks_on()

    # plt3.plot(total_drop_count[:,0], total_drop_count[:,1], label='total_drop', color = 'purple', alpha=1.0)
    plt3.plot(temp_server_drop_count[:,0], temp_server_drop_count[:,1], label='server_drop', color = 'red', alpha=0.5)
    plt3.plot(temp_client_drop_count[:,0], temp_client_drop_count[:,1], label='client_drop', color = 'blue', alpha=0.5)


    plt3.axis(xmin=exp_start-.1, xmax=exp_end + .1)
    if close_up:
      plt3.axis(xmin=close_up_min, xmax=close_up_max)
    # plt3.axis(ymin=60000)

    plt3.set_xlabel('Time (s)', fontsize=18)
    plt3.set_ylabel('drops per second', fontsize=18)
    plt3.legend(fontsize=18)


    """
    PLOT 4
    """
    plt4.tick_params(axis='both', which='major', labelsize=18)

    # plt4.axis(xmin=x_range[0], xmax=x_range[1])
    #plt4.axis(ymin=0, ymax=25)
    plt4.grid(which='major', color='black', linewidth=1.0)
    plt4.grid(which='minor', color='grey', linewidth=0.2)
    plt4.minorticks_on()
    # plt.ylim(ymin=0)


    plt4.plot(netbench_cores[:,0], netbench_cores[:,1], label='netbench', color='blue')
    
    mask1 = (netbench_cores[:,0] >= 4)
    mask2 = (netbench_cores[:,0] <= 8)
    m = np.logical_and(mask1, mask2)
    netbench_avg = netbench_cores[m, :]

    plt4.axhline(y=np.average(netbench_avg[:,1]), color='r')

    # plt4.axis(xmin=6, xmax=14.5)
    # plt4.axis(ymax=6)
    plt4.axis(xmin=exp_start - .1, xmax=exp_end + .1)
    if close_up:
      plt4.axis(xmin=close_up_min, xmax=close_up_max)
    plt4.set_xlabel('Time(s)', fontsize=18)
    plt4.set_ylabel('number of cores', fontsize=18)
    plt4.legend(fontsize=18)

    """
    PLOT 5
    """
    plt5.tick_params(axis='both', which='major', labelsize=18)

    # plt5.axis(xmin=x_range[0], xmax=x_range[1])
    #plt5.axis(ymin=0, ymax=25)
    plt5.grid(which='major', color='black', linewidth=1.0)
    plt5.grid(which='minor', color='grey', linewidth=0.2)
    plt5.minorticks_on()
    # plt.ylim(ymin=0)


    plt5.plot(temp_throughput_over_time[:,0], temp_throughput_over_time[:,1])

    # plt5.axis(xmin=6, xmax=14.5)
    # plt5.axis(ymax=6)
    plt5.axis(xmin=exp_start - .1, xmax=exp_end + .1)
    if close_up:
      plt5.axis(xmin=close_up_min, xmax=close_up_max)
    plt5.set_xlabel('Time(s)', fontsize=18)
    plt5.set_ylabel('throughput per second', fontsize=18)
    plt5.legend(fontsize=18)

    """
    PLOT 6
    """
    if antagonist:
      plt6.tick_params(axis='both', which='major', labelsize=18)

      # plt6.axis(xmin=x_range[0], xmax=x_range[1])
      #plt6.axis(ymin=0, ymax=25)
      plt6.grid(which='major', color='black', linewidth=1.0)
      plt6.grid(which='minor', color='grey', linewidth=0.2)
      plt6.minorticks_on()
      # plt.ylim(ymin=0)


      plt6.plot(antagonist_cores[:,0], antagonist_cores[:,1], label='antagonist', color='red')
      mask1 = (antagonist_cores[:,0] >= 4)
      mask2 = (antagonist_cores[:,0] <= 8)
      m = np.logical_and(mask1, mask2)
      antagonist_avg = antagonist_cores[m, :]

      plt6.axhline(y=np.average(antagonist_avg[:,1]), color='blue')
      # plt6.axis(xmin=6, xmax=14.5)
      plt6.axis(xmin=exp_start - .1, xmax=exp_end + .1)
      if close_up:
        plt6.axis(xmin=close_up_min, xmax=close_up_max)
      plt6.set_xlabel('Time(s)', fontsize=18)
      plt6.set_ylabel('number of cores', fontsize=18)
      plt6.legend(fontsize=18)

    # plt.show()

    # print(completed_tasks_data[0:3])
    fig.tight_layout()
    
    
    pdf.savefig(fig)
    plt.clf()
    plt.close()


if __name__ == "__main__":
    main()