#!/usr/bin/env python3
import os
import csv
import numpy as np
import pandas as pd
import argparse


def get_files():
    files = []
    for f in os.listdir('./data'):
        if 'csv' in f:
            files.append(f)
    return files

def get_mpki(f):
    df = pd.read_csv('./data/'+f, index_col=0)
    df['per_mpki'] = df['iew.branchMispredicts'] / 200000
    df.to_csv(f)
    print('%s: %.2f' % (f[:-4], df['per_mpki'].mean().round(2)))

def main():
    print('')
    parser = argparse.ArgumentParser(usage='-s')
    parser.add_argument('-s', '--specified-test', action='store',
                        help='specify a test')

    opt = parser.parse_args()
    if opt.specified_test != None:
        files = [opt.specified_test+'.csv']
    else:
        files = get_files()

    files.sort()

    for f in files:
        get_mpki(f)

if __name__ == '__main__':
    main()
