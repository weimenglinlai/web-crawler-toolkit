# -*- coding: utf-8 -*-
import csv
import logging
import os
from datetime import datetime

from scrapy import signals


class StockCrawlerPipeline:
    """CSV文件保存管道 - 兼容 Scrapy 2.16+"""

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        crawler.signals.connect(pipeline._spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(pipeline._spider_closed, signal=signals.spider_closed)
        return pipeline

    def _spider_opened(self, spider):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if spider.name == 'tonghuashun':
            filename = f"tonghuashun_{timestamp}.csv"
            self.fieldnames = ['article_title', 'publish_date', 'article_content',
                               'comment_url', 'student_id', 'student_name', 'source']
        else:
            filename = f"eastmoney_{timestamp}.csv"
            self.fieldnames = ['stock_code', 'stock_name', 'comment_time',
                               'comment_title', 'comment_url', 'student_id', 'student_name', 'source']

        os.makedirs("output", exist_ok=True)
        filepath = os.path.join("output", filename)

        self.file = open(filepath, 'w', newline='', encoding='utf-8-sig')
        self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames)
        self.writer.writeheader()

        spider.logger.info(f"CSV文件已创建: {filepath}")

    def _spider_closed(self, spider):
        if hasattr(self, 'file') and self.file:
            self.file.close()
        spider.logger.info("CSV文件已保存")

    def process_item(self, item, spider):
        row = {field: item.get(field, '') for field in self.fieldnames}
        self.writer.writerow(row)
        return item