# -*- coding: utf-8 -*-
import scrapy


class StockCrawlerItem(scrapy.Item):
    # 东方财富网字段
    stock_code = scrapy.Field()
    stock_name = scrapy.Field()
    comment_time = scrapy.Field()
    comment_title = scrapy.Field()
    comment_url = scrapy.Field()

    # 同花顺财经字段
    article_title = scrapy.Field()
    publish_date = scrapy.Field()
    article_content = scrapy.Field()
    source = scrapy.Field()

    # 通用字段
    student_id = scrapy.Field()
    student_name = scrapy.Field()