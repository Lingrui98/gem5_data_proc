#!/usr/bin/env python3
import os
from os.path import join as pjoin
import sh
import subprocess
import argparse

res_dir = pjoin(os.getenv('HOME'), 'gem5', 'gem5-results')

def get_test(res_dir, target):
    test = []
    for d in os.listdir(res_dir):
        if target == 'my':
            if 'my' in d:
                test.append(d)
        elif target == 'path':
            if 'path' in d:
                test.append(d)
        else:
            test.append(d)
    return test

def main():
    parser = argparse.ArgumentParser(usage='-s | -n | -m | -p')
    parser.add_argument('-s', '--specified-test', action='store',
                        help='sepcify a test')
    parser.add_argument('-n', '--newest-test', action='store_true',
                        help='get the newest test')
    parser.add_argument('-m', '--all-from-my-perceptron', action='store_true',
                        help='get all data from myperceptron')
    parser.add_argument('-p', '--all-from-path-perceptron', action='store_true',
                        help='get all data from pathperceptron')
    opt = parser.parse_args()
    if opt.specified_test != None:
        dirs = [opt.specified_test]
    elif opt.newest_test:
        d = os.listdir(res_dir)
        target_dir = ''
        latest = 0
        for dirs in d:
            stat = os.stat(os.path.join(res_dir, dirs))
            if (stat.st_mtime > latest):
                latest = stat.st_mtime
                target_dir = dirs
        #print("Latest dir is %s" % target_dir)
        dirs = [target_dir]
    elif opt.all_from_my_perceptron:
        dirs = get_test(res_dir,'my')
    elif opt.all_from_path_perceptron:
        dirs = get_test(res_dir,'path')
    else:
        print("Please sepecify a target")
        exit(0)
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
