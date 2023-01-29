import utils as u
import utils.common as c
import utils.target_stats as t
import json
import pandas as pd
import numpy as np
import sys
import os.path as osp
from scipy.stats import gmean
from statistics import geometric_mean
import argparse
import re
import functools as ft

simpoints17 = '/home51/zyy/expri_results/simpoints.json'

def gen_coverage():
    tree = u.glob_weighted_stats(
            '/home51/zyy/expri_results/omegaflow_spec17/of_g1_perf/',
            u.stats_factory(t.ipc_target, 'cpi')
            )
    d = {}
    for bmk in tree:
        for workload in tree[bmk]:
            d[workload] = {}
            coverage, selected = u.coveraged(0.8, tree[bmk][workload])
            print(coverage)
            weights = selected['weight']
            for row in weights.index:
                d[workload][int(row)] = weights[row]
            print(d[workload])
    with open(simpoints, 'w') as f:
        json.dump(d, f, indent=4)


def get_insts(fname: str):
    assert osp.isfile(fname)
    p = re.compile('total guest instructions = (\d+)')
    with open(fname) as f:
        for line in f:
            m = p.search(line)
            if m is not None:
                return m.group(1)
    return None

def print_score(df: pd.DataFrame, clock_rate, name):
    print(f"----------- SPEC {name} ------------")
    print(df.sort_index())
    print(f'Estimated score @ {clock_rate/(10**9)}GHz:', geometric_mean(df['score']))
    print('Estimated score per GHz:', geometric_mean(df['score'])/(clock_rate/(10**9)))
    # print('Excluded because of low coverage:', list(excluded.index))

def compute_weighted_mpki(ver, confs, base, simpoints, prefix, insts_file_fmt, stat_file,
        clock_rate, min_coverage=0.0, blacklist=[], whitelist=[], merge_benckmark=False):
    target = eval(f't.{prefix}branch_targets')
    workload_dict = {}
    bmk_stat = {}

    for conf, file_path in confs.items():
        workload_dict[conf] = {}
        bmk_stat[conf] = {}
        if prefix == '':
            stats = target
            print(target)
        else:
            assert prefix == 'xs_'
            stats = target + ['(ipc)']
        tree = u.glob_weighted_stats(
                file_path,
                ft.partial(u.stats_factory, target, stats, prefix=prefix),
                whitelist,
                simpoints=simpoints,
                stat_file=stat_file,
                )
        with open(simpoints) as jf:
            js = json.load(jf)
            # print(js.keys())
        times = {}
        # print(tree)
        for bmk in tree:
            if bmk in blacklist:
                continue
            if len(whitelist) and bmk not in whitelist:
                continue
            mpkis = []
            cpis = []
            weights = []
            time = 0
            coverage = 0
            count = 0
            total_misp = 0
            total_misp_b = 0
            total_miss_ftb = 0
            total_miss_btb = 0
            total_update_ftb = 0
            total_misp_b_ubtb = 0
            total_misp_b_btb = 0
            total_misp_j = 0
            total_misp_i = 0
            total_misp_c = 0
            total_misp_r = 0
            total_rdc_sc = 0
            total_inst = 0
            total_branches = 0
            total_cycle = 0
            total_frontend_bubble = 0
            total_s2_redirect = 0
            for workload, df in tree[bmk].items():
                if (workload in blacklist):
                    continue
                # print(workload)
                selected = dict(js[workload])
                keys = [int(x) for x in selected]
                keys = [x for x in keys if x in df.index]
                # print(keys)
                df = df.loc[keys]
                # print(df)
                cpi, weight = u.weighted_cpi(df)
                if prefix == '':
                    (total_mpki, b_mpki, i_mpki, r_mpki, j_mpki, ftb_mpki, bpki, b_misrate) = u.weighted_mpkis(df)
                else:
                    assert prefix == 'xs_'
                    ([total_mpki, b_mpki, j_mpki, i_mpki, c_mpki, r_mpki, ftb_mpki, ftb_upki, frontend_bubble_pki, s2_redirect_pki], bpki, b_misrate, sc_rdc_mpki) = u.xs_weighted_mpkis(df)
                    # ([total_mpki, b_mpki, j_mpki, i_mpki, c_mpki, r_mpki, btb_mpki], bpki, b_misrate, sc_rdc_mpki) = u.xs_weighted_mpkis(df)
                weights.append(weight)

                workload_dict[conf][workload] = {}
                workload_dict[conf][workload]['CPI'] = cpi
                workload_dict[conf][workload]['IPC'] = 1.0/cpi
                workload_dict[conf][workload]['MPKI_B'] = b_mpki
                workload_dict[conf][workload]['BPKI'] = bpki
                workload_dict[conf][workload]['MISRATE_B'] = b_misrate
                workload_dict[conf][workload]['MPKI_I'] = i_mpki
                workload_dict[conf][workload]['MPKI_R'] = r_mpki
                workload_dict[conf][workload]['MPKI'] = total_mpki
                workload_dict[conf][workload]['MPKI_FTB'] = ftb_mpki
                workload_dict[conf][workload]['MPKI_J'] = j_mpki
                if prefix == 'xs_':
                    # workload_dict[conf][workload]['MPKI_B_UBTB'] = ubtb_b_mpki
                    # workload_dict[conf][workload]['MPKI_B_BTB'] = btb_b_mpki
                    workload_dict[conf][workload]['MPKI_C'] = c_mpki
                    # workload_dict[conf][workload]['MPKI_BTB'] = btb_mpki
                    workload_dict[conf][workload]['UPKI_FTB'] = ftb_upki
                    workload_dict[conf][workload]['MPKI_RDC_SC'] = sc_rdc_mpki
                    workload_dict[conf][workload]['FrontendBubble'] = frontend_bubble_pki
                    workload_dict[conf][workload]['s2_redirect'] = s2_redirect_pki
                workload_dict[conf][workload]['Coverage'] = weight

                # merge multiple sub-items of a benchmark
                if merge_benckmark:
                    insts_file = insts_file_fmt.format(workload)
                    insts = int(get_insts(insts_file))
                    workload_dict[conf][workload]['TotalInst'] = insts
                    workload_dict[conf][workload]['PredictedCycles'] = insts*cpi
                    seconds = insts*cpi / clock_rate
                    workload_dict[conf][workload]['PredictedSeconds'] = seconds
                    time += seconds
                    total_inst += insts
                    total_cycle += insts * cpi
                    total_misp_b += insts*b_mpki/1000
                    total_branches += insts*bpki/1000
                    total_misp_i += insts*i_mpki/1000
                    total_misp_r += insts*r_mpki/1000
                    total_misp += insts*total_mpki/1000
                    total_misp_j += insts*j_mpki/1000
                    total_miss_ftb += insts*ftb_mpki/1000
                    if prefix == 'xs_':
                        # total_misp_b_ubtb += insts*ubtb_b_mpki/1000
                        # total_misp_b_btb += insts*btb_b_mpki/1000
                        total_misp_c += insts*c_mpki/1000
                        # total_miss_btb += insts*btb_mpki/1000
                        total_update_ftb += insts*ftb_upki/1000
                        total_frontend_bubble += insts*frontend_bubble_pki/1000
                        total_s2_redirect += insts*s2_redirect_pki/1000
                        total_rdc_sc += insts*sc_rdc_mpki/1000
                    coverage += weight
                    count += 1
            # print(1111)
            # print(tree)
            # print(bmk_stat)
            if merge_benckmark:
                bmk_stat[conf][bmk] = {}
                bmk_stat[conf][bmk]['time'] = time
                ref_time = c.get_spec_ref_time(bmk, ver)
                assert ref_time is not None
                bmk_stat[conf][bmk]['ref_time'] = ref_time
                bmk_stat[conf][bmk]['score'] = ref_time / time
                bmk_stat[conf][bmk]['Coverage'] = coverage/count
                bmk_stat[conf][bmk]['IPC'] = total_inst / total_cycle
                bmk_stat[conf][bmk]['mpki_b'] = 1000 * total_misp_b / total_inst
                bmk_stat[conf][bmk]['misrate_b'] = 100 * total_misp_b / total_branches
                bmk_stat[conf][bmk]['mpki_i'] = 1000 * total_misp_i / total_inst
                bmk_stat[conf][bmk]['mpki_r'] = 1000 * total_misp_r / total_inst
                bmk_stat[conf][bmk]['mpki'] = 1000 * total_misp / total_inst
                bmk_stat[conf][bmk]['mpki_j'] = 1000 * total_misp_j / total_inst
                bmk_stat[conf][bmk]['mpki_ftb'] = 1000 * total_miss_ftb / total_inst
                # bmk_stat[conf][bmk]['misrate_ftb'] = total_miss_ftb / total_update_ftb * 100

                if prefix == 'xs_':
                    # bmk_stat[conf][bmk]['mpki_b_ubtb'] = 1000 * total_misp_b_ubtb / total_inst
                    # bmk_stat[conf][bmk]['mpki_b_btb'] = 1000 * total_misp_b_btb / total_inst
                    bmk_stat[conf][bmk]['mpki_c'] = 1000 * total_misp_c / total_inst
                    # bmk_stat[conf][bmk]['misrate_btb'] = total_miss_btb / total_update_ftb * 100
                    bmk_stat[conf][bmk]['mpki_ftb'] = 1000 * total_miss_ftb / total_inst
                    bmk_stat[conf][bmk]['frontend_bubble_pki'] = 1000 * total_frontend_bubble / total_inst
                    bmk_stat[conf][bmk]['s2_redirect_pki'] = 1000 * total_s2_redirect / total_inst
                    # bmk_stat[conf][bmk]['mpki_btb'] = 1000 * total_miss_btb / total_inst
                    bmk_stat[conf][bmk]['mpki_rdc_sc'] = 1000 * total_rdc_sc / total_inst
    int_list = [
        "perlbench", "bzip2", "gcc", "mcf", 
        "gobmk", "hmmer", "sjeng", "libquantum",
        "h264ref", "omnetpp", "astar", "xalancbmk"
    ]
    fp_list = [
        'bwaves', 'gamess', 'milc', 'zeusmp',
        'gromacs', 'cactusADM', 'leslie3d',
        'namd', 'dealII', 'soplex', 'povray',
        'calculix', 'GemsFDTD', 'tonto',
        'lbm', 'sphinx3'
    ]
    for conf in confs:
        print(conf, '='*60)
        df = pd.DataFrame.from_dict(workload_dict[conf], orient='index')
        workload_dict[conf] = df
        # pd.set_option('display.max_columns', None)
        print(df)

        if merge_benckmark:
            df = pd.DataFrame.from_dict(bmk_stat[conf], orient='index')
            bmk_stat[conf] = df
            excluded = df[df['Coverage'] <= min_coverage]
            df = df[df['Coverage'] > min_coverage]
        # # # print(int_df.sort_index())
        # # print(fp_df.sort_index())
        # # print(df.sort_index())
        # int_df.to_csv('spec06_int_'+conf+'.csv')
        # fp_df.to_csv('spec06_fp_'+conf+'.csv')
        # int_df = df.loc[int_list]
        # fp_df = df.loc[fp_list]
        # print_score(int_df, clock_rate, 'INT')
        # print_score(fp_df, clock_rate, 'FP')
        df.to_csv('spec06_total_'+conf+'.csv')
        print_score(df, clock_rate, 'TOTAL')
        if len(list(excluded.index)):
            print('Excluded because of low coverage:', list(excluded.index))


    tests = []
    for conf in confs.keys():
        if conf == base:
            continue
        rel = workload_dict[conf]['IPC']/workload_dict[base]['IPC']
        print(f'{conf}  Mean relative performance: {gmean(rel)}')
        tests.append(rel)
    if len(tests):
        dfx = pd.concat(tests, axis=1)
        print('Relative performance:')
        print(dfx)


def gem5_spec2006():
    ver = '06'
    confs = {
            # 'O1': '/home51/zyy/expri_results/omegaflow_spec17/OmegaH1S1G1Config',
            # 'O2': '/home51/zyy/expri_results/omegaflow_spec17/OmegaH1S1G2CL0Config',
            # 'O1S0': '/home51/zyy/expri_results/omegaflow_spec17/OmegaH1S0G1Config',
            # 'O1X': '/home51/zyy/expri_results/omegaflow_spec17/XOmegaH1S1G1Config',
            # 'O1*-': '/home51/zyy/expri_results/omegaflow_spec17/OmegaH0S0G1Config',
            # 'F1-': '/home51/zyy/expri_results/omegaflow_spec17/FFS0Config',
            # 'F1H': '/home51/zyy/expri_results/omegaflow_spec17/FFH1Config',
            # 'GEM5': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-04-09_22:21:46'
            # 'GEM5_LTAGE': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-11-05_18:02:01',
            # 'GEM5_TAGE': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-11-05_20:52:29',
            # 'GEM5_TAGE_his4-64': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-11-05_20:50:10',
            # 'GEM5_TAGE_his2-128': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-11-05_21:28:09',
            # 'GEM5_TAGE_his4-128': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-11-05_21:31:52',
            # 'new_u_algorithm': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/NanhuNoL3-02624fcac',
            # 'new_base': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/NanhuNoL3-341ad0d23',
            # 'thr_shift_10b': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/NanhuNoL3-59005177e',
            'nanhu-ftb': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-always-taken',
            'nanhu-ftb-no-always-taken': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-no-always-taken',
            'nanhu-ftb-uftb-fixed': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-uftb-fixed',
            'nanhu-ftb-uncond-fixed': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-uncond-slot-fixed',
            'nanhu-ftb-all-fixed': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-all-fixed',
            'nanhu-ftb-false-hit-fixed': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-false-hit-fixed',
            'nanhu-ftb-br-slot-shuffled': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-br-slot-shuffled',
            'nanhu-fetchwidth-fetchqueue-size': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-fetchwidth-fetchqueue-size',
            'nanhu-with-ittage': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-with-ittage',
            'nanhu-with-db-all': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-with-db-all',
            'nanhu-tage-alt-tag': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-tage-alt-tag',
            'nanhu-ittage': '/nfs/home/goulingrui/expri_results/gem5/frontend_06/nanhu-ittage',
            
            # 'GEM5_Tour': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-10-12_21:31:41',
            # 'GEM5_BiMode': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-10-12_21:37:50',
            # 'GEM5hist128': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-06-23_14:08:12',
            # 'GEM5hist256': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-06-23_14:25:29',
            # 'GEM5hist512': '/home51/glr/expri_results/SPEC06/FullWindowO3Config_2021-06-23_14:55:46',
            # 'F2': '/home51/zyy/expri_results/omegaflow_spec17/FFG2CL0CG1Config',
            # 'FullO3': '/home51/zyy/expri_results/omegaflow_spec17/FullWindowO3Config'
            }

    compute_weighted_mpki(
            ver=ver,
            confs=confs,
            # base='new_u_algorithm',
            base='nanhu-ftb',
            simpoints=f'/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_20m/simpoint_summary.json',
            prefix = '',
            stat_file='m5out/stats.txt',
            insts_file_fmt =
            # '/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_50m/profiling/{}/nemu_out.txt',
            '/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_20m/logs/profiling/{}.log',
            # '/bigdata/zzf/spec_cpt/logs/profiling/{}.log',
            clock_rate = 4 * 10**9,
            min_coverage = 0.1,
            # blacklist = ['gamess'],
            # whitelist = ['mcf', 'astar', 'gobmk', 'gcc', 'sjeng', 'bzip2'],
            merge_benckmark=True,
            )


def xiangshan_spec2006(stat_file='main_err.txt'):
    ver = '06'
    confs = {
            # 'XiangShan_decoupled': '/home/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasksConfig_2021-09-03',
            # 'XiangShan_decoupled': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasksConfig_2021-09-06',
            # 'XiangShan_his128': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasksConfig_hist128_2021-10-05',
            # 'XiangShan_his64': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasksConfig_hist64_2021-10-06',
            # 'XiangShan_br1': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasksConfig_br1_2021-10-08',
            # 'XiangShan': '/nfs/home/goulingrui/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_02_15',
            # 'XiangShan_22_06_03': '/nfs/home/goulingrui/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_06_03',
            # 'XiangShan_22_02_12': '/nfs/home/goulingrui/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_02_12',
            # 'XiangShan_22_02_15': '/nfs/home/goulingrui/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_02_15',
            # 'XiangShan_22_08_04': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasks_08_04_2022',
            # 'XiangShan_21_10_10_YQH': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasks_YQH_21_10_10/',
            # 'XiangShan_22_06_10': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasksConfig_2022-06-10',
            # 'XiangShan_old_ubtb': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasksConfig_2022-09-14_emu-faubtb-perf-base-16t',
            # 'XiangShan_fauftb': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasksConfig_2022-09-14_emu-faubtb-perf-16t',
            # 'XiangShan_fauftb_new_mechanism': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasksConfig_2022-09-14_emu-faubtb-perf-new-mechanism-16t',
            # 'XiangShan_nanhu': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasks_12_05_2022',
            'XiangShan_nanhu_gcb': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasks_12_03_2022',
            # 'XiangShan_22_01_07': '/nfs/home/goulingrui/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_01_07',
            # 'XiangShan_22_03_19': '/nfs/home/goulingrui/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_03_19',
            # 'XiangShan_21_12_12': '/nfs/home/goulingrui/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_12_12',
            # 'XiangShan_22_08_21': '/nfs/home/goulingrui/expri_results/xs_simpoint_batch/SPEC06_EmuTasks_08_21_2022',
            # 'XiangShanNew': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_01_07',
            # 'lzs_run' :'/home/lzs/project/run_spec06/output1020',
            # 'XiangShan_master_fp_0.3': '/home/ljw/master-40-perf/output',
            # 'XiangShan2': '/home51/glr/expri_results/xs_simpoint_batch/emu-master-4t/SPEC06_EmuTasksConfig'
            # 'XiangShan_yqh': '/home/glr/SPEC06_EmuTasksConfig-04-27-2021',
            # 'no-ium': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasksConfig_hist64_2021-10-06',
            # 'ium': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasksConfig_ium_2021-10-10',
            
            # 'XiangShan_master_10-28': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_10_28_2021_cov100',
            # 'XiangShan_master_10-22': '/home53/glr/spec_output/xs_simpoint_batch/SPEC06_EmuTasks_10_22_2021_cov100',
            }
    int_list = [
        "perlbench", "bzip2", "gcc", "mcf", 
        "gobmk", "hmmer", "sjeng", "libquantum",
        "h264ref", "omnetpp", "astar", "xalancbmk"
        ]
    bp_list = [
        "perlbench", "povray", "astar", "gcc",
        "omnetpp", "mcf", "soplex", "bzip2",
        "namd", "sjeng", "hmmer", "xalancbmk", "sphinx3"
    ]
    fp_list = []
    # white_list = bp_list
    white_list = []
    # white_list = ['astar', 'bzip2']
    black_list = []
    # black_list = ['mcf', 'omnetpp', 'astar']
    # if (int_stat and not fp_stat):
    #     white_list = int_list
    # elif (fp_stat and not int_stat):
    #     black_list = int_list
    compute_weighted_mpki(
            ver=ver,
            confs=confs,
            # base='XiangShan_master_10-28',
            # base='XiangShan_master_10-22',
            # base='XiangShan_decoupled',
            # base='XiangShan_22_02_12',
            # base='XiangShan_22_02_15',
            # base='XiangShan_21_10_10_YQH',
            # base='XiangShan_22_06_10',
            # base='XiangShan_22_08_21',
            # base='XiangShan_nanhu',
            base='XiangShan_nanhu_gcb',
            # base='lzs_run',
            # simpoints=f'/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_20m/simpoint_summary.json',
            # simpoints=f'/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_50m/simpoint_summary.json',
            simpoints=f'/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gcb_o2_20m/json/simpoint_summary.json',
            # simpoints=f'/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gcb_o2_20m/json/simpoint_coverage0.3_test.json',
            
            prefix = 'xs_',
            stat_file=stat_file,
            insts_file_fmt =
            # '/bigdata/zzf/spec_cpt/logs/profiling/{}.log',
            '/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gcb_o2_20m/logs/profiling/{}.log',
            # '/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_20m/logs/profiling/{}.log',
            # '/nfs-nvme/home/share/checkpoints_profiles/spec06_rv64gc_o2_50m/profiling/{}/nemu_out.txt',
            # '/bigdata/zyy/checkpoints_profiles/betapoint_profile_06_fix_mem_addr/{}/nemu_out.txt',
            clock_rate = 2 * 10**9,
            min_coverage = 0.1,
            # blacklist = int_list,
            whitelist = white_list,
            blacklist = black_list,
            # whitelist = bp_list,
            # whitelist = ['gobmk'],
            # blacklist = ['gcc_expr2'],
            merge_benckmark=True,
            )



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', action='store', choices=['xs', 'gem5'], type=str)
    parser.add_argument('--stat-file', action='store', type=str)
    parser.add_argument('--simpoint-json', action='store', type=str)
    parser.add_argument('--inst-profile', action='store', type=str)
    parser.add_argument('--spec-result', action='store', type=str)
    
    args = parser.parse_args()
    if (args.mode == 'gem5'):
        gem5_spec2006()
    else:
        if (args.stat_file):
            xiangshan_spec2006(args.stat_file)
        else:
            xiangshan_spec2006()
