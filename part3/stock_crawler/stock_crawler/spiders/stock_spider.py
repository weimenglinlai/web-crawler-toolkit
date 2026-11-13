# -*- coding: utf-8 -*-
import scrapy
import json
import re
from datetime import datetime, timedelta
from stock_crawler.items import StockCrawlerItem


class StockSpider(scrapy.Spider):
    name = "stock_spider"
    allowed_domains = ["eastmoney.com", "reportapi.eastmoney.com"]

    # ========== 请修改为您的和 ==========
    STUDENT_ID = ""
    STUDENT_NAME = ""

    # ==========================================

    async def start(self):
        """Scrapy 2.16+: 异步生成器，替代旧的 start_requests"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        print("\n" + "=" * 60)
        print("股票评论数据爬虫 - Scrapy")
        print(f": {self.STUDENT_ID}")
        print(f": {self.STUDENT_NAME}")
        print(f"时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
        print("=" * 60 + "\n")

        for page_no in range(1, 4):
            begin_time = start_date.strftime("%Y-%m-%d")
            end_time = end_date.strftime("%Y-%m-%d")

            url = f"https://reportapi.eastmoney.com/report/list?cb=datatable3684874&industryCode=*&pageSize=50&industry=*&rating=*&ratingChange=*&beginTime={begin_time}&endTime={end_time}&pageNo={page_no}&fields=&qType=0&orgCode=&code=*&rcode="

            print(f"正在请求第 {page_no} 页...")

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )

    def parse(self, response):
        try:
            text = response.text
            match = re.search(r'datatable3684874\((.*)\)', text, re.DOTALL)

            if match:
                data = json.loads(match.group(1))
                reports = data.get('data', [])
                print(f"本页找到 {len(reports)} 条数据")

                for report in reports:
                    item = StockCrawlerItem()
                    item['stock_code'] = report.get('stockCode', '')
                    item['stock_name'] = report.get('stockName', '')
                    item['comment_time'] = report.get('publishDate', '')
                    item['comment_title'] = report.get('title', '')
                    item[
                        'comment_url'] = f"https://data.eastmoney.com/report/{report.get('infoCode', '')}.html" if report.get(
                        'infoCode') else ''
                    item['student_id'] = self.STUDENT_ID
                    item['student_name'] = self.STUDENT_NAME

                    print(
                        f"  获取: {item['stock_name']} - {item['comment_title'][:35] if item['comment_title'] else '无标题'}...")
                    yield item
        except Exception as e:
            print(f"解析错误: {e}")