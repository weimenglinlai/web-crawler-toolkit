# -*- coding: utf-8 -*-

BOT_NAME = "stock_crawler"

SPIDER_MODULES = ["stock_crawler.spiders"]
NEWSPIDER_MODULE = "stock_crawler.spiders"

ROBOTSTXT_OBEY = False
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
DOWNLOAD_DELAY = 0.5

ITEM_PIPELINES = {
    "stock_crawler.pipelines.StockCrawlerPipeline": 300,
}

# 日志配置（run.py 会覆盖为 INFO）
LOG_LEVEL = 'INFO'
LOG_ENABLED = True
LOG_STDOUT = True