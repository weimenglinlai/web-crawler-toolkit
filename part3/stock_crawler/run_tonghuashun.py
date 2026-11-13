# -*- coding: utf-8 -*-
import os
import sys
from scrapy import cmdline

# 自动切换到项目根目录
project_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_dir)
sys.path.insert(0, project_dir)

cmdline.execute(["scrapy", "crawl", "tonghuashun",
                 "-s", "LOG_LEVEL=INFO",
                 "-s", "LOG_STDOUT=True"])
