#!/usr/bin/env python3

import os
from os.path import join as pjoin
import sh
import sys

res_dir = '/home/glr/gem5/gem5-results'

def get_test_dirs():
    dirs = []
    for d in os.listdir(res_dir):
        if 'my' in d:
            dirs.append(d)
    print(dirs)
    return dirs

def main():
    dirs = get_test_dirs()
    batch = sh.Command('./batch.py')
    options = [['--st',
                '-s={}'.format(pjoin(res_dir,d)),
                '-o={}'.format(pjoin('data',d+'.csv'))]
                for d in dirs]
    print(options)
    for option in options:
        batch(*option)

main()
