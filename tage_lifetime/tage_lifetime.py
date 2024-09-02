import sqlite3
import argparse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

res_dir_name = 'tage_entry_analysis'

num_tables = 4

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
    print("id %10d, lifetime %10d, startPC %#10lx, brPC %#10lx, oldBrPC %#10lx, tableIdx %d, phyBrIdx %d "\
          "correct %d wrong %d start %10d end %10d" %
          (id, lifetime, startPC, brPC, oldPC, tableIdx, phyBrIdx, correct, wrong, start, end))

def print_entries(tage_entries):
    for entry in tage_entries:
        # print(entry)
        print_tage_entry(entry)

# (id, tick, controlPC, controlType, fallThruPC, mispred, source, startPC, taken, target)
def print_bp_trace(row):
    (id, tick, controlPC, controlType, fallThruPC, mispred, source, startPC, taken, target) = row
    print("id %10d, cycle %10d, startPC %#10lx, controlPC %#10lx, fallThruPC %#10lx, "\
          "target %#10lx, type %d, taken %d, source %d, mispred %d, rasOp %s" %
          (id, tick, startPC, controlPC, fallThruPC, target, controlType, taken,
           source, mispred, controlType))
    return (controlType, fallThruPC, target)

def print_normal_branch(row):
    print(row)

def check_column_existence(cursor, table_name, column_name):
    cursor.execute("PRAGMA table_xinfo(%s)" % table_name)
    rows = cursor.fetchall()
    # print(rows)
    for row in rows:
        if row[1] == column_name:
            return True
    return False

def get_tage_entry_count_from_branch_pc(cursor, pc, break_down=False):
    if not break_down:
        total_count = cursor.execute("SELECT COUNT(*) FROM TAGEENTRYLIFETIMETRACE WHERE start != 0 AND brPC = %s" % pc).fetchone()[0]
        return total_count
    else:
        # use auxiliary columns to break down entries used by correct/wrong predictions
        # description of all categories:
        # 1. never used (correct = wrong = 0)
        # 2. rarely used (correct < threshold && wrong < threshold, where threshold is a small number, say 10)
        # below are categories that made some correct/wrong predictions
        # 3. negative effect (correct rate < 50%)
        # 4. correct rate >= 50% && < 70%
        # 5. correct rate >= 70% && < 90%
        # 6. correct rate >= 90%
        # each category are represented by a tuple (category name, count)
        category_names = ["never used", "rarely used", "negative effect", "correct rate >= 50% && < 70%", "correct rate >= 70% && < 90%", "correct rate >= 90%"]
        category_counts = [0] * len(category_names)
        threshold = 10
        # first make auxiliary columns
        if not check_column_existence(cursor, "TAGEENTRYLIFETIMETRACE", "correct_rate"):
            cursor.execute("ALTER TABLE TAGEENTRYLIFETIMETRACE ADD COLUMN correct_rate REAL AS (usedCorrect * 1.0 / (usedCorrect + usedWrong)) VIRTUAL")
        if not check_column_existence(cursor, "TAGEENTRYLIFETIMETRACE", "correct_rate_category"):
            cursor.execute("ALTER TABLE TAGEENTRYLIFETIMETRACE ADD COLUMN correct_rate_category INTEGER AS (CASE WHEN correct_rate < 0.5 THEN 0 WHEN correct_rate < 0.7 THEN 1 WHEN correct_rate < 0.9 THEN 2 ELSE 3 END) VIRTUAL")
        if not check_column_existence(cursor, "TAGEENTRYLIFETIMETRACE", "used_category"):
            cursor.execute("ALTER TABLE TAGEENTRYLIFETIMETRACE ADD COLUMN used_category INTEGER AS (CASE WHEN usedCorrect = 0 AND usedWrong = 0 THEN 0 WHEN usedCorrect < %d AND usedWrong < %d THEN 1 ELSE correct_rate_category + 2 END) VIRTUAL" % (threshold, threshold))
        # then count
        for i, category_name in enumerate(category_names):
            category_counts[i] = cursor.execute("SELECT COUNT(*) FROM TAGEENTRYLIFETIMETRACE WHERE start != 0 AND brPC = %s AND used_category = %d" % (pc, i)).fetchone()[0]
        # finally wrap into a list of tuples
        res = list(zip(category_names, category_counts))
        print(res)
        return res

# distinct entries of tuple(idx, tableIndex, phyBrIdx)
def get_unique_tage_entry_count_from_branch_pc(cursor, pc=None):
    query = f'''SELECT COUNT(*)
    FROM (
        SELECT DISTINCT idx, tableIndex, phyBrIdx
        FROM TAGEENTRYLIFETIMETRACE
        WHERE start != 0 {f'AND brPC = {pc:d}' if pc else ''}
        )
    '''
    return cursor.execute(query).fetchone()[0]

def get_mispredict_count_from_branch_pc(cursor, pc):
    return cursor.execute("SELECT COUNT(*) FROM BPTRACE WHERE controlPC = %s AND mispred = 1" % pc).fetchone()[0]

def get_all_branches_and_misps(cursor):
    unique_branches = cursor.execute("SELECT DISTINCT controlPC FROM BPTRACE WHERE controlType = 0").fetchall()
    dict_branch_misp = {}
    print("total %d branches" % len(unique_branches))
    # get their mispredict count
    for branch in unique_branches:
        misp_count = get_mispredict_count_from_branch_pc(cursor, branch[0])
        dict_branch_misp[branch[0]] = misp_count
        print("branch %x, misp %d" % (branch[0], misp_count))
    # print top 5 branches and their mispredict count
    
    return dict_branch_misp

# x for branch_pc, y for entry_num, z for misp_num, w for unique_entry_num
# total_unique_entry represents total physical entries that all branches used all together
# y_threshold set a threshold to only show branches who used more entries than the threshold
# y_break_down categorize entries used by the correct/wrong predictions they made
#     format: [
#               [(category name 1: n_entries_1),
#                (category name 2: n_entries_2),
#                ...
#                (category name n: n_entries_n)
#               ],
#               ...
#               [                    
#               ]
#             ], category order is fixed
#             |
def draw_three_bar_graph(target_dir, name, x, y, z, w, total_unique_entry, y_threshold=100, y_break_down=None):
    # draw a three-bar graph of num entries and misps for each branch with matplotlib
    # 根据y的值进行排序，同时保持x, y, z之间的对应关系，并过滤掉y值小于y_threshold的数据
    print(y_break_down)
    no_breakdown = y_break_down is None or len(y_break_down) == 0
    
    if no_breakdown:
        sorted_lists = sorted(zip(z, x, y, w), reverse=True)
        limited_lists = [item for item in sorted_lists if item[2] > y_threshold]
        z, x, y, w = [[elem[i] for elem in limited_lists] for i in range(4)]
    else:
        sorted_lists = sorted(zip(z, x, y, w, y_break_down), reverse=True)
        limited_lists = [item for item in sorted_lists if item[2] > y_threshold]
        if len(limited_lists) == 0:
            limited_lists = sorted_lists[:10]
        z, x, y, w, y_break_down = [[elem[i] for elem in limited_lists] for i in range(5)]    
    
    
    # 设置条形的位置
    x_positions = range(len(x))

    # 设置图表的大小
    plt.figure(figsize=(12, 8))

    # 定义每个条形的宽度
    bar_width = 0.25

    # 画出y值的柱形图
    y_positions = [pos - bar_width for pos in x_positions]
    plt.bar(y_positions, z, width=bar_width, label='misp_num', align='center')


    # 画出z值的柱形图
    z_positions = x_positions
    w_positions = [pos + bar_width for pos in x_positions]
    plt.bar(w_positions, w, width=bar_width, label='unique_entry_num', align='center')

    # 画出w值的柱形图
    if no_breakdown:
        plt.bar(z_positions, y, width=bar_width, label='entry_num', align='center')
    else:
        print(y_break_down)
        num_data_points = len(y_break_down)
        num_categories = len(y_break_down[0])
        category_names = [data[0] for data in y_break_down[0]]
        print(category_names)
        # data_in_categories = [[data[1] for data in y_break_down[i]] for i in range(num_categories)]
        data_in_categories = [[data[i][1] for data in y_break_down] for i in range(num_categories)]
        print(data_in_categories)
        cumulative_values = np.zeros(num_data_points)
        for i in range(num_categories):
            plt.bar(z_positions, data_in_categories[i], width=bar_width, label='entry_num_'+category_names[i], bottom=cumulative_values, align='center')
            cumulative_values += np.array(data_in_categories[i])
            
            

    # 设置横坐标的标签
    plt.xticks([pos + 0.2 for pos in x_positions], [f'{pc:x}' for pc in x], rotation=45, ha='right') # ha='right' 使得标签右对齐
    
    # 添加图例
    plt.legend()

    # 添加标题和坐标轴标签
    plt.title(f'''
              {name}
              TAGE entry num and misp num for each branch
              total misps {sum(z)}, total unique entry {total_unique_entry}
              ''')
    plt.xlabel('branches')
    plt.ylabel('nums')

    # 显示图表
    plt.show()
    plt.savefig(os.path.join(target_dir, "tage_entry_misp.png"))

def categorize_entries(c, res_dir, db_path):
    # tage_entries = c.execute("SELECT * FROM TAGEENTRYLIFETIMETRACE WHERE start != 0")

    # print_entries(tage_entries)
    
    branches_and_misps = get_all_branches_and_misps(c)
    
    target_branch_pcs = branches_and_misps.keys()
    misp_per_branch = [branches_and_misps[pc] for pc in target_branch_pcs]
    
    break_down = True
    num_entry_per_branch = [get_tage_entry_count_from_branch_pc(c, pc, break_down) for pc in target_branch_pcs]
    if break_down:
        num_entry_per_branch_break_down = num_entry_per_branch
        num_entry_per_branch = [sum([category[1] for category in branch]) for branch in num_entry_per_branch_break_down]
    else:
        num_entry_per_branch_break_down = None
    
    unique_entry_per_branch = [get_unique_tage_entry_count_from_branch_pc(c, pc) for pc in target_branch_pcs]
    total_misps = sum(branches_and_misps.values())
    # do not pass pc, calculate all branches
    total_unique_entry = get_unique_tage_entry_count_from_branch_pc(c)
    
    draw_three_bar_graph(res_dir, get_checkpoint_name(db_path), target_branch_pcs, num_entry_per_branch, misp_per_branch, unique_entry_per_branch, total_unique_entry, y_threshold=100, y_break_down=num_entry_per_branch_break_down)
    for i, pc in enumerate(target_branch_pcs):
        print("branch %x, %d entries(%d unique) for %d misps" % (pc, num_entry_per_branch[i], unique_entry_per_branch[i], misp_per_branch[i]))
    print("total misps %d" % total_misps)
    print("total unique entries %d" % total_unique_entry)

def analyze_tage_entry_occupancy_sample(cursor):
    # with existing table "TAGEENTRYALIVE"
    # generate for each sample a table containing data as follows:
    # for each branchPC, the number of entries existing in each TAGE history table
    cursor.execute("DROP TABLE IF EXISTS SAMPLETABLE")
    cursor.execute("CREATE TABLE SAMPLETABLE AS SELECT branchPC, COUNT(*) FROM TAGEENTRYALIVE GROUP BY branchPC")

def tage_entry_occupancy_sampling(cursor, res_dir, db_path, interval=1000):
    def check_occupancy_table_existence():
        table_name = "OccupancyAnalysis"
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        result = cursor.fetchone()
        if result:
            print(f"Table {table_name} exists in the database.")
        else:
            print(f"Table {table_name} does not exist in the database.")
        return bool(result)

    def count_occupancy_entry():    
        cursor.execute("SELECT COUNT(*) FROM OccupancyAnalysis")
        count = cursor.fetchone()[0]
        print(f"table entry count is {count}")

    # Get maximum end cycle to determine when to end the following loop
    cursor.execute("SELECT MAX(end) FROM TAGEENTRYLIFETIMETRACE")
    max_end_cycle = cursor.fetchone()[0]
    print(f"max cycle is {max_end_cycle}")

    # if check_occupancy_table_existence():
    if False:
        count_occupancy_entry()
    else:
        # db records each entry's start and end cycle
        # create another table to record the number of entries alive at each sampling point
        cursor.execute("DROP TABLE IF EXISTS TAGEENTRYALIVE")
        cursor.execute("DROP TABLE IF EXISTS OccupancyAnalysis")
        cursor.execute('CREATE TABLE TAGEENTRYALIVE AS SELECT * FROM TAGEENTRYLIFETIMETRACE WHERE 0;')
        cursor.execute('''CREATE TABLE OccupancyAnalysis (
                            ID INTEGER PRIMARY KEY,
                            branchPC INTEGER NOT NULL,
                            intervalID INTEGER NOT NULL,
                            tableIdx INTEGER NOT NULL,
                            tageEntryAlive INTEGER NOT NULL
                        )''')


        current_position = 0
        while True:
            print(f"sampling for position {current_position}...")
            # get all entries alive at current position
            cursor.execute("INSERT INTO TAGEENTRYALIVE SELECT * FROM TAGEENTRYLIFETIMETRACE WHERE start <= %d AND start > %d AND end >= %d AND oldPC != 0" %
                           (current_position, current_position-interval, current_position))
            cursor.execute("DELETE FROM TAGEENTRYALIVE WHERE end < %d" % current_position)
            # tage_entries = cursor.execute("SELECT * FROM TAGEENTRYALIVE")

            # print_entries(tage_entries)
            
            # Deal with table OccupancyAnalysis
            interval_id = current_position // interval
            cursor.execute('''INSERT INTO OccupancyAnalysis (branchPC, intervalID, tableIdx, tageEntryAlive)
                            SELECT oldPC, ?, tableIndex, COUNT(*) FROM TAGEENTRYALIVE GROUP BY oldPC, tableIndex''', (interval_id,))
            
            
            current_position += interval
            print(f"end sampling for position {current_position}...")
            if current_position > max_end_cycle:
                break
            # 检查同一位置下是否存在多条记录的 SQL 查询
            def check_duplicate(cursor, intervalID):
                print(f"interval {intervalID}")
                # 检测重复记录的 SQL 查询
                find_duplicates_query = """
                SELECT *
                FROM TAGEENTRYALIVE
                WHERE (tableIndex, idx, phyBrIdx) IN (
                    SELECT tableIndex, idx, phyBrIdx
                    FROM TAGEENTRYALIVE
                    GROUP BY tableIndex, idx, phyBrIdx
                    HAVING COUNT(*) > 1
                )
                ORDER BY tableIndex, idx, phyBrIdx
                """

                # 执行查询
                cursor.execute(find_duplicates_query)

                # 获取查询结果
                duplicate_records = cursor.fetchall()

                # 打印重复记录
                if duplicate_records:
                    print("以下是重复的记录：")
                    for record in duplicate_records:
                        print(record)
                else:
                    print("没有发现重复的记录。")

            check_duplicate(cursor, interval_id)
            count_occupancy_entry()

        count_occupancy_entry()
    
    def count_entry_ever_used():
        cursor.execute('SELECT COUNT(*) FROM TAGEENTRYLIFETIMETRACE WHERE start == 0 AND oldPC == 0')
        cnt = cursor.fetchone()[0]
        print(f'totally {cnt} entries ever been used, among them')
        for tableIdx in range(4):
            cursor.execute('SELECT COUNT(*) FROM TAGEENTRYLIFETIMETRACE WHERE start == 0 AND oldPC == 0 AND tableIndex == %d' % tableIdx)
            cnt = cursor.fetchone()[0]
            print(f'{cnt} in table {tableIdx}')
    
    count_entry_ever_used()
    
    # TODO: draw stacked area chart of number of entries of each branch PC changing by interval
    # data source is table "OccupancyAnalysis", show the ten branches with the largest average entry num as they are,
    # and sum up all other branches to "otherBranches"
    # below are the codes:

    def draw_stacked_area_chart(cursor):
        # Retrieve data from OccupancyAnalysis table
        cursor.execute("SELECT branchPC, intervalID, SUM(tageEntryAlive) as entryCount FROM OccupancyAnalysis GROUP BY branchPC, intervalID")
        rows = cursor.fetchall()
        print(rows)
    
        # Set the options to display all rows and columns
        pd.set_option('display.max_rows', None)  # None means show all rows
        pd.set_option('display.max_columns', None)  # None means show all columns

        # Increase the width of each column to avoid breaking down lines
        pd.set_option('display.width', None)  # None means use the maximum available width

        # Optionally, set the option to display the full content of the cells
        pd.set_option('display.max_colwidth', None)  # None means show full width of columns
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(rows, columns=['branchPC', 'intervalID', 'entryCount'])
        
        # Convert branchPC to hexadecimal
        df['branchPC'] = df['branchPC'].apply(lambda x: format(x, 'x').upper())

        # Calculate the average entry count for each branchPC
        average_counts = df.groupby('branchPC')['entryCount'].mean().sort_values()

        # Get the top five branchPCs by average entry count
        top_branches = average_counts.tail(10).index.tolist()
        
        # Filter out the top branches and sum the rest as 'otherBranches'
        df['branchGroup'] = df['branchPC'].apply(lambda x: x if x in top_branches else 'otherBranches')
        
        # Sum all non-top branches under 'otherBranches'
        df_grouped = df.groupby(['intervalID', 'branchGroup'])['entryCount'].sum().unstack('branchGroup').fillna(0)
        print(df_grouped)
        # Ensure 'OtherBranches' is at the end if it exists
        cols_ordered = average_counts.index.tolist()
        cols_ordered = [col for col in cols_ordered if col not in top_branches]
        cols_ordered += ['OtherBranches'] if 'OtherBranches' in df_grouped.columns else []
        cols_ordered += top_branches
        
        # 获取当前轴上的图例句柄和标签

        # Draw the stacked area chart
        ax = df_grouped.plot(kind='area', stacked=True)
        # Setting the titles and labels
        plt.title('Stacked Area Chart of TAGE Entry Occupancy')
        plt.xlabel('Interval ID')
        plt.ylabel('Number of TAGE Entries')

        # Get handles and labels
        handles, labels = ax.get_legend_handles_labels()
        
        # Reverse the order for the legend
        ax.legend(handles[::-1], labels[::-1], title='branchPC')

        # Show the plot
        plt.savefig(os.path.join(res_dir, "tage_entry_occupancy.png"))

    def draw_stacked_area_chart_by_tableIdx(cursor):
        # Retrieve data from OccupancyAnalysis table
        cursor.execute("SELECT tableIdx, intervalID, SUM(tageEntryAlive) as entryCount FROM OccupancyAnalysis GROUP BY tableIdx, intervalID")
        rows = cursor.fetchall()

        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(rows, columns=['tableIdx', 'intervalID', 'entryCount'])

        # Sum all entries under each tableIdx
        df_grouped = df.groupby(['intervalID', 'tableIdx'])['entryCount'].sum().unstack('tableIdx').fillna(0)

        # Draw the stacked area chart
        ax = df_grouped.plot(kind='area', stacked=True)
        # Setting the titles and labels
        plt.title('Stacked Area Chart of TAGE Entry Occupancy by tableIdx')
        plt.xlabel('Interval ID')
        plt.ylabel('Number of TAGE Entries')

        # Get handles and labels
        handles, labels = ax.get_legend_handles_labels()

        # Reverse the order for the legend
        ax.legend(handles[::-1], labels[::-1], title='tableIdx')

        # Show the plot
        plt.savefig(os.path.join(res_dir, "tage_entry_occupancy_by_tableIdx.png"))
        
    def draw_stacked_area_chart_by_lgcTableIdx(cursor):
        # Retrieve data from OccupancyAnalysis table
        cursor.execute("SELECT oldLgcTableIdx, intervalID, SUM(tageEntryAlive) as entryCount FROM OccupancyAnalysis GROUP BY oldLgcTableIdx, intervalID")
        rows = cursor.fetchall()

        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(rows, columns=['oldLgcTableIdx', 'intervalID', 'entryCount'])

        # Sum all entries under each tableIdx
        df_grouped = df.groupby(['intervalID', 'oldLgcTableIdx'])['entryCount'].sum().unstack('oldLgcTableIdx').fillna(0)

        # Draw the stacked area chart
        ax = df_grouped.plot(kind='area', stacked=True)
        # Setting the titles and labels
        plt.title('Stacked Area Chart of TAGE Entry Occupancy by lgcTableIdx')
        plt.xlabel('Interval ID')
        plt.ylabel('Number of TAGE Entries')

        # Get handles and labels
        handles, labels = ax.get_legend_handles_labels()

        # Reverse the order for the legend
        ax.legend(handles[::-1], labels[::-1], title='lgcTableIdx')

        # Show the plot
        plt.savefig(os.path.join(res_dir, "tage_entry_occupancy_by_lgcTableIdx.png"))

    # Call the function with the cursor
    draw_stacked_area_chart(cursor)
    draw_stacked_area_chart_by_tableIdx(cursor)
    # draw_stacked_area_chart_by_lgcTableIdx(cursor)
    # draw_area_chart(cursor)
    

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="database file")
    args = parser.parse_args()
    
    db_path = args.db
    # make res dir if not exist
    res_dir = os.path.join(get_dir(db_path), res_dir_name)
    if not os.path.exists(res_dir):
        os.mkdir(res_dir)
        

    db = sqlite3.connect(db_path)
    c = db.cursor()

    # categorize_entries(c, res_dir, db_path)
    tage_entry_occupancy_sampling(c, res_dir, db_path)
    db.commit()
    # db.rollback()
    c.close()
    # c_spec.close()
    db.close()

if __name__ == '__main__':
    main()
