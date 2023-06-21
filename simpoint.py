import gzip
import numpy as np
import matplotlib.pyplot as plt
from scipy.sparse import dok_matrix
import scipy.sparse as sp
from scipy.cluster.vq import kmeans, vq
import multiprocessing

num_threads = 100
lines_per_part = 10

# get coo matrix for a set of lines
def process_lines(input):
    (lines, start_line_idx) = input
    data = []
    row = []
    col = []
    max_block_id = 0
    cur_line_idx = start_line_idx
    total_data_num = 0
    for line in lines:
        line = line.strip()
        if line:
            blocks = line.split()
            blocks[0] = blocks[0][1:]
            data_point = {}
            for block in blocks:
                # print(block)
                parts = block.decode().split(':')
                block_id = int(parts[1])
                block_count = int(parts[2])
                data_point[block_id] = block_count
                row.append(cur_line_idx)
                col.append(block_id)
                data.append(block_count)
                total_data_num += 1
                if block_id > max_block_id:
                    max_block_id = block_id
            cur_line_idx += 1
    print(f'max_block_id of line {start_line_idx}~{start_line_idx+lines_per_part-1}: {max_block_id}')
    print(f'total data num of line {start_line_idx}~{start_line_idx+lines_per_part-1}: {total_data_num}')
    return [data, row, col, max_block_id]

def read_file_in_batches(filename, batch_size=100):
    with open(filename, 'rb') as file:
        batch_start_line_idx = 0
        while True:
            batch = []
            for _ in range(batch_size):
                line = file.readline()
                if not line:
                    break  # 文件已读完
                batch.append(line.strip())
            if not batch:
                break  # 文件已读完
            
            yield (batch, batch_start_line_idx)
            batch_start_line_idx += batch_size


# 解压缩.gz文件并逐行读取文本数据
def read_data(filename):
    total_data = []
    total_row = []
    total_col = []
    total_max_block_id = []
    with gzip.open(filename, 'rb') as file:
        line_idx = 0
        max_block_id = 0
        pool = multiprocessing.Pool(num_threads)
        results = []
        batch_readline_iterator = read_file_in_batches(filename, lines_per_part)
        results = pool.imap(process_lines, batch_readline_iterator)
            
        pool.close()
        pool.join()
    
    for result in results:
        [data, row, col, max_block_id] = result
        total_data += data
        total_row += row
        total_col += col
        total_max_block_id.append(max_block_id)
    print(f'total max block id is {max(total_max_block_id)}')
    return (total_data, total_row, total_col)

# 将稀疏数据转换为稀疏矩阵表示
def convert_to_sparse_matrix(data):
    (data, row, col) = data
    rows = np.array(row)
    cols = np.array(col)
    vals = np.array(data)
    sparseM = sp.coo_matrix((vals, (rows, cols)), dtype=np.int32)
    return sparseM

def k_means(data, k, max_iterations=100):
    # 随机选择k个中心点
    centers = data[np.random.choice(len(data), k, replace=False)]
    
    for _ in range(max_iterations):
        # 计算每个样本与中心点的距离
        distances = np.linalg.norm(data[:, np.newaxis] - centers, axis=2)
        
        # 分配每个样本到最近的中心点
        labels = np.argmin(distances, axis=1)
        
        # 更新中心点为每个簇的均值
        new_centers = np.array([data[labels == i].mean(axis=0) for i in range(k)])
        
        # 如果中心点不再发生变化，则停止迭代
        if np.all(centers == new_centers):
            break
        
        centers = new_centers
    
    return labels, centers

# # 示例用法
# data = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
# k = 2

# labels, centers = k_means(data, k)

# # 绘制聚类结果
# colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
# for i in range(k):
#     cluster_points = data[labels == i]
#     plt.scatter(cluster_points[:, 0], cluster_points[:, 1], color=colors[i], label=f'Cluster {i+1}')

# plt.scatter(centers[:, 0], centers[:, 1], color='black', marker='x', s=100, label='Centroids')
# plt.xlabel('X')
# plt.ylabel('Y')
# plt.title('K-means Clustering')
# plt.legend()
# plt.show()

data = read_data('/nfs/home/goulingrui/expri_result/emu_microbench_cpt/profiling/emu_microbench/simpoint_bbv')
print('finish read data')
sparseM = convert_to_sparse_matrix(data)
print('finish convert to sparse matrix')
csrM = sparseM.tocsr()
print('finish convert to csr matrix')
sp.save_npz('/nfs/home/goulingrui/expri_result/emu_microbench_cpt/profiling/emu_microbench/simpoint_bbv.npz', csrM)