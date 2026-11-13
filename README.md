# Web Crawler Toolkit

Focused crawlers, stock data collection and news event analysis utilities.

## Structure

```
demo/news_event_analysis/config.py
demo/news_event_analysis/crawler.py
demo/news_event_analysis/entity_extractor.py
demo/news_event_analysis/gui_config.json
demo/news_event_analysis/gui_main.py
demo/news_event_analysis/visualizer_gui.py
part1/2025长沙.txt
part1/steam.txt
part2/风力等级.txt
part3/steam_crawler/steam_crawler.py
part3/stock_crawler/inspect_engine.py
part3/stock_crawler/response_index.txt
part3/stock_crawler/run.py
part3/stock_crawler/run_tonghuashun.py
part3/stock_crawler/scrapy.cfg
part3/stock_crawler/stock_crawler/items.py
part3/stock_crawler/stock_crawler/middlewares.py
part3/stock_crawler/stock_crawler/pipelines.py
part3/stock_crawler/stock_crawler/settings.py
part3/stock_crawler/stock_crawler/spiders/stock_spider.py
part3/stock_crawler/stock_crawler/spiders/tonghuashun_spider.py
```

## Setup

Install dependencies from `requirements.txt` when present:

```bash
pip install -r requirements.txt
```

Data files, model weights and generated outputs are not included; place them under the paths referenced by the configuration before running.
