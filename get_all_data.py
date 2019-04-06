#!/usr/bin/env python3
import os
from os.path import join as pjoin
import sh

res_dir = pjoin(os.getenv('HOME'), 'gem5', 'gem5-results')

def get_test(res_dir):
    test = []
    for d in os.listdir(res_dir):
        if 'my' in d:
            test.append(d)
    return test

def main():
    dirs = get_test(res_dir)
    batch = sh.Command('./batch.py')
    for test in dirs:
        print(test)
        options = ['--st',
                   '-s={}'.format(pjoin(res_dir,test)),
                   '-o={}'.format(pjoin('./data',test+'.csv'))]
        batch(*options)

if __name__ == '__main__':
    main()
