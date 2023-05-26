import os.path as osp
import os
import argparse
import matplotlib.pyplot as plt
import json
import functools as ft
import utils as u
import utils.common as c
import utils.target_stats as t
from multiprocessing import Pool
import multiprocessing
import numpy as np

parser = argparse.ArgumentParser(
    description="collect frontend profiling data from gem5 (mainly) and xs rtl, and draw graphs"
)
# parser.add_argument("-f", help="profiling result file")
parser.add_argument("--profiling-path", help="profiling result path",
                    default="/nfs/home/goulingrui/expri_results/gem5/profiling")
parser.add_argument("--gem5-src-path", help="gem5 run result path",
                    default="/nfs/home/goulingrui/expri_results/gem5/frontend_06/NanhuDRAMSim-8c70ce82d5-bp-profiling-fixed")
parser.add_argument("--rtl-src-paths", help="rtl run result path", action='append',
                    default=["/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasks_12_05_2022"])
parser.add_argument("--simpoint-json", help="simpoint description file in json",
                    default="/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_20m/simpoint_summary.json")
parser.add_argument("--debug", help="debug mode", action="store_true", default=False)
parser.add_argument("-j", help="number of processes", type=int, default=1)
actions = parser.add_argument_group('actions')
actions.add_argument("-d", "--draw", help="draw graphs", action="store_true", default=True)
actions.add_argument("-csv", "--csv", help="dump to csv", action="store_true", default=False)
actions.add_argument("--static-branch", help="static branch counts", action="store_true", default=False)
actions.add_argument("-p", "--phase", help="output stats by phase", action="store_true", default=False)
actions.add_argument("--fb", help="fetch block size", action="store_true", default=False)
actions.add_argument("--lb", help="loop buffer inst supply percent", action="store_true", default=False)
actions.add_argument("--gem5-vs-rtl", help="output rtl data compared to rtl for supported profiles", action='store_true', default=False)
actions.add_argument("--top-mispred", help="copy top mispredictions to res path", action="store_true", default=False)

args = parser.parse_args()

if not args.static_branch and not args.fb and not args.top_mispred and not args.lb:
    print("no profiling option specified, exit")
    exit(0)

profiling_path = args.profiling_path
gem5_src_path = args.gem5_src_path
rtl_src_paths = args.rtl_src_paths
rtl_src_path = rtl_src_paths[0]
simpoints = args.simpoint_json

def debug_print(*rgs, **kwargs):
    if args.debug:
        print(*rgs, **kwargs)

def get_checkpoint_path_tree(simpoints, output=False, gem5=True):
    assert osp.exists(simpoints)
    all_workloads = {}
    def debug_print(*args, **kwargs):
        if output:
            print(*args, **kwargs)
    with open(simpoints) as j:
        js = json.load(j)
        for workload in js:
            all_workloads[workload] = []
            debug_print(workload,js[workload].keys())
            for point in js[workload]:
                if gem5:
                    this_point_path = osp.join(gem5_src_path,workload,point,"m5out")
                else:
                    this_point_path = osp.join(rtl_src_path,workload,point)
                debug_print(this_point_path)
                assert osp.exists(this_point_path)
                all_workloads[workload].append(this_point_path)
                debug_print(all_workloads[workload])
    return all_workloads


# rtl_checkpoint_path_tree = get_checkpoint_path_tree(simpoints, gem5=False)


gem5_target = [
    # 'cpus?\.branchPred\.(ftbEntriesWithDifferentStart)',
    # 'cpus?\.branchPred\.(commitFsqEntryHasInsts::mean)',
    # 'cpus?\.branchPred\.(staticBranchNum)',
    # 'cpus?\.branchPred\.(staticBranchNumEverTaken)',
]
if args.lb:
    gem5_target += [f'(commitLoopBufferEntryInstNum::{x})' for x in range(1,16+1)]
    gem5_target += [f'(commitLoopBufferDoubleEntryInstNum::{x})' for x in range(1,16+1)]

# print(gem5_target)
rtl_target = [f'(commit_num_inst_{i})' for i in range(1, 16+1)]
# print(rtl_target)
# exit()
def get_tree(simpoints, file_path, stat_file, gem5=True):
    if gem5:
        target = gem5_target
    else:
        target = rtl_target
    prefix = "" if gem5 else "xs_"
    tree = u.glob_weighted_stats(
        file_path,
        ft.partial(u.stats_factory, target, target, prefix),
        white_list=[],
        simpoints=simpoints,
        stat_file=stat_file
    )
    # print(tree)
    return tree


def get_name_of_run(file):
    for part in file.split("/"):
        # print(part)
        if "Nanhu" in part:
            return part
    return 'unnamed'

def get_subpath(stat_file):
    return stat_file.split("/")[-4:-3]

def get_workload_name(stat_file):
    return stat_file.split("/")[-4]

def get_checkpoint_name(stat_file):
    return stat_file.split("/")[-3]

def try_save_fig(plt, path):
    if not osp.exists(osp.split(path)[0]):
        os.makedirs(osp.split(path)[0])
    print("saving fig to", path)
    plt.savefig(path, bbox_inches='tight')

def total_max_stat_by_workload(stat_tree, key, filename, save_fig=False):
    res_dict = {}
    for bmk in stat_tree:
        for workload in stat_tree[bmk]:
            # print(stat_tree[bmk][workload])
            res_dict[workload] = 0
            df = stat_tree[bmk][workload]
            all_points = df[key]
            # print(all_points)
            for num in all_points:
                if num > res_dict[workload]:
                    res_dict[workload] = num
            # for point in stat_tree[bmk][workload]:
            #     print(stat_tree[bmk][workload][point])
            #     print(point)
            #     num = stat_tree[bmk][workload][point]
            #     if num > res_dict[workload]:
            #         res_dict[workload] = num
    # print(res_dict.keys())
    res_dict = dict(sorted(res_dict.items(), key = lambda kv:(kv[1], kv[0]), reverse=True))
    if save_fig:
        plt.cla()
        fig = plt.figure(figsize=(10,15))
        # print(len(res_dict.keys()))
        plt.bar(res_dict.keys(), res_dict.values())
        plt.xticks(rotation=90)
        plt.title(key)
        try_save_fig(plt, osp.join(profiling_path, filename))
    return res_dict

def ftb_entry_num_by_workload(stat_tree):
    return total_max_stat_by_workload(stat_tree, "ftbEntriesWithDifferentStart", "ftb_entry_total.png")

def static_branch_num_by_workload(stat_tree):
    return total_max_stat_by_workload(stat_tree, "staticBranchNum", "static_branch_total.png")

def taken_static_branch_num_by_workload(stat_tree):
    return total_max_stat_by_workload(stat_tree, "staticBranchNumEverTaken", "taken_static_branch_total.png")



def ave_fsq_entry_stat_by_workload(stat_tree, filename, inst_num=20*10**6, rtl_stat_tree=None):
    res_dict = {}
    rtl_res_dict = {}
    if (rtl_stat_tree):
        print("rtl_stat_tree is not None")
    for bmk in stat_tree:
        for workload in stat_tree[bmk]:
            
            # print(stat_tree[bmk][workload])
            res_dict[workload] = 0
            df = stat_tree[bmk][workload]
            all_points_fsq_entry_lens = df["commitFsqEntryHasInsts::mean"]
            weights = df['weight']
            # print(all_points)
            fsq_entry_nums = inst_num / all_points_fsq_entry_lens
            total_fsq_entry_num = np.sum(np.dot(fsq_entry_nums, weights))
            res_dict[workload] = inst_num / total_fsq_entry_num
            # for point in stat_tree[bmk][workload]:
            #     print(stat_tree[bmk][workload][point])
            #     print(point)
            #     num = stat_tree[bmk][workload][point]
            #     if num > res_dict[workload]:
            #         res_dict[workload] = num
            if rtl_stat_tree:
                rtl_res_dict[workload] = 0
                rtl_df = rtl_stat_tree[bmk][workload]
                rtl_keys = [x[1:-1] for x in rtl_target]
                rtl_fsq_entry_nums = rtl_df[rtl_keys].sum(axis=1)
                rtl_weights = rtl_df['weight']
                rtl_total_fsq_entry_num = np.sum(np.dot(rtl_fsq_entry_nums, rtl_weights))
                rtl_res_dict[workload] = inst_num / rtl_total_fsq_entry_num
                
    # print(res_dict.keys())
    res_dict = dict(sorted(res_dict.items(), key = lambda kv:(kv[1], kv[0]), reverse=True))
    fig = plt.figure(figsize=(10,15))
    # print(len(res_dict.keys()))
    plt.cla()
    plt.bar(res_dict.keys(), res_dict.values())
    plt.xticks(rotation=90)
    plt.title("gem5_fb_size")
    plt.savefig(osp.join(profiling_path, "gem5_"+filename))
    
    if rtl_stat_tree:
        rtl_res_dict = dict(sorted(rtl_res_dict.items(), key = lambda kv:(kv[1], kv[0]), reverse=True))
        fig = plt.figure(figsize=(10,15))
        # print(len(res_dict.keys()))
        plt.cla()
        plt.bar(rtl_res_dict.keys(), rtl_res_dict.values())
        plt.xticks(rotation=90)
        plt.title("rtl_fb_size")
        plt.savefig(osp.join(profiling_path, "rtl_"+filename))
        
        x = range(len(res_dict.keys()))
        fig = plt.figure(figsize=(10,15))
        plt.cla()
        bar_gem5 = plt.bar([i-0.2 for i in x], res_dict.values(), width=0.4, label="gem5", color='r')
        bar_rtl = plt.bar([i+0.2 for i in x], [rtl_res_dict[k] for k in res_dict.keys()], width=0.4, label="rtl", color='b')
        plt.xticks(x,res_dict.keys(),rotation=90)
        plt.title("gem5_vs_rtl_fb_size")
        plt.legend()
        plt.savefig(osp.join(profiling_path, "gem5_vs_rtl_"+filename))

    return res_dict


# calculate the average percentage of instructions supplied by loop buffer
def dyn_inst_from_loop_buffer_percent_by_workload(stat_tree, filename, inst_num=20*10**6):
    res_dict = {}
    double_res_dict = {}
    for bmk in stat_tree:
        for workload in stat_tree[bmk]:
            res_dict[workload] = 0
            df = stat_tree[bmk][workload]
            df['insts_in_lb'] = 0
            df['double_insts_in_lb'] = 0
            for i in range(1, 16+1):
                df['insts_in_lb'] += df[f'commitLoopBufferEntryInstNum::{i}']
                df['insts_in_lb'] += df[f'commitLoopBufferDoubleEntryInstNum::{i}']
                df['double_insts_in_lb'] += df[f'commitLoopBufferDoubleEntryInstNum::{i}'] * 2
            inst_in_lb_sum = np.sum(np.dot(df['insts_in_lb'], df['weight']))
            double_inst_in_lb_sum = np.sum(np.dot(df['double_insts_in_lb'], df['weight']))
            res_dict[workload] = inst_in_lb_sum / inst_num
            double_res_dict[workload] = double_inst_in_lb_sum / inst_num
    
    res_dict = dict(sorted(res_dict.items(), key = lambda kv:(kv[1], kv[0]), reverse=True))
    # rtl_res_dict = dict(sorted(rtl_res_dict.items(), key = lambda kv:(kv[1], kv[0]), reverse=True))
    
    x = range(len(res_dict.keys()))
    fig = plt.figure(figsize=(10,15))
    plt.cla()
    bar_gem5 = plt.bar([i-0.2 for i in x], res_dict.values(), width=0.4, label="insts_in_loop_buffer", color='r')
    bar_rtl = plt.bar([i+0.2 for i in x], [double_res_dict[k] for k in res_dict.keys()], width=0.4, label="double_insts_in_loop_buffer", color='b')
    plt.xticks(x,res_dict.keys(),rotation=90)
    plt.title("inst_percent_in_loop_buffer")
    plt.legend()
    plt.savefig(osp.join(profiling_path, filename))
    
    return res_dict, double_res_dict


def pointwise_data_extraction(file, col_pos=1, dataType='int', dict_key_pos=None):
    data = []
    try:
        # print(file)
        with open(file) as f:
            lines = f.readlines()
            for line in lines[1:]:
                if (dataType == 'int'):
                    if type(col_pos) == int:
                        datum = int(line.split()[col_pos])
                    elif type(col_pos) == list:
                        datum = [int(line.split()[i]) for i in col_pos]
                elif (dataType == 'float'):
                    if type(col_pos) == int:
                        datum = float(line.split()[col_pos])
                    elif type(col_pos) == list:
                        datum = [float(line.split()[i]) for i in col_pos]
                if dict_key_pos is not None:
                    key = line.split()[dict_key_pos]
                    datum = {key: datum}
                data.append(datum)
        debug_print(data)
        return data
    except Exception as e:
        print(e)
        return []
    
# input src file name, save fig in result path, leveled by run name and workload name
def pointwise_all_static_branch_and_ftb_entry_by_phase(files):
    [ftb_entry_file, static_branch_file] = files
    static_entry_nums = pointwise_data_extraction(ftb_entry_file, 1)
    static_branch_nums = pointwise_data_extraction(static_branch_file, 1)
    taken_static_branch_nums = pointwise_data_extraction(static_branch_file, 2)
    if len(static_entry_nums) > 0 and len(static_branch_nums) > 0 and len(taken_static_branch_nums) > 0:
        plt.cla()
        plt.xlabel("phase")
        plt.ylabel("num")
        plt.plot(static_entry_nums, color='blue', label='ftb entry')
        plt.plot(static_branch_nums, color='green', label='static branch')
        plt.plot(taken_static_branch_nums, color='red', label='taken static branch')
        plt.legend(loc='best')
        # plt.show()
        try_save_fig(plt, osp.join(profiling_path, get_name_of_run(ftb_entry_file), get_workload_name(ftb_entry_file),
                            "static_"+get_checkpoint_name(ftb_entry_file)+".png"))

# input src file name, save fig in result path, leveled by run name and workload name
def pointwise_fsq_entry_len_by_phase(file):
    fsq_entry_lens = pointwise_data_extraction(file, -1, 'float')
    if len(fsq_entry_lens) > 0:
        plt.cla()
        plt.xlabel("phase")
        plt.ylabel("len")
        plt.ylim((0,16))
        plt.plot(fsq_entry_lens, color='blue')
        try_save_fig(plt, osp.join(profiling_path, get_name_of_run(file), get_workload_name(file),
                            "fsq_entry_len_"+get_checkpoint_name(file)+".png"))


def pointwise_get_and_copy_top_mispredict(file):
    weight = get_checkpoint_name(file)
    workload_name = get_workload_name(file)
    file_name = file.split('/')[-1]
    dest_path = osp.join(profiling_path, get_name_of_run(file), workload_name)

    debug_print("try to draw top mispredict breakdown for "+file)
    # get top mispredict data
    # format: [{pc: [total, dirMiss, tgtMiss, noPredMiss]}, ...]
    top_mispredict_branches = pointwise_data_extraction(file, [2,5,6,7], dict_key_pos=0)
    maximum_mispred = list(top_mispredict_branches[0].values())[0][0]
    minimum_mispred_to_show = maximum_mispred * 0.01
    for i in range(len(top_mispredict_branches)):
        if list(top_mispredict_branches[i].values())[0][0] < minimum_mispred_to_show:
            top_mispredict_branches = top_mispredict_branches[:i]
            debug_print(f"deleting elements starting from index {i} since it has too few mispreds")
            break
    debug_print(f"top_mispredict_branches has {len(top_mispredict_branches)} items")
    # draw stacked column chart, dirMiss at bottom, and then tgtMiss, and then noPredMiss
    dirMisses = [list(x.values())[0][1] for x in top_mispredict_branches]
    tgtMisses = [list(x.values())[0][2] for x in top_mispredict_branches]
    noPredMisses = [list(x.values())[0][3] for x in top_mispredict_branches]
    dirPlusTgtMisses = [dirMisses[i]+tgtMisses[i] for i in range(len(dirMisses))]
    # debug_print
    plt.cla()
    fig = plt.figure()
    plt.bar(range(len(top_mispredict_branches)), dirMisses, color='b', label='dirMiss')
    plt.bar(range(len(top_mispredict_branches)), tgtMisses, bottom=dirMisses, color='g', label='tgtMiss')
    plt.bar(range(len(top_mispredict_branches)), noPredMisses, bottom=dirPlusTgtMisses, color='r', label='noPredMiss')
    plt.xticks(range(len(top_mispredict_branches)), [list(x.keys())[0] for x in top_mispredict_branches], rotation=90)
    plt.legend()
    try_save_fig(plt, osp.join(dest_path, weight+"_top_mispredict_by_branch.png"))
    # copy top mispredict files

    cp_dst_file_name = weight + "_" + file_name
    try:
        os.system("cp "+file+" "+osp.join(dest_path, cp_dst_file_name))
    except Exception as e:
        print(e)
    

    
    return top_mispredict_branches


# pointwise statistics
if ((args.static_branch or args.fb) and args.phase) or args.top_mispred:
    gem5_checkpoint_path_tree = get_checkpoint_path_tree(simpoints, args.debug)
    tp = Pool(args.j)
    ftb_entry_args_list = []
    static_branch_args_list = []
    taken_static_branch_args_list = []
    all_in_one_args_list = []
    fsq_entry_len_args_list = []
    top_mispredict_args_list = []
    for workload in gem5_checkpoint_path_tree:
        for point in gem5_checkpoint_path_tree[workload]:
            if args.static_branch:
                entry_file = osp.join(point,"ftbEntriesByPhase.txt")
                static_branch_file = osp.join(point,"topMispredictByPhase.txt")
                all_in_one_args_list.append([entry_file, static_branch_file])
            if args.fb:
                fsq_committed_len_file = osp.join(point,"fsqEntryCommittedInstNumDistsByPhase.txt")
                fsq_entry_len_args_list.append(fsq_committed_len_file)
            if args.top_mispred:
                top_mispred_file = osp.join(point,"topMispredictsByBranch.txt")
                top_mispredict_args_list.append(top_mispred_file)
    debug_print(top_mispredict_args_list, args.top_mispred)
    # tp.map(pointwise_ftb_entry_by_phase, ftb_entry_args_list)
    # tp.map(pointwise_static_branch_by_phase, static_branch_args_list)
    # tp.map(pointwise_taken_static_branch_by_phase, taken_static_branch_args_list)
    if args.static_branch:
        tp.map(pointwise_all_static_branch_and_ftb_entry_by_phase, all_in_one_args_list)
    if args.fb:
        tp.map(pointwise_fsq_entry_len_by_phase, fsq_entry_len_args_list)
    if args.top_mispred:
        debug_print("top mispred")
        tp.map(pointwise_get_and_copy_top_mispredict, top_mispredict_args_list)


if args.static_branch or args.fb or args.lb:
    tree_gem5 = get_tree(
        simpoints=simpoints,
        file_path=gem5_src_path,
        stat_file='m5out/stats.txt',
        gem5=True)
# print(tree_gem5)

if (args.gem5_vs_rtl):
    tree_rtl = get_tree(
        simpoints=simpoints,
        file_path=rtl_src_path,
        stat_file='main_err.txt',
        gem5=False)
# print(tree_rtl)


if args.static_branch:
    ftb_entry = ftb_entry_num_by_workload(tree_gem5)
    static_branch = static_branch_num_by_workload(tree_gem5)
    taken_static_branch = taken_static_branch_num_by_workload(tree_gem5)
    plt.cla()
    fig = plt.figure(figsize=(10,15))
    # use ftb entry data as x ticks
    # print(len(res_dict.keys()))
    plt.bar(ftb_entry.keys(), [static_branch[k] for k in ftb_entry.keys()], label="static branch", color='g')
    plt.bar(ftb_entry.keys(), ftb_entry.values(), label="ftb entry", color='r')
    plt.bar(ftb_entry.keys(), [taken_static_branch[k] for k in ftb_entry.keys()], label="taken static branch", color='b')
    plt.xticks(rotation=90)
    plt.title("total static branch and ftb entry")
    plt.legend()
    try_save_fig(plt, osp.join(profiling_path, "static_branch_ftb_entry_total.png"))
    
    plt.cla()
    plt.bar(ftb_entry.keys(), [ftb_entry[k] / taken_static_branch[k] for k in ftb_entry.keys()])
    plt.xticks(rotation=90)
    plt.title("ftb entry num / taken static branch")
    plt.ylim(1, 3)
    try_save_fig(plt, osp.join(profiling_path, "ftb_entry_taken_static_branch_ratio.png"))

if args.fb:
    ave_fsq_entry_stat_by_workload(tree_gem5, "fsq_entry_len.png", rtl_stat_tree=(tree_rtl if args.gem5_vs_rtl else None))

if args.lb:
    dyn_inst_from_loop_buffer_percent_by_workload(tree_gem5, "inst_percent_in_loop_buffer.png")

