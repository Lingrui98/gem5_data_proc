# Makefile

# 定义变量
BASE_DIR := /nfs/home/goulingrui/expri_results/gem5/frontend_06/verilator-simpoint-fetch-db-fix-tlb
PYTHON_SCRIPT := /nfs/home/goulingrui/project/gem5_data_proc/fetch_analysis/fetch_analysis.py
TMPFS_DIR := /dev/shm
PYTHON_PATH := /nfs/home/goulingrui/project/gem5_data_proc

# 找到所有的fetch.db文件
FETCH_DB_FILES := $(shell find $(BASE_DIR) -type f -name 'fetch.db')
# fetch.db -> fetch_analysis.log
ANALAYSIS_FILES := $(FETCH_DB_FILES:%/fetch.db=%/fetch_analysis.log)

# 找到所有的bp.db文件
BP_DB_FILES := $(shell find $(BASE_DIR) -type f -name 'bp.db')
# bp.db -> bb.log
BB_FILES := $(BP_DB_FILES:%/bp.db=%/bb.log)
# bp.db -> ftb.log
FTB_FILES := $(BP_DB_FILES:%/bp.db=%/ftb.log)
# bp.db -> branch.log
BRANCH_FILES := $(BP_DB_FILES:%/bp.db=%/branch.log)

# 定义伪目标，以防止与同名文件冲突
.PHONY: all, clean

fetch_analysis: $(ANALAYSIS_FILES)
bb: $(BB_FILES)
ftb: $(FTB_FILES)
branch: $(BRANCH_FILES)

# 默认目标
all: fetch_analysis, bb, ftb, branch

# 模式规则：对每个bp.db文件执行Python脚本，并重定向输出到fetch_analysis.log
$(ANALAYSIS_FILES):  %/fetch_analysis.log : %/fetch.db

	@echo "Processing $< to $@"
# 创建临时目录
	@mkdir -p $(TMPFS_DIR)/$(dir $<)
# 拷贝数据库到tmpfs
	@cp $< $(TMPFS_DIR)/$<
# 执行Python脚本，输入输出都在tmpfs
	@python3 $(PYTHON_SCRIPT) --db $(TMPFS_DIR)/$< > $(TMPFS_DIR)/$@
# 将生成的日志文件从tmpfs拷贝回原目录
	@cp $(TMPFS_DIR)/$@ $@
# 将python脚本生成的图片从tmpfs拷贝回原目录
	@cp -r $(TMPFS_DIR)/$(dir $<)/fetch_result $(dir $@)
# 清理tmpfs中的文件
	@rm -rf $(TMPFS_DIR)/$(dir $<)

$(BB_FILES): %/bb.log : %/bp.db

	@echo "Processing $< to $@"
# 创建临时目录
	@mkdir -p $(TMPFS_DIR)/$(dir $<)
# 拷贝数据库到tmpfs
	@cp $< $(TMPFS_DIR)/$<
# 执行Python脚本，输入输出都在tmpfs
	@python3 $(PYTHON_SCRIPT) --db $(TMPFS_DIR)/$< > $(TMPFS_DIR)/$@
# 将生成的日志文件从tmpfs拷贝回原目录
	@cp $(TMPFS_DIR)/$@ $@
# 将python脚本生成的图片从tmpfs拷贝回原目录
	@cp -r $(TMPFS_DIR)/$(dir $<)/fetch_result $(dir $@)
# 清理tmpfs中的文件
	@rm -rf $(TMPFS_DIR)/$(dir $<)


$(FTB_FILES): %/ftb.log : %/bp.db

	@echo "Processing $< to $@"
# 创建临时目录
	@mkdir -p $(TMPFS_DIR)/$(dir $<)
# 拷贝数据库到tmpfs
	@cp $< $(TMPFS_DIR)/$<
# 执行Python脚本，输入输出都在tmpfs
	@python3 $(PYTHON_SCRIPT) --db $(TMPFS_DIR)/$< --ftb > $(TMPFS_DIR)/$@
# 将生成的日志文件从tmpfs拷贝回原目录
	@cp $(TMPFS_DIR)/$@ $@
# 将python脚本生成的图片从tmpfs拷贝回原目录
	@cp -r $(TMPFS_DIR)/$(dir $<)/fetch_result $(dir $@)
# 清理tmpfs中的文件
	@rm -rf $(TMPFS_DIR)/$(dir $<)

$(BRANCH_FILES): %/branch.log : %/bp.db

	@echo "Processing $< to $@"
# 创建临时目录
	@mkdir -p $(TMPFS_DIR)/$(dir $<)
# 拷贝数据库到tmpfs
	@cp $< $(TMPFS_DIR)/$<
# 执行Python脚本，输入输出都在tmpfs
	@python3 $(PYTHON_SCRIPT) --db $(TMPFS_DIR)/$< --branch > $(TMPFS_DIR)/$@
# 将生成的日志文件从tmpfs拷贝回原目录
	@cp $(TMPFS_DIR)/$@ $@
# 将python脚本生成的图片从tmpfs拷贝回原目录
	@cp -r $(TMPFS_DIR)/$(dir $<)/fetch_result $(dir $@)
# 清理tmpfs中的文件
	@rm -rf $(TMPFS_DIR)/$(dir $<)

clean-fetch_analysis:
	@rm -rf $(ANALAYSIS_FILES)
	@rm -rf $(shell find $(BASE_DIR) -type d -name 'fetch_result')

clean-bb:
	@rm -rf $(BB_FILES)
	@rm -rf $(shell find $(BASE_DIR) -type d -name 'fetch_result')

clean-ftb:
	@rm -rf $(FTB_FILES)
	@rm -rf $(shell find $(BASE_DIR) -type d -name 'fetch_result')

clean-branch:
	@rm -rf $(BRANCH_FILES)
	@rm -rf $(shell find $(BASE_DIR) -type d -name 'fetch_result')

clean: clean-fetch_analysis clean-bb clean-ftb clean-branch

# @echo "Processing $@"
# @python3 $(PYTHON_SCRIPT) --db $^ > $@