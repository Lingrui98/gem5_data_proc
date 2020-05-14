#!/usr/bin/env python3

import os
import sys
from os.path import join as pjoin
import time
import re
import argparse
import pandas as pd
import numpy as np

from paths import *
import common as c
from target_stats import *
from st_stat import make_st_stat_cache


def further_proc(pair: str, d: dict, verbose: bool) -> None:
    hpt, lpt = pair.split('_')
    # c.add_st_ipc(hpt, d)
    # c.add_overall_qos(hpt, lpt, d)
    # c.add_ipc_pred(d)
    c.add_slot_sanity(d)
    # c.add_qos(d)

    if verbose:
        c.print_line()
        print(pair, ':')
        c.print_dict(d)

    return d



def main():
    parser = argparse.ArgumentParser(usage='specify stat directory')
    parser.add_argument('-s', '--stat-dir', action='store', required=True,
                        help='gem5 output directory'
                       )
    parser.add_argument('-o', '--output', action='store',
                        help='csv to save results'
                       )
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='whether output intermediate result'
                       )
    parser.add_argument('-b', '--error-bound', action='store', type=float,
                        default=0.0,
                        help='Threshold to output an entry'
                       )
    parser.add_argument('-i', '--ipc-only', action='store_true',
                        default=0.0,
                        help='Only extract ipc'
                       )
    parser.add_argument('--st', action='store_true',
                        help='processing ST stats'
                       )
    parser.add_argument('--pair-filter', action='store', default='',
                        help='file than filt pairs'
                       )
    opt = parser.parse_args()

    pairs = c.pairs(opt.stat_dir, return_path=False)

    if (opt.pair_filter):
        pairs = c.pair_filt(pairs, opt.pair_filter)

    paths = c.pair_to_full_path(opt.stat_dir, pairs)

    pairs, paths = c.stat_filt(pairs, paths)
    # paths = c.time_filt(paths)
    paths = [pjoin(x, 'stats.txt') for x in paths]

    # make_st_stat_cache()

    matrix = {}

    for pair, path in zip(pairs, paths):
        if opt.ipc_only:
            d = c.get_stats(path, ipc_target, re_targets=True)
        else:
            #d = c.get_stats(path, branch_targets, re_targets=True)
            d = c.get_stats(path, branch_targets, re_targets=True)
        if len(d):
            if not opt.st:
                matrix[pair] = further_proc(pair, d, opt.verbose)
            else:
                matrix[pair] = d

    df = pd.DataFrame.from_dict(matrix, orient='index')
    #if df['iew.branchMispredict'] != None:
    #    df['mpki'] = df['iew.branchMispredict'] / df['Insts'] * 1000
    #    df['Mispredict Rate'] = df['branchPred.condIncorrect'] / df['branchPred.condPredicted']
    pd.set_option('display.max_columns', None)
    #print(df.sort_index(1))
    try:
        df['Misp%'] = df['Misp'] / df['cond'] * 100
        df['MPKI'] = df['Misp'] / df['Insts'] * 1000
        df['Status'] = 'running'
        df.loc[df['Insts'] > 30000000, ['Status']] = 'done'
        print(df[['Status', 'ipc', 'indirectMis', 'Misp', 'Misp%', 'MPKI']])
        hmean_mpki = len(df['MPKI']) / np.sum(1.0/df['MPKI'])
        hmean_misp = len(df['Misp%']) / np.sum(1.0/df['Misp%'])
        gmean_mpki = df['MPKI'].prod() ** (1.0/len(df['MPKI']))
        gmean_misp = df['Misp%'].prod() ** (1.0/len(df['Misp%']))
        print('Totally %d tests' % len(df['Status']))
        print('Mean MPKI is:  %.2f, Hmean MPKI is:  %.4f, Gmean MPKI is:  %.4f' % (df['MPKI'].mean().round(2), hmean_mpki, gmean_mpki))
        print('Mean Misp%% is: %.2f, Hmean Misp%% is: %.4f, Gmean Misp%% is: %.4f' % (df['Misp%'].mean().round(2), hmean_misp, gmean_misp))
        print('Mean IPC is: %.4f' % df['ipc'].mean())
        df.drop(['Status'], axis=1, inplace=True)
    except Exception:
        print("No data yet")
        exit()

    if not opt.st:
        errors = df['IPC prediction error'].values
        print('Mean: {}'.format(np.mean(np.abs(errors))))
        # df.sort_values(['QoS prediction error'], ascending=False, inplace=True)

        print(df['overall QoS'][abs(df['IPC prediction error']) > opt.error_bound])

    if opt.output:
        df.to_csv(opt.output, index=True)

    # print('filted QoS')
    # print(df['QoS_0'][df['QoS_0'] < 0.9])

if __name__ == '__main__':
    main()
