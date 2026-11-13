# 实践任务二：多线程蒸汽平台游戏数据爬虫

import json
import os
import re
import sys
import threading
import time
from queue import Queue

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# ==================== 配置区域 ====================
DATA_PATH = "datas"
CSV_FILE = "gameDatas.csv"
CHROME_DRIVER_PATH = r"./data"
BASE_URL = "https://store.steamchina.com/search/?sort_by=Reviews_DESC"
THREAD_COUNT = 4  # 线程数
PAGE_LOAD_WAIT = 2  # 页面加载等待秒数

# 线程锁，保护文件写入
write_lock = threading.Lock()

# ==================== 函数定义 ====================
def init_csv():
    """初始化 CSV 文件"""
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)
    df_header = pd.DataFrame(columns=["Name", "Price", "Rating"])
    df_header.to_csv(CSV_FILE, encoding="utf_8_sig", index=False, mode="w")


def save_infos(name, price, rating):
    """将游戏的名称、价格和好评率保存为JSON文件，并追加到CSV文件中"""
    # 保存为 JSON
    with open(os.path.join(DATA_PATH, f"{hash(name)}.json"), "w", encoding="utf-8") as f:
        data = {"Name": name, "Price": price, "Rating": rating}
        json.dump(data, f, indent=4, ensure_ascii=False)

    # 追加到 CSV（加锁，防止多线程写入冲突）
    with write_lock:
        new_line = pd.DataFrame([{"Name": name, "Price": price, "Rating": rating}])
        new_line.to_csv(CSV_FILE, encoding="utf_8_sig", index=False, mode="a", header=False)

def get_rating(driver):
    """提取游戏好评率"""
    try:
        elem = driver.find_element(By.CLASS_NAME, "user_reviews_summary")
        if elem and elem.text:
            lines = elem.text.strip().split("\n")
            for line in lines:
                if "好评" in line or "差评" in line:
                    return line.strip()[:60]
    except Exception:
        pass

    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        patterns = [
            r'([^、\n]{2,6}?(?:好评|差评)[^、\n]{0,4}?)\s*\([\d,]+\)',
            r'(?:全部评测|总体评测)[：:]\s*\n?\s*([^\(\n]+)\s*\(',
        ]
        for pattern in patterns:
            m = re.search(pattern, page_text)
            if m:
                return m.group(1).strip()[:30]
    except Exception:
        pass

    return "暂无评价"

def get_price(driver):
    """提取游戏价格"""
    try:
        elem = driver.find_element(By.CLASS_NAME, "game_purchase_price")
        if elem and elem.text:
            return elem.text.strip()
    except Exception:
        pass
    try:
        elem = driver.find_element(By.CLASS_NAME, "discount_final_price")
        if elem and elem.text:
            return elem.text.strip()
    except Exception:
        pass
    return "价格未知"

# ==================== 线程类 ====================
class GameCrawlerThread(threading.Thread):
    """爬虫线程：从游戏链接队列中取出链接，访问详情页，提取数据并保存"""

    def __init__(self, thread_id, link_queue, stats):
        super().__init__()
        self.thread_id = thread_id
        self.link_queue = link_queue  # Queue[str]
        self.stats = stats  # {"success": 0, "fail": 0}
        self.driver = None

    def run(self):
        """线程主循环：从队列取链接 -> 访问详情页 -> 提取数据 -> 保存"""
        service = Service(CHROME_DRIVER_PATH)
        self.driver = webdriver.Chrome(service=service)

        while not self.link_queue.empty():
            try:
                url = self.link_queue.get(timeout=2)
            except Exception:
                # 队列为空
                break

            try:
                self.driver.get(url)
                time.sleep(0.8)

                # 提取游戏名称
                try:
                    name = self.driver.find_element(By.CLASS_NAME, "apphub_AppName").text
                except Exception:
                    name = "未知"

                # 提取价格
                price = get_price(self.driver)

                # 提取好评率
                rating = get_rating(self.driver)

                # 保存数据
                save_infos(name, price, rating)

                # 计数
                with write_lock:
                    self.stats["success"] += 1

                print(f"  [线程{self.thread_id}] ✓ {name[:30]:30} | {price:12} | {rating[:20]}")

            except Exception as e:
                with write_lock:
                    self.stats["fail"] += 1
                print(f"  [线程{self.thread_id}] ✗ 失败: {str(e)[:50]}")

            finally:
                self.link_queue.task_done()

        self.driver.quit()


# ==================== 主爬虫函数 ====================
def crawl():
    """多线程爬虫主函数"""

    # ---- 初始化爬虫环境 ----
    init_csv()

    # ---- 步骤1：获取所有游戏链接 ----
    print("\n[1/3] 正在获取游戏列表...")
    driver = webdriver.Chrome(service=Service(CHROME_DRIVER_PATH))
    driver.get(BASE_URL)
    time.sleep(PAGE_LOAD_WAIT)

    # 获取总页数
    try:
        page_elem = driver.find_element(By.CLASS_NAME, "search_pagination_right")
        pages = page_elem.find_elements(By.TAG_NAME, "a")
        total_pages = max(
            int(a.text) for a in pages if a.text.isdigit()
        ) if pages else 1
    except Exception:
        total_pages = 1
    print(f"  总页数: {total_pages}")

    # 遍历所有页面，收集游戏链接
    game_link_list = []

    for page in range(1, total_pages + 1):
        if page > 1:
            driver.get(f"{BASE_URL}&page={page}")
            time.sleep(PAGE_LOAD_WAIT)

        print(f"  正在提取第 {page}/{total_pages} 页链接...")

        try:
            results = driver.find_element(By.ID, "search_resultsRows")
            for a in results.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href")
                if href and href.startswith("https://store.steamchina.com"):
                    game_link_list.append(href)
        except Exception as e:
            print(f"  ✗ 第{page}页提取失败: {e}")

    driver.quit()

    # 去重
    game_link_list = list(dict.fromkeys(game_link_list))
    print(f"  共获取 {len(game_link_list)} 个游戏链接")

    if not game_link_list:
        print("  没有获取到游戏链接，退出。")
        return

    # ---- 步骤2：多线程并发爬取 ----

    # 将链接放入线程安全队列
    link_queue = Queue()
    for link in game_link_list:
        link_queue.put(link)

    # 统计
    stats = {"success": 0, "fail": 0}

    # 创建并启动线程
    print(f"\n[2/3] 启动 {THREAD_COUNT} 个线程并发采集...")
    threads = []
    for i in range(THREAD_COUNT):
        t = GameCrawlerThread(i + 1, link_queue, stats)
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    # ---- 步骤3：统计结果 ----
    print("\n[3/3] 采集完成！")
    print("=" * 60)
    print(f"  成功: {stats['success']} 条")
    print(f"  失败: {stats['fail']} 条")
    print(f"  文件: {CSV_FILE}")
    print(f"  数据目录: {DATA_PATH}/")
    print("=" * 60)


# ==================== 主入口 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("蒸汽平台游戏数据多线程爬虫")
    print(f": ")
    print(f": ")
    print("=" * 60)

    try:
        start_time = time.time()
        crawl()
        elapsed = time.time() - start_time
        print(f"\n总耗时: {elapsed:.2f} 秒 ({elapsed / 60:.2f} 分钟)")
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n按 Enter 退出...")
