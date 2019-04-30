#!/usr/bin/env python3
import os
import csv
import numpy as np
import pandas as pd


def get_files():
    files = []
    for f in os.listdir('./data'):
        if 'csv' in f:
            files.append(f)
    return files

files = get_files()
print(files)

for f in files:
    print(f)
    df = pd.read_csv('./data/'+f, index_col=0)
    df['per_mpki'] = df['iew.branchMispredicts'] / 200000
    df['per_mpki'].round(2)
    df.to_csv(f)
    print('\ttotal_mean_mpki: ', df['per_mpki'].mean().round(2),'\n')
