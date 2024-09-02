# Makefile

# 定义变量
BASE_DIR := /nfs/home/goulingrui/expri_results/gem5/frontend_06/NanhuDRAMSimWithTageDB-eea6a98f73-table_sharing
PYTHON_SCRIPT := /nfs/home/goulingrui/project/gem5_data_proc/tage_lifetime/tage_lifetime.py
TMPFS_DIR := /dev/shm

# 找到所有的bp.db文件
DB_FILES := $(shell find $(BASE_DIR) -type f -name 'bp.db')
# bp.db -> tage_lifetime.log
ANALAYSIS_FILES := $(DB_FILES:%/bp.db=%/tage_lifetime.log)

# 定义伪目标，以防止与同名文件冲突
.PHONY: all, clean

# 默认目标
all: $(ANALAYSIS_FILES)

# 模式规则：对每个bp.db文件执行Python脚本，并重定向输出到stage_lifetime.log
$(ANALAYSIS_FILES):  %/tage_lifetime.log : %/bp.db

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
	@cp -r $(TMPFS_DIR)/$(dir $<)/tage_entry_analysis $(dir $@)
# 清理tmpfs中的文件
	@rm -rf $(TMPFS_DIR)/$(dir $<)

clean:
	@rm -rf $(ANALAYSIS_FILES)
	@rm -rf $(shell find $(BASE_DIR) -type d -name 'tage_entry_analysis')

# @echo "Processing $@"
# @python3 $(PYTHON_SCRIPT) --db $^ > $@