import sqlite3
import argparse
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import re
import os
import sys
import time
sys.path.append('/nfs/home/goulingrui/project/gem5_data_proc')
from utils.common import reverse_readline

res_dir_name = 'fetch_result'

cache_block_size = 64

xs_disassembly_file = '/nfs/home/share/verilator_gcc10_20m/bins/xs-qsort-64/workload.txt'
rocket_disassembly_file = '/nfs/home/share/verilator_gcc10_20m/bins/rocket-dhrystone/workload.txt'

# 定义一个装饰器来测量函数的运行时间
def time_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()  # 记录函数开始运行的时间
        result = func(*args, **kwargs)  # 调用原始函数
        end_time = time.time()  # 记录函数结束运行的时间
        print(f"{func.__name__} ran in: {end_time - start_time} sec")  # 打印运行时间
        return result  # 返回原始函数的返回值
    return wrapper

def get_total_cache_lines_from_dissasembly(disassembly_file):
    # inst pattern: \x+: \x+
    inst_pattern = re.compile(r"\s+([0-9a-f]+):\s+([0-9a-f]+)\s+.*")
    # read the disassembly file from start and get the first inst addr
    # TODO: inst_addr = ...
    # read the disassembly file from the end and get the last inst addr
    # TODO: last_inst_addr = ...
    # total_cache_lines = (last_inst_addr - inst_addr) / cache_block_size
    with open(disassembly_file, 'r') as f:
        line = f.readline()
        while line :
            debug_print(line)
            # if match, get the first inst addr
            match = inst_pattern.match(line)
            if match:
                inst_addr = int(match.group(1), 16)
                debug_print(f"inst addr: {inst_addr:#x}")
                break
            line = f.readline()

    for line in reverse_readline(disassembly_file):
        debug_print(line)
        match = inst_pattern.match(line)
        if match:
            last_inst_addr = int(match.group(1), 16)
            debug_print(f"last inst addr: {last_inst_addr:#x}")
            break

    total_cache_lines = (last_inst_addr - inst_addr) / cache_block_size
    return total_cache_lines, inst_addr, last_inst_addr

# call_ret = c.execute("SELECT * FROM BPTRACE WHERE taken == 1 AND (controlType == 2 OR controlType >= 4)")
# target_branch = c.execute("SELECT * FROM BPTRACE WHERE controlPC == 0x223d0")
# target_branch = c.execute("SELECT * FROM BPTRACE WHERE controlType == 0")

# c.execute("ALTER TABLE TAGEENTRYLIFETIMETRACE ADD COLUMN lifetime INTEGER AS (end - start) VIRTUAL")
# c.execute(")
# tage_entries = c.execute("SELECT *, Count(*) FROM TAGEENTRYLIFETIMETRACE GROUP BY startPC ORDER BY Count(*) DESC")
# SELECT *, Count(*) FROM TAGEENTRYLIFETIMETRACE GROUP BY startPC ORDER BY Count(*) DESC

# def print_tage_entry(row):
#     (id, tick, end, idx, phyBrIdx, start, startPC, tableIdx, correct, wrong, count, lifetime) = row
#     print("id %10d, lifetime %10d, startPC %#10lx, tableIdx %d, phyBrIdx %d "\
#           "correct %d wrong %d, count %d" %
#           (id, lifetime, startPC, tableIdx, phyBrIdx, correct, wrong, count))
debug = False
def debug_print(*args):
    if debug:
        print(*args)


def get_dir(db_path):
    return os.path.dirname(db_path)

# db_path = /../workload/checkpoint/bp.db
# get 'workload_checkpoint' from db_path
def get_checkpoint_name(db_path):
    checkpoint = os.path.basename(os.path.dirname(db_path))
    workload = os.path.basename(os.path.dirname(os.path.dirname(db_path)))
    return workload + '_' + checkpoint
    

def print_tage_entry(row):
    print(row)
    # get first 11 columns
    (id, cycle, brPC, end, idx, oldPC, phyBrIdx, start, startPC, tableIdx, correct, wrong) = row[:12]
    # (id, cycle, brPC, end, idx, phyBrIdx, start, startPC, tableIdx, correct, wrong) = row
    lifetime = end-start
    debug_print("id %10d, lifetime %10d, startPC %#10lx, brPC %#10lx, oldBrPC %#10lx, tableIdx %d, phyBrIdx %d "\
          "correct %d wrong %d start %10d end %10d" %
          (id, lifetime, startPC, brPC, oldPC, tableIdx, phyBrIdx, correct, wrong, start, end))

def print_entries(tage_entries):
    for entry in tage_entries:
        # debug_print(entry)
        print_tage_entry(entry)

# (id, tick, controlPC, controlType, fallThruPC, mispred, source, startPC, taken, target)
def print_bp_trace(row):
    (id, tick, controlPC, controlType, fallThruPC, mispred, source, startPC, taken, target) = row
    debug_print("id %10d, cycle %10d, startPC %#10lx, controlPC %#10lx, fallThruPC %#10lx, "\
          "target %#10lx, type %d, taken %d, source %d, mispred %d, rasOp %s" %
          (id, tick, startPC, controlPC, fallThruPC, target, controlType, taken,
           source, mispred, controlType))
    return (controlType, fallThruPC, target)

def print_normal_branch(row):
    debug_print(row)

def align_block_pc(pc, block_size):
    return (pc // block_size) * block_size

def align_next_block_pc(pc, block_size):
    return align_block_pc(pc, block_size) + block_size

def get_one_item_from_trace(cursor, trace):
        cursor.execute(f"SELECT * FROM {trace}")
        next_item = cursor.fetchone()
        while next_item is not None:
            yield next_item
            next_item = cursor.fetchone()

# fetch trace is defined to be the sequence of demand instruction cache blocks
# how to get the fetch trace from branch trace:
# the principle is: only a taken branch may prevent fetch pc from going fall through
# we could use a helper variable: fetch_pc to record the current fetch pc
# first set fetch pc to the first branch's start pc, and align to the block boundary
# check each branch in the branch trace until a taken one is found, then add all the cache blocks from current fetch_pc
# to the branch's fall through pc to the fetch trace
# set fetch_pc to the branch's target, align to the block boundary, and repeat the process
def construct_fetch_trace_from_branch_trace(db_connect, cache_block_size):
    def get_one_branch_from_trace(cursor):
        return get_one_item_from_trace(cursor, 'BPTRACE')
    branch_trace_cursor = db_connect.cursor()
    # construct fetch trace as a new table
    fetch_trace_cursor = db_connect.cursor()
    fetch_trace_cursor.execute("DROP TABLE IF EXISTS FETCHTRACE")
    # enter_pc would be the target of a previous branch which jumps to current block, or it will be the cache block boundary
    # out_pc would be the fall-through pc of a branch taken out of current block if the branch is fully in this cache block, or it will be the cache block boundary
    fetch_trace_cursor.execute("CREATE TABLE FETCHTRACE (id INTEGER PRIMARY KEY, enter_pc INTEGER, out_pc INTEGER, jump_in INTEGER, jump_out INTEGER)")
    db_connect.commit()
    # cursor is a sqlite3 cursor
    first_branch = get_one_branch_from_trace(branch_trace_cursor).__next__()
    # set initial fetch_pc
    fetch_pc = first_branch['startPC']
    debug_print("first branch: control PC %#lx, taken %d, fall through %#lx, target %#lx, fetch_pc is %#lx" % (
        first_branch['controlPC'], first_branch['taken'], first_branch["fallThruPC"], first_branch["target"], fetch_pc))
    if first_branch['taken']:
        # insert a block containing the first branch
        fetch_trace_cursor.execute("INSERT INTO FETCHTRACE (enter_pc, out_pc, jump_in, jump_out) VALUES (?, ?, ?, ?)",
                        (fetch_pc, first_branch['fallThruPC'], 1, 1))
        debug_print("insert the first block containing the first branch: enter %#lx, jump_in %d, out %#lx, jump_out %d" %
                (fetch_pc, 1, first_branch['fallThruPC'], 1))
        fetch_pc = first_branch['target']
    
    first_encountered = False
    for branch in get_one_branch_from_trace(branch_trace_cursor):
        debug_print("control PC %#lx, taken %d, fall through %#lx, %s fetch_pc is %#lx" % (
            branch['controlPC'], branch['taken'], branch["fallThruPC"], f"target {branch['target']:#x}" if branch['taken'] else "", fetch_pc))
        if not first_encountered:
            first_encountered = True
            debug_print("discard the first branch")
            continue
        if not branch['taken']:
            continue
        
        # now we get a taken branch
        debug_print("this basic block is [%#lx,%#lx)" % (fetch_pc, branch['fallThruPC']))
        # try add the first block after the previous branch to the fetch trace
        # first check if the first block jumps out of itself, in which case the "basic block"(regions between two branches) contains only one block
        aligned_fetch_pc = align_block_pc(fetch_pc,cache_block_size)
        aligned_next_fetch_pc = align_next_block_pc(fetch_pc,cache_block_size)
        debug_print("fetch pc is %#lx, aligned to %#lx, aligned next fetch pc %#lx" % (fetch_pc, aligned_fetch_pc, aligned_next_fetch_pc))
        if branch["fallThruPC"] <= aligned_next_fetch_pc:
            fetch_trace_cursor.execute("INSERT INTO FETCHTRACE (enter_pc, out_pc, jump_in, jump_out) VALUES (?, ?, ?, ?)",
                        (fetch_pc, branch['fallThruPC'], 1, 1))
            debug_print("insert the first block after taken branch (immediately out): enter %#lx, jump_in %d, out %#lx, jump_out %d" % (fetch_pc, 1, branch['fallThruPC'], 1))
            # set fetch_pc to the target since we've got to the taken branch
            fetch_pc = branch['target']
            debug_print("set fetch_pc to target %#lx" % fetch_pc)
            continue
        else:
            fetch_trace_cursor.execute("INSERT INTO FETCHTRACE (enter_pc, out_pc, jump_in, jump_out) VALUES (?, ?, ?, ?)",
                            (fetch_pc, aligned_next_fetch_pc, 1, 0))
            debug_print("insert the first block after taken branch (fall through): enter %#lx, jump_in %d, out %#lx, jump_out %d" % (fetch_pc, 1, aligned_next_fetch_pc, 0))
            fetch_pc += cache_block_size
            aligned_fetch_pc = align_block_pc(fetch_pc,cache_block_size)
            aligned_next_fetch_pc = align_next_block_pc(fetch_pc,cache_block_size)
        
        # try to add the blocks between the first block and the block containing the fall through pc
        while aligned_fetch_pc < branch['fallThruPC']:
            debug_print("fetch pc is %#lx, aligned to %#lx, fall through is %#lx" %
                    (fetch_pc, aligned_fetch_pc, branch['fallThruPC']))
            # Add the cache block to the fetch trace
            if aligned_next_fetch_pc >= branch['fallThruPC']:
                # The block contains the fall-through pc
                fetch_trace_cursor.execute("INSERT INTO FETCHTRACE (enter_pc, out_pc, jump_in, jump_out) VALUES (?, ?, ?, ?)",
                               (aligned_fetch_pc, branch['fallThruPC'], 0, 1))
                debug_print("insert the block containing fall through: enter %#lx, jump_in %d, out %#lx, jump_out %d" % (aligned_fetch_pc, 0, branch['fallThruPC'], 1))
                # set fetch_pc to the target since we've got to the taken branch
                fetch_pc = branch['target']
                debug_print("set fetch_pc to target %#lx" % fetch_pc)
                break
            else:
                fetch_trace_cursor.execute("INSERT INTO FETCHTRACE (enter_pc, out_pc, jump_in, jump_out) VALUES (?, ?, ?, ?)",
                           (aligned_fetch_pc, aligned_next_fetch_pc, 0, 0))
                debug_print("insert a fall through block: enter %#lx, jump_in %d, out %#lx, jump_out %d" %
                        (aligned_fetch_pc, 0, aligned_next_fetch_pc, 0))
            fetch_pc += cache_block_size
            aligned_fetch_pc = align_block_pc(fetch_pc,cache_block_size)
            aligned_next_fetch_pc = align_next_block_pc(fetch_pc,cache_block_size)
            debug_print("set fetch_pc to next block %#lx" % fetch_pc)
            
    # print fetch trace
    fetch_trace = fetch_trace_cursor.execute("SELECT * FROM FETCHTRACE")
    for block in fetch_trace:
        debug_print("enter %#lx, jump_in %d, out %#lx, jump_out %d" %
              (block['enter_pc'], block['jump_in'], block['out_pc'], block['jump_out']))
    
def check_column_existence(cursor, table_name, column_name):
    cursor.execute("PRAGMA table_xinfo(%s)" % table_name)
    rows = cursor.fetchall()
    # debug_print(rows)
    for row in rows:
        if row[1] == column_name:
            return True
    return False

def check_table_existence(cursor, table_name):
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None

@time_decorator
def extract_fetch_trace_basic_info(db_connect, workload, db_path):
    cursor = db_connect.cursor()
    # total accesses
    cursor.execute("SELECT COUNT(*) FROM fetchTrace")
    total_accesses = cursor.fetchone()[0]
    # cache miss
    cursor.execute("SELECT COUNT(*) FROM fetchTrace WHERE cacheMiss == 1")
    cache_miss = cursor.fetchone()[0]
    # count flushed cachelines
    cursor.execute("SELECT COUNT(*) FROM fetchTrace WHERE flushType == 2")
    flushed_cache_lines = cursor.fetchone()[0]

    percent_miss = cache_miss / total_accesses * 100
    percent_flushed = flushed_cache_lines / total_accesses * 100
    print(f"total accesses: {total_accesses}, flushed: {flushed_cache_lines}({percent_flushed:.2f}%), miss: {cache_miss}({percent_miss:.2f}%)")

    # count flushed missed cachelines
    cursor.execute("SELECT COUNT(*) FROM fetchTrace WHERE flushType == 2 AND cacheMiss == 1")
    flushed_missed_cache_lines = cursor.fetchone()[0]
    percent_flush_miss_total = flushed_missed_cache_lines / total_accesses * 100
    percent_flush_miss_flush = flushed_missed_cache_lines / flushed_cache_lines * 100
    percent_flush_miss_miss = flushed_missed_cache_lines / cache_miss * 100
    print(f"flushed missed: {flushed_missed_cache_lines}, {percent_flush_miss_total:.2f}%(total), {percent_flush_miss_flush:.2f}%(flush), {percent_flush_miss_miss:.2f}%(miss)")

    # average miss latency
    cursor.execute("SELECT AVG(cacheLatency) FROM fetchTrace WHERE cacheMiss == 1")
    avg_cache_latency = cursor.fetchone()[0]
    print("average cache latency:", avg_cache_latency)
    
    # cache miss caused by branch
    cursor.execute("SELECT COUNT(*) FROM fetchTrace WHERE cacheMiss == 1 AND jumpIn == 1")
    jump_in_miss = cursor.fetchone()[0]
    print("cache miss caused by branch:", jump_in_miss)
    
    # tlb misses
    cursor.execute("SELECT COUNT(*) FROM fetchTrace WHERE tlbMiss > 0")
    tlb_miss = cursor.fetchone()[0]
    # tlb miss caused by branch
    cursor.execute("SELECT COUNT(*) FROM fetchTrace WHERE tlbMiss > 0 AND jumpIn == 1")
    jump_in_tlb_miss = cursor.fetchone()[0]
    print(f"tlb miss: {tlb_miss}, caused by branch: {jump_in_tlb_miss}")
    # group by jump in branch type
    cursor.execute("SELECT COUNT(*), jumpInBranchType FROM fetchTrace WHERE tlbMiss > 0 AND jumpIn == 1 GROUP BY jumpInBranchType")
    print("tlb miss caused by branch type:")
    for row in cursor.fetchall():
        # branch type, miss
        print(f"type: {row[0]}, miss: {row[1]}")
        # print(row)

    # count each cache line's frequency in descending order
    # first align enterPC to 64Bytes boundary
    # count misses for each aligned enterPC and caculate miss rate
    
    if not check_column_existence(cursor, 'fetchTrace', 'aligned'):
        cursor.execute("ALTER TABLE fetchTrace ADD COLUMN aligned INTEGER AS (enterPC & ~63) VIRTUAL")
    if not check_column_existence(cursor, 'fetchTrace', 'total_flushed'):
        cursor.execute("ALTER TABLE fetchTrace ADD COLUMN total_flushed INTEGER AS (flushType == 2) VIRTUAL")
    if not check_column_existence(cursor, 'fetchTrace', 'tlb_real_miss'):
        cursor.execute("ALTER TABLE fetchTrace ADD COLUMN tlb_real_miss INTEGER AS (tlbMiss > 0) VIRTUAL")
    cursor.execute("SELECT aligned, COUNT(*), SUM(cacheMiss), SUM(total_flushed), AVG(cacheLatency), SUM(tlb_real_miss), AVG(tlbLatency) FROM fetchTrace GROUP BY aligned ORDER BY COUNT(*) DESC")
    all_cache_lines = cursor.fetchall()
    
    # percentage of cache lines that checkpoint touched
    disassembly_file = eval(f"{workload}_disassembly_file")
    workload_cache_lines, start_addr, end_addr = get_total_cache_lines_from_dissasembly(disassembly_file)
    print(f"unique cache lines: {len(all_cache_lines)}, workload all: {workload_cache_lines}")
    # get touched cache lines that within start and end
    cursor.execute("SELECT COUNT(DISTINCT aligned) FROM fetchTrace WHERE aligned >= ? AND aligned < ?", (start_addr, end_addr))
    touched_cache_lines = cursor.fetchone()[0]
    percent_touched_of_workload = touched_cache_lines / workload_cache_lines * 100
    print(f"touched cache lines in workload: {touched_cache_lines}, {percent_touched_of_workload:.2f}%")
    # exit()
    for row in all_cache_lines:
        print(f"cache line pc {row[0] & 0xFFFFFFFFFFFFFFFF:#18x}, frequency {row[1]:7d}, miss {row[2]:5d}, miss rate {row[2]/row[1]*100:.2f}%, flushed {row[3]/row[1]*100:.2f}%, avg latency {row[4]:.2f}, tlb miss {row[5]}, tlb miss rate {row[5]/row[1]*100:.2f}%, tlb avg latency {row[6]:.2f}")
    # save to csv, columns: aligned, frequency, miss, flushed, avg_latency, tlb_miss, tlb_avg_latency
    # format aligned to 16 hex digits
    df=pd.DataFrame(all_cache_lines, columns=['aligned', 'frequency', 'miss', 'flushed', 'avg_latency', 'tlb_miss', 'tlb_avg_latency'])
    df['aligned'] = df['aligned'].apply(lambda x: format(x & 0xFFFFFFFFFFFFFFFF, 'X'))
    df.to_csv(os.path.join(get_dir(db_path), res_dir_name, 'cache_lines.csv'), index=False)

    # drop first 5M rows

    # draw a scatter graph of cache access addresses by time
    # x: id, y: access address(enterPC or aligned)
    @time_decorator
    def draw_scatter_of_workload_cachelines(filtered_cursor, end_addr, name, drop=None, _marker='o', _s=1):
        fetch_trace = filtered_cursor.fetchall()
        if drop:
            fetch_trace = fetch_trace[drop:]
        fetch_trace_df = pd.DataFrame(fetch_trace, columns=['id', 'enterPC'])
        fetch_trace_df['enterPC'] = fetch_trace_df['enterPC'].astype('uint64')
        plt.scatter(fetch_trace_df['id'], fetch_trace_df['enterPC'], s=_s, marker=_marker)
        # Define a formatter for the y-axis that displays values as hexadecimal
        formatter = ticker.FuncFormatter(lambda x, pos: f"{int(x):X}")

        # Apply the formatter to the y-axis
        plt.gca().yaxis.set_major_formatter(formatter)

        plt.ylim(0, end_addr)
        # fetch_trace_df.plot(x='id', y='enterPC')
        # plt.show()
        plt.savefig(os.path.join(get_dir(db_path), res_dir_name, name))
    # # draw a line graph of cache access addresses by time
    # cursor.execute("SELECT id, enterPC FROM fetchTrace")
    # draw_scatter_of_workload_cachelines(cursor, end_addr, 'fetch_trace_all.png')
    cursor.execute("SELECT id, enterPC FROM fetchTrace WHERE flushType < 2")
    # print(len(cursor))
    draw_scatter_of_workload_cachelines(cursor, end_addr, 'fetch_trace_not_flushed.png', _s=0.3)
    cursor.execute("SELECT id, enterPC FROM fetchTrace WHERE flushType == 2")
    draw_scatter_of_workload_cachelines(cursor, end_addr, 'fetch_trace_with_flushed.png', _marker='x')
    cursor.execute("SELECT id, aligned FROM fetchTrace WHERE tlbMiss > 0")
    draw_scatter_of_workload_cachelines(cursor, end_addr, 'fetch_trace_with_tlb_miss.png', _marker='p')
    
    # for a special cacheline, get its previous n cachelines everytime it misses
    @time_decorator
    def get_miss_lines_around(db_connect, line_addr, n, require_miss=True):
        out_cursor = db_connect.cursor()
        out_cursor.execute("SELECT id, enterPC FROM fetchTrace WHERE aligned == ? AND cacheMiss == 1", (line_addr,))
        miss_line = out_cursor.fetchone()
        all_previous_lines = []
        occurrence = 0
        while miss_line is not None:
            miss_id = miss_line[0]
            sub_cursor = db_connect.cursor()
            sub_cursor.execute("SELECT id, enterPC, aligned, cacheMiss, flushType FROM fetchTrace WHERE id < ? AND id >= ? ORDER BY id DESC", (miss_id+n, miss_id-n))
            prev_lines = sub_cursor.fetchall()
            all_previous_lines.append(prev_lines)
            # output
            print(f"miss line {miss_line[1]:#x} occurrence {occurrence}, id {miss_id}, previous {n} lines:")
            i = 0
            for line in prev_lines:
                print(f"line {line[1]:#x}, aligned {line[2]:#x}, miss {line[3]:d}, flushType {line[4]:d}")
                if i == n:
                    print("----")
                i += 1
            print("---------------")
            miss_line = out_cursor.fetchone()
        return all_previous_lines
    
    get_miss_lines_around(db_connect, 0x13a140, 10)

@time_decorator
def ftb_analysis(db_connect, db_path):
    cursor = db_connect.cursor()
    # total accesses
    cursor.execute("SELECT COUNT(*) FROM FTBTRACE")
    total_accesses = cursor.fetchone()[0]
    
    
    # maintain an ftb table
    ftb_way = 4
    ftb_set = 512
    ftb = np.array([[0 for _ in range(ftb_way)] for _ in range(ftb_set)])
    
    numBr = 2
    def count_entry_of_different_branch_num(ftb):
        entry_num = []
        for i in range(numBr):
            num = np.sum(ftb == (i+1))
            entry_num.append(num)
            print(f"branch num {i} entry count: {num}")
    
    def count_branch_num_in_ftb_record(record):
        num = 0
        for i in range(numBr):
            if record[f"br_{i}_valid"] == 1:
                num += 1
        return num
    
    iterate_cursor = db_connect.cursor()
    def get_one_record_from_ftb_trace(cursor):
        return get_one_item_from_trace(cursor, 'FTBTRACE')

    from enum import Enum, auto

    class EntryType(Enum):
        EMPTY = 0
        ONE_COND = 2
        ONE_UNCOND = 3
        TWO_CONDS = 4
        ONE_COND_ONE_UNCOND = 5

    def get_entry_type(record):
        # enum: 1*cond, 1*uncond, 2*cond, 1*cond+1*uncond
        ty = 0
        for i in range(numBr):
            if record[f"br_{i}_valid"] == 1:
                if record[f"br_{i}_type"] == 0:
                    ty += 2
                else:
                    ty += 3
        return EntryType(ty)

    def get_num_branch_from_entry_type(ty):
        debug_print(ty)
        if ty == EntryType.EMPTY:
            return 0
        elif ty == EntryType.ONE_COND or ty == EntryType.ONE_UNCOND:
            return 1
        elif ty == EntryType.TWO_CONDS:
            return 2
        elif ty == EntryType.ONE_COND_ONE_UNCOND:
            return 2
        else:
            return -1

    num_entry_of_branch_num = [0 for _ in range(numBr)]
    num_entry_of_each_type = {}
    for ty in EntryType:
        num_entry_of_each_type[ty] = 0
    num_entry_of_each_type[EntryType.EMPTY] = ftb_set * ftb_way

    current_cycle = 0
    df = pd.DataFrame(columns=['cycle', '1-branch-entry', '2-branch-entry']+list(EntryType.__members__.keys()))
    for record in get_one_record_from_ftb_trace(iterate_cursor):
        idx = record['idx']
        way = record['way']
        cycle = record['CYCLE']
        branch_num = count_branch_num_in_ftb_record(record)
        entry_type = get_entry_type(record)
        
        df_row = {'cycle': current_cycle}
        s = ''
        for i in range(numBr):
            s += f", {i+1}_branch_entry: {num_entry_of_branch_num[i]}"
            df_row[f'{i+1}-branch-entry'] = num_entry_of_branch_num[i]
        for ty in EntryType:
            s += f", {ty.name}: {num_entry_of_each_type[ty]}"
            df_row[ty.name] = num_entry_of_each_type[ty]
        debug_print(f"idx {idx}, way {way}, cycle {cycle}, branch num {branch_num}")
        prev_entry_type = EntryType(ftb[idx][way])
        if prev_entry_type != entry_type:
            df = pd.concat([df, pd.DataFrame([df_row])], ignore_index=True)
            print(f"cycle {current_cycle} to {cycle}{s}")
            prev_branch_num = get_num_branch_from_entry_type(prev_entry_type)
            debug_print(f"prev branch num {prev_branch_num}, type {prev_entry_type.name} of idx {idx}, way {way}")
            if prev_branch_num > 0:
                num_entry_of_branch_num[prev_branch_num-1] -= 1
            num_entry_of_branch_num[branch_num-1] += 1
            
            num_entry_of_each_type[prev_entry_type] -= 1
            num_entry_of_each_type[entry_type] += 1
            ftb[idx][way] = entry_type.value
            current_cycle = cycle
        
    # plot df, two graphs:
    # entry of one/two branches, entry of each type
    # both graphs have x-axis as cycle, y-axis as entry number
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    df.plot(x='cycle', y=['1-branch-entry', '2-branch-entry'], ax=ax1)
    ax1.set_title('Entry number of one/two branches')
    ax1.set_ylabel('Entry number')
    ax1.set_xlabel('Cycle')
    # 1M cycles per tick
    ax1.xaxis.set_major_locator(ticker.MultipleLocator(100000))
    # the sum of each entry type should be equal to the total number of entries
    # thus we want to draw a stack area chart
    df.plot.area(x='cycle', y=list(EntryType.__members__.keys()), ax=ax2, stacked=True)
    ax2.set_title('Entry number of each type')
    ax2.set_ylabel('Entry number')
    ax2.set_xlabel('Cycle')
    ax2.xaxis.set_major_locator(ticker.MultipleLocator(100000))
    
    plt.tight_layout()
    
    fig.savefig(os.path.join(get_dir(db_path), res_dir_name, 'ftb_analysis.png'))
    
    
        
def branch_analysis(db_connect, db_path):
    cursor = db_connect.cursor()
    # per branch taken rate
    if not check_table_existence(cursor, 'taken_percent'):
        print("aaaaaa")
        cursor.execute("""
        CREATE TABLE taken_percent AS
        WITH CTE AS (
            SELECT
                controlPC,
                COUNT(*) AS num,
                -- 计算taken为1的百分比
                SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS taken_percentage,
                -- 选择不等于fallThruPC的target值
                MAX(CASE WHEN target != fallThruPC THEN target ELSE NULL END) AS jump_target,
                SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) AS taken_num
            FROM
                BPTRACE
            WHERE
                controlType == 0
            GROUP BY
                controlPC
        )
        SELECT
            *
        FROM
            CTE
        """)
        
        # calculate each branch's offset bits needed and write to table
        # offset bits are defined to be the minimum bits needed to represent the distance between controlPC and jump_target

        cursor.execute("ALTER TABLE taken_percent ADD COLUMN offset_bits INTEGER")
        cursor.execute("""
            UPDATE taken_percent
            SET offset_bits = CASE
                WHEN jump_target IS NULL THEN 0
                ELSE CAST(CEIL(LOG2(ABS(jump_target - controlPC) + 1)) AS INTEGER)
            END;""")
        

    
    cursor.execute("SELECT COUNT(*) FROM taken_percent;")
    total_static_cond = cursor.fetchone()[0]
    print("total static conditional branches:", total_static_cond)
    
    # save to csv
    cursor.execute("SELECT * FROM taken_percent;")
    all_branches = cursor.fetchall()
    df = pd.DataFrame(all_branches, columns=['controlPC', 'num', 'taken_percentage', 'jump_target', 'taken_num', 'offset_bits'])
    # print first 10 rows
    print(df.head(10))
    # set controlPC and jump_target to hex
    df['controlPC'] = df['controlPC'].apply(lambda x: format(x, 'x'))
    # jump_target is float, convert jump_target to int then hex, if jump_target is null, set it to 0
    df['jump_target'] = df['jump_target'].fillna(0)
    df['jump_target'] = df['jump_target'].apply(lambda x: format(int(x), 'x'))
    df.to_csv(os.path.join(get_dir(db_path), res_dir_name, 'branch_taken_percentage.csv'), index=False)
    
    
    cursor.execute("SELECT COUNT(*), SUM(num) FROM taken_percent WHERE taken_percentage == 100.0;")
    [always_taken_static, always_taken_dynamic] = cursor.fetchone()
    print(f"always taken static: {always_taken_static}, dynamic {always_taken_dynamic}")
    if not always_taken_dynamic:
        always_taken_dynamic = 0
    static_list = [always_taken_static]
    dynamic_list = [always_taken_dynamic]
    name_list = ['always taken']
    
    # cursor.execute("SELECT * FROM taken_percent WHERE taken_percentage == 100.0;")
    # print("always taken branches:")
    
    ################### always taken detailed #######################
    for num in range(10):
        cursor.execute(f"SELECT COUNT(*), SUM(num) FROM taken_percent WHERE taken_percentage == 100.0 AND num == {num};")
        [st, dy] = cursor.fetchone()
        print(f"always taken branches occurring {num+1} times static {st}, dynamic {dy}:")
    cursor.execute("SELECT COUNT(*), SUM(num) FROM taken_percent WHERE taken_percentage == 100.0 AND num > 10;")
    [st, dy] = cursor.fetchone()
    print(f"always taken branches occurring more than 10 times static {st}, dynamic {dy}")
    
    
    ################ partially taken detailed #######################
    cursor.execute("SELECT COUNT(*) FROM taken_percent WHERE taken_percentage != 0.0 AND taken_percentage != 100.0;")
    print("partially taken:", cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM taken_percent WHERE taken_percentage > 90.0 AND taken_percentage != 100.0;")
    print("partially taken > 90%:", cursor.fetchone()[0])
    for i in range(10):
        cursor.execute("SELECT COUNT(*), SUM(num) FROM taken_percent WHERE taken_percentage > (10.0 * ?) AND taken_percentage <= (10.0 * ?) AND taken_percentage != 100.0;" , (9-i, 10-i))
        [st, dy] = cursor.fetchone()
        if not dy:
            dy = 0
        static_list.append(st)
        dynamic_list.append(dy)
        name_list.append(f"{10*(9-i)}%~{10*(10-i)}%")
        print(f"partially taken ({10*(9-i)}%, {10*(10-i)}%{']' if i != 0 else ')'}:", st, ", occurrence: ", dy)
    
    ################# never taken detailed #######################
    cursor.execute("SELECT COUNT(*), SUM(num) FROM taken_percent WHERE taken_percentage == 0.0;")
    [never_taken_static, never_taken_dynamic] = cursor.fetchone()
    if not never_taken_dynamic:
        never_taken_dynamic = 0
    static_list.append(never_taken_static)
    dynamic_list.append(never_taken_dynamic)
    name_list.append('never taken')
    print(f"never taken static: {never_taken_static}, dynamic {never_taken_dynamic}")
    
    # cursor.execute("SELECT * FROM taken_percent WHERE taken_percentage == 0.0;")
    for num in range(10):
        cursor.execute(f"SELECT COUNT(*), SUM(num) FROM taken_percent WHERE taken_percentage == 0.0 AND num == {num};")
        [st, dy] = cursor.fetchone()
        print(f"never taken branches occurring {num+1} times static {st}, dynamic {dy}:")
        
    cursor.execute("SELECT COUNT(*), SUM(num) FROM taken_percent WHERE taken_percentage == 0.0 AND num > 10;")
    [st, dy] = cursor.fetchone()
    print(f"always not taken branches occurring more than 10 times static {st}, dynamic {dy}")
    
    # draw bar chart of static
    
    # draw bar chart seperatedly by static and dynamic of two graphs
        
    x = np.arange(len(name_list))
    print(x)
    width = 0.7
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    
    rects1 = ax1.bar(x, static_list, width, label='static')
    ax1.set_ylabel('Branches')
    ax1.set_title('Static Conditional Branches by taken percentage')
    ax1.set_xticks(x)
    ax1.set_xticklabels(name_list, rotation=45, ha='right')
    ax1.legend()

    rects2 = ax2.bar(x, dynamic_list, width, label='dynamic')
    ax2.set_ylabel('Branches')
    ax2.set_title('Dynamic Conditional Branches by taken percentage')
    ax2.set_xticks(x)
    ax2.set_xticklabels(name_list, rotation=45, ha='right')
    # ax2.tick_params(axis='x', rotation=45, ha='right')
    ax2.legend()
    

    # plt.xticks(rotation=45)
    fig.tight_layout()
    plt.savefig(os.path.join(get_dir(db_path), res_dir_name, 'branch_taken_percentage.png'))
    
    ############ branch offset bits stacked line graph ############
    # 百分比累计折线图
    x = np.arange(1, 14)
    cursor.execute("SELECT offset_bits, COUNT(*), SUM(num) FROM taken_percent WHERE offset_bits != 0 GROUP BY offset_bits ORDER BY offset_bits")
    offset_bits = cursor.fetchall()
    df = pd.DataFrame(offset_bits, columns=['offset_bits', 'static', 'dynamic'])
    df['static_percent'] = ((df['static'] / df['static'].sum()) * 100).cumsum()
    df['dynamic_percent'] = ((df['dynamic'] / df['dynamic'].sum()) * 100).cumsum()
    
    plt.cla()
    fig, ((ax1, ax2)) = plt.subplots(1, 2, figsize=(12, 6))
    ax1.plot(df['offset_bits'], df['static_percent'], label='cond_static', marker='o', color='r')
    ax1.set_title('Static Branches by offset bits')
    ax1.set_xlabel('offset bits')
    ax1.set_ylabel('percentage')
    # ax1.set_xticks(x)
    ax1.legend()
    
    ax2.plot(df['offset_bits'], df['dynamic_percent'], label='cond_dynamic', marker='o', color='r')
    ax2.set_title('Dynamic Branches by offset bits')
    ax2.set_xlabel('offset bits')
    ax2.set_ylabel('percentage')
    # ax2.set_xticks(x)
    ax2.legend()
    
    # get offset bits of jal from BPTRACE(controlType == 1 or 2)
    if not check_table_existence(cursor, 'jal_offset_bits'):
        cursor.execute("""
        CREATE TABLE jal_offset_bits AS
        WITH CTE AS (
            SELECT
                controlPC,
                controlType,
                COUNT(*) AS num,
                MAX(target) AS jump_target
            FROM
                BPTRACE
            WHERE
                controlType == 1 OR controlType == 2
            GROUP BY
                controlPC
        )
        SELECT
            *
        FROM
            CTE
        """)
        cursor.execute("ALTER TABLE jal_offset_bits ADD COLUMN offset_bits INTEGER")
        cursor.execute("""
            UPDATE jal_offset_bits
            SET offset_bits = CAST(CEIL(LOG2(ABS(jump_target - controlPC)+1)) AS INTEGER)
        """)
    
    cursor.execute("SELECT offset_bits, COUNT(*), SUM(num) FROM jal_offset_bits GROUP BY offset_bits ORDER BY offset_bits")
    jal_offset_bits = cursor.fetchall()
    df = pd.DataFrame(jal_offset_bits, columns=['offset_bits', 'static_num', 'dynamic_num'])
    df['static_percent'] = ((df['static_num'] / df['static_num'].sum()) * 100).cumsum()
    df['dynamic_percent'] = ((df['dynamic_num'] / df['dynamic_num'].sum()) * 100).cumsum()
    
    ax1.plot(df['offset_bits'], df['static_percent'], label='jal_static', marker='o', color='g')
    # ax1.set_title('Static JAL by offset bits')
    # ax1.set_xlabel('offset bits')
    # ax1.set_ylabel('percentage')
    # ax1.set_xticks(x)
    # ax1.legend()
    
    ax2.plot(df['offset_bits'], df['dynamic_percent'], label='jal_dynamic', marker='o', color='g')
    # ax2.set_title('Dynamic JAL by offset bits')
    # ax2.set_xlabel('offset bits')
    # ax2.set_ylabel('percentage')
    # ax2.set_xticks(x)
    # ax2.legend()


    
    ############ jalr ##############
    # jalr may have more than one target
    if not check_table_existence(cursor, 'jalr_offset_bits'):
        # cursor.execute("SELECT controlPC, COUNT(*) AS num FROM BPTRACE WHERE controlType == 3 OR controlType == 5 GROUP BY controlPC ORDER BY num")
        # jalrs = cursor.fetchall()
        # print("jalr branch num:", len(jalrs))
        # for jalr in jalrs:
        #     print(jalr['controlPC'], jalr['num'])
        cursor.execute("""
        CREATE TABLE jalr_offset_bits AS
        WITH CTE AS (
            SELECT
                controlPC,
                controlType,
                COUNT(*) AS num,
                target as jump_target
            FROM
                BPTRACE
            WHERE
                controlType == 3 OR controlType == 5
            GROUP BY
                controlPC, target
        )
        SELECT
            *
        FROM
            CTE
        """)
        cursor.execute("ALTER TABLE jalr_offset_bits ADD COLUMN offset_bits INTEGER")
        cursor.execute("""
            UPDATE jalr_offset_bits
            SET offset_bits = CAST(CEIL(LOG2(ABS(jump_target - controlPC)+1)) AS INTEGER)
        """)
        
    # number of different targets of each jalr
    cursor.execute("""
        SELECT controlPC, COUNT(*) AS target_num
        FROM jalr_offset_bits
        GROUP BY controlPC
        HAVING target_num > 1
        ORDER BY num DESC
    """)
    
    # draw a bar chart of jalr with different targets
    jalr_targets = cursor.fetchall()


    # dynamic jalr offset bits
    cursor.execute("SELECT offset_bits, COUNT(*), SUM(num) FROM jalr_offset_bits GROUP BY offset_bits ORDER BY offset_bits")
    jalr_offset_bits = cursor.fetchall()
    df = pd.DataFrame(jalr_offset_bits, columns=['offset_bits', 'static_num', 'dynamic_num'])
    df['static_percent'] = ((df['static_num'] / df['static_num'].sum()) * 100).cumsum()
    df['dynamic_percent'] = ((df['dynamic_num'] / df['dynamic_num'].sum()) * 100).cumsum()
    # plt.savefig(os.path.join(get_dir(db_path), res_dir_name, 'jalr_offset_bits.png'))
    
    x = np.arange(1, 40)
    # plt.cla()
    # fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    ax1.plot(df['offset_bits'], df['static_percent'], label='jalr_static_target', marker='o', color='b')
    # ax1.set_title('Static JALR by offset bits(each target count for a static jalr)')
    # ax1.set_xlabel('offset bits')
    # ax1.set_ylabel('percentage')
    ax1.set_xticks(x)
    ax1.set_xticklabels(x, rotation=45, ha='right')
    ax1.legend()
    
    ax2.plot(df['offset_bits'], df['dynamic_percent'], label='jalr_dynamic', marker='o', color='b')
    # ax2.set_title('Dynamic JALR by offset bits')
    # ax2.set_xlabel('offset bits')
    # ax2.set_ylabel('percentage')
    ax2.set_xticks(x)
    ax2.set_xticklabels(x, rotation=45, ha='right')
    ax2.legend()
    plt.savefig(os.path.join(get_dir(db_path), res_dir_name, 'branch_offset_bits.png'))
    
    # draw a bar chart of jalr with different targets
    df = pd.DataFrame(jalr_targets, columns=['controlPC', 'num'])
    df['controlPC'] = df['controlPC'].apply(lambda x: format(x, 'x'))
    df.to_csv(os.path.join(get_dir(db_path), res_dir_name, 'jalr_multiple_targets.csv'), index=False)

    plt.cla()
    fig, ax = plt.subplots(figsize=(6, 6))
    
    df['controlPC'] = df['controlPC'].astype(str)
    ax.plot(df['controlPC'], df['num'], marker='o')
    ax.set_xticks(range(len(df['controlPC'])))
    ax.set_xticklabels(df['controlPC'], rotation=45, ha='right')
    # plt.tight_layout()
    fig.savefig(os.path.join(get_dir(db_path), res_dir_name, 'jalr_targets.png'))
    

    
    


    
    
    

def add_options():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="database file")
    parser.add_argument("--dump-table", help="dump specific table of given database file")
    parser.add_argument("--db-type", action="store", help="database type")
    parser.add_argument("--debug", action="store_true", help="debug mode")
    parser.add_argument("--ftb", action="store_true", help="do ftb analysis")
    parser.add_argument("--branch", action="store_true", help="do branch analysis")
    return parser

def main():
    parser = add_options()
    args = parser.parse_args()
    if args.debug:
        global debug
        debug = True
    
    db_path = args.db
    # make res dir if not exist
    res_dir = os.path.join(get_dir(db_path), res_dir_name)
    if not os.path.exists(res_dir):
        os.mkdir(res_dir)
    
    if args.db_type:
        db_type = args.db_type
    else:
        if "fetch.db" in db_path:
            db_type = "fetch"
        elif "bp.db" in db_path:
            db_type = "bp"
            
    if db_type == "fetch":
        if "xs" in db_path:
            workload = "xs"
        elif "rocket" in db_path:
            workload = "rocket"
            

    # print db path
    print("db path:", db_path)
    db_connect = sqlite3.connect(db_path)
    db_connect.row_factory = sqlite3.Row

    if args.dump_table:
        table = args.dump_table
        cursor = db_connect.cursor()
        # get all column names
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        print("columns:")
        for column in columns:
            print(column['name'], end=', ')

        cursor.execute(f"SELECT * FROM {table}")

        rows = cursor.fetchall()

        if db_type == 'bp':
            for row in rows:
                print("enter %#lx, jump_in %d, out %#lx, jump_out %d" %
                (row['enter_pc'], row['jump_in'], row['out_pc'], row['jump_out']))

            if table == 'FETCHTRACE':
                # count total cache lines, unique cache lines
                # align enter_pc to 64Bytes boundary, and count unique aligned enter_pc
                # check existence of virtual column aligned_enter_pc
                if not check_column_existence(cursor, 'FETCHTRACE', 'aligned_enter_pc'):
                    cursor.execute(f"ALTER TABLE FETCHTRACE ADD COLUMN aligned_enter_pc INTEGER AS (enter_pc & ~{cache_block_size-1}) VIRTUAL")
                cursor.execute(f"SELECT COUNT(DISTINCT enter_pc) FROM FETCHTRACE")
                print("total cache lines:", cursor.fetchone()[0])
                # count each cache line's frequency in descending order
                cursor.execute(f"SELECT aligned_enter_pc, COUNT(*) FROM FETCHTRACE GROUP BY aligned_enter_pc ORDER BY COUNT(*) DESC")
                all_cache_lines = cursor.fetchall()
                print("unique cache lines:", len(all_cache_lines))
                for row in all_cache_lines:
                    print(f"cache line pc {row[0]:#x}, frequency {row[1]}")
        elif db_type == "fetch":
            pass
            
            

        cursor.close()
        db_connect.close()
        exit()
    
    if db_type == 'bp':
        # construct_fetch_trace_from_branch_trace(db_connect, cache_block_size)
        if args.ftb:
            ftb_analysis(db_connect, db_path)
        if args.branch:
            branch_analysis(db_connect, db_path)
            

    if db_type == 'fetch':
        extract_fetch_trace_basic_info(db_connect, workload, db_path)

    db_connect.commit()
    # db.rollback()
    # c_spec.close()
    db_connect.close()

if __name__ == '__main__':
    main()
