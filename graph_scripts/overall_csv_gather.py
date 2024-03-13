import os
import sys
import shutil

if not os.path.exists("overall_csvs"):
    os.makedirs("overall_csvs")

for current_dir in os.listdir():
    if current_dir == "overall_csvs":
        continue
    os.chdir(current_dir)
    for f in os.listdir():
        if "breakwater" in f or "nocontrol" in f:
            shutil.copy(f, "../overall_csvs/")
            print(f)
    os.chdir("..")
print("done")