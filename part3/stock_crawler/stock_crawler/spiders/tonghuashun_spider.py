# -*- coding: utf-8 -*-
import scrapy
import json
from stock_crawler.items import StockCrawlerItem


class TonghuashunSpider(scrapy.Spider):
    name = "tonghuashun"
    allowed_domains = ["10jqka.com.cn", "comment.10jqka.com.cn"]

    STUDENT_ID = ""
    STUDENT_NAME = ""

    async def start(self):
        """Scrapy 2.16+: 异步生成器，替代旧的 start_requests"""
        print("\n" + "=" * 60)
        print("同花顺财经爬虫 - 使用真实API")
        print(f": {self.STUDENT_ID}")
        print(f": {self.STUDENT_NAME}")
        print("=" * 60 + "\n")

        # 真实API接口
        for page in range(1, 4):  # 爬取前3页
            url = f"https://comment.10jqka.com.cn/api/realtime.php?block=getnews&page={page}"

            print(f"正在请求第 {page} 页...")

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://stock.10jqka.com.cn/',
                    'Accept': 'application/json, text/javascript, */*',
                }
            )

    def parse(self, response):
        """解析API返回的JSON数据"""
        try:
            text = response.text

            # 直接解析JSON（不是JSONP）
            data = json.loads(text)

            # 数据是数组格式
            if isinstance(data, list):
                articles = data
            elif isinstance(data, dict):
                articles = data.get('data') or data.get('list') or data.get('result') or []
            else:
                articles = []

            print(f"本页找到 {len(articles)} 条数据")

            for article in articles:
                if isinstance(article, dict):
                    item = StockCrawlerItem()
                    item['source'] = 'tonghuashun'
                    item['student_id'] = self.STUDENT_ID
                    item['student_name'] = self.STUDENT_NAME

                    # 提取字段
                    item['article_title'] = article.get('title', '无标题')
                    # 时间戳转日期
                    ctime = article.get('ctime')
                    if ctime:
                        from datetime import datetime
                        item['publish_date'] = datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        item['publish_date'] = article.get('date', '')

                    item['article_content'] = article.get('content', '')[:500]
                    item['comment_url'] = article.get('url', '')

                    print(f"  ✓ {item['article_title'][:40]} - {item['publish_date']}")
                    yield item

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"响应内容前200字符: {text[:200]}")
        except Exception as e:
            print(f"解析错误: {e}")