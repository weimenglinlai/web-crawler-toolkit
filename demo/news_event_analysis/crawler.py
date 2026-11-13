"""
新闻爬虫模块 - 从界面新闻采集新闻数据

采集来源: https://www.jiemian.com/lists/4.html (快报频道)
采集数据项: 新闻发表日期、新闻标题、新闻正文、新闻URL
采集规模: 100篇以上1个月以内的新闻数据
"""

import requests
from bs4 import BeautifulSoup
import re
import csv
import time
import os
import random
from datetime import datetime, timedelta

class JiemianCrawler:
    """界面新闻快报频道爬虫"""

    BASE_URL = "https://www.jiemian.com"
    LIST_URL = f"{BASE_URL}/lists/4.html"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    ]

    def __init__(self, output_dir: str = ".", progress_callback: callable = None):
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        self.session = requests.Session()
        self.articles = []
        self._delay = (1.0, 3.0)
        self._log = progress_callback or print

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.BASE_URL + "/",
        }

    def _sleep(self):
        time.sleep(random.uniform(*self._delay))

    def fetch_list_page(self, page: int) -> list:
        """采集列表页，提取文章URL列表"""
        url = f"{self.LIST_URL}?page={page}"
        self._log(f"[列表] 请求第{page}页: {url}")
        try:
            r = self.session.get(url, headers=self._get_headers(), timeout=15)
            r.encoding = "utf-8"
            urls = re.findall(r'/article/\d+\.html', r.text)
            full_urls = [self.BASE_URL + u for u in set(urls)]
            self._log(f"  -> 获取到 {len(full_urls)} 篇文章链接")
            return full_urls
        except Exception as e:
            self._log(f"  -> 请求失败: {e}")
            return []

    def parse_article(self, url: str) -> dict | None:
        """解析单篇文章页面"""
        try:
            r = self.session.get(url, headers=self._get_headers(), timeout=15)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "lxml")

            # 标题
            title_tag = soup.select_one("h1")
            if not title_tag:
                return None
            title = title_tag.text.strip()
            if not title:
                return None

            # 日期 - 从 meta 或 URL 推断
            date_str = None
            meta_date = soup.select_one('meta[property="article:published_time"]')
            if meta_date:
                date_str = meta_date.get("content", "")

            # 正文 - 收集所有段落文字
            content_div = soup.select_one(
                ".article-content, .article_content, .article-view, .article-main"
            )
            if content_div:
                paragraphs = [p.text.strip() for p in content_div.find_all("p") if p.text.strip()]
            else:
                paragraphs = [p.text.strip() for p in soup.find_all("p") if p.text.strip()]

            content = "\n".join(paragraphs)
            if not content:
                return None

            # 插图 - 采集图片URL，并下载到本地
            img_urls = []
            if content_div:
                imgs = content_div.find_all("img")
            else:
                imgs = soup.find_all("img")
            for img in imgs:
                src = img.get("src", "") or img.get("data-src", "")
                if src and not src.endswith(".svg") and "logo" not in src.lower():
                    img_urls.append(src)

            # 下载图片到本地
            img_local_paths = []
            if img_urls and self.images_dir:
                img_dir = self.images_dir
                os.makedirs(img_dir, exist_ok=True)
                art_idx = len(self.articles)
                for j, img_url in enumerate(img_urls[:5]):  # 最多下载5张
                    try:
                        ext = os.path.splitext(img_url.split("?")[0])[1]
                        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                            ext = ".jpg"
                        local_name = f"img_{art_idx}_{j}{ext}"
                        local_path = os.path.join(img_dir, local_name)
                        img_resp = self.session.get(img_url, headers=self._get_headers(), timeout=10)
                        if img_resp.status_code == 200:
                            with open(local_path, "wb") as img_f:
                                img_f.write(img_resp.content)
                            img_local_paths.append(local_path)
                    except Exception:
                        pass

            return {
                "url": url,
                "title": title,
                "date": date_str,
                "content": content,
                "images": "|".join(img_urls) if img_urls else "",
                "images_local": "|".join(img_local_paths) if img_local_paths else "",
            }
        except Exception as e:
            self._log(f"  解析失败 [{url}]: {e}")
            return None

    def crawl(self, target_count: int = 120, max_pages: int = 10) -> list:
        """执行爬虫，采集指定数量的新闻"""
        self._log("=" * 50)
        self._log("界面新闻快报频道爬虫启动")
        self._log(f"目标: 采集 {target_count}+ 篇新闻")
        self._log("=" * 50)

        all_urls = []

        # 第一阶段: 收集文章URL
        for page in range(1, max_pages + 1):
            urls = self.fetch_list_page(page)
            if not urls:
                self._log(f"第{page}页无数据，停止翻页")
                break
            all_urls.extend(urls)
            self._log(f"累计收集 {len(all_urls)} 个文章URL")
            if len(all_urls) >= target_count:
                break
            self._sleep()

        self._log(f"共收集到 {len(all_urls)} 个文章URL，开始逐篇解析...")

        # 第二阶段: 解析每篇文章
        success = 0
        for i, url in enumerate(all_urls[:target_count + 20]):
            article = self.parse_article(url)
            if article:
                self.articles.append(article)
                success += 1
                if success % 10 == 0:
                    self._log(f"已成功解析 {success} 篇")
                if success >= target_count:
                    break
            self._sleep()

        self._log(f"爬虫完成: 成功 {success}/{target_count} 篇")
        return self.articles

    def save_to_csv(self, filename: str = "news_data.csv"):
        """保存数据到CSV文件"""
        filepath = os.path.join(self.output_dir, filename)
        if not self.articles:
            self._log("无数据可保存")
            return filepath

        fieldnames = ["url", "title", "date", "content", "images", "images_local"]
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for art in self.articles:
                writer.writerow({
                    "url": art["url"],
                    "title": art["title"],
                    "date": art["date"] or "",
                    "content": art["content"],
                    "images": art["images"] or "",
                    "images_local": art.get("images_local", ""),
                })

        self._log(f"数据已保存: {filepath} ({len(self.articles)} 条)")
        return filepath

    def run(self, target_count: int = 120) -> str:
        """一站式运行: 爬取 + 保存"""
        self.crawl(target_count=target_count)
        return self.save_to_csv()

if __name__ == "__main__":
    crawler = JiemianCrawler(output_dir=os.path.dirname(__file__) or ".")
    crawler.run(target_count=120)
