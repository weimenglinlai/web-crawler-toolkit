"""Check how Scrapy 2.16 engine calls the spider start method"""
import inspect
import scrapy.core.engine

# Get the full engine source
src = inspect.getsource(scrapy.core.engine.ExecutionEngine.open_spider)
print("=== open_spider ===")
print(src)

src2 = inspect.getsource(scrapy.core.engine.ExecutionEngine._next_request_from_spider)
print("\n=== _next_request_from_spider ===")
print(src2)

# Also check spider.py for start
import scrapy.spiders
src3 = inspect.getsource(scrapy.spiders.Spider.start)
print("\n=== Spider.start (async) ===")
print(src3)
