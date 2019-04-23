#!/usr/bin/env python3
import os
from os.path import join as pjoin
import sh
import subprocess
import argparse

res_dir = pjoin(os.getenv('HOME'), 'gem5', 'gem5-results')

def get_test(res_dir):
    test = []
    for d in os.listdir(res_dir):
        if 'my' in d:
            test.append(d)
    return test

def main():
    parser = argparse.ArgumentParser(usage='-s')
    parser.add_argument('-s', '--specified-test', action='store',
                        help='sepcify a test')
    opt = parser.parse_args()
    if opt.specified_test != None:
        dirs = [opt.specified_test]
    else:
        dirs = get_test(res_dir)
    for test in dirs:
        print(test)
        options = ['./batch.py',
                   '--st',
                   '-s={}'.format(pjoin(res_dir,test)),
                   '-o={}'.format(pjoin('./data',test+'.csv'))]
        out = subprocess.check_output(options)
        out_text = out.decode('utf-8')
        print(out_text)

if __name__ == '__main__':
    main()
