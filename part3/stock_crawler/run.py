# -*- coding: utf-8 -*-
import os
import sys
from scrapy import cmdline


def main():
    # 自动切换到项目根目录，无论从哪里运行都能找到 scrapy.cfg
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    sys.path.insert(0, project_dir)

    print("\n" + "=" * 60)
    print("        股票评论数据爬虫 - Scrapy")
    print("=" * 60)
    print("请确保已在 stock_spider.py 中设置正确的和")
    print("=" * 60 + "\n")

    cmdline.execute(["scrapy", "crawl", "stock_spider",
                     "-s", "LOG_LEVEL=INFO",
                     "-s", "LOG_STDOUT=True"])


if __name__ == "__main__":
    main()
