"""
新闻事件抽取分析系统 - GUI 版本
"""

import os
import sys
import csv
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from crawler import JiemianCrawler
from entity_extractor import EntityExtractor
from config import C, load_config, save_config, AppState

import queue
import logging
import shutil
import concurrent.futures
from PIL import Image, ImageTk

# Logging config
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S", force=True)
logger = logging.getLogger("news")

# Suppress noisy libs
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("jieba").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("concurrent").setLevel(logging.WARNING)

state = AppState()


class FlatButton(tk.Canvas):
    def __init__(self, parent, text="", command=None, width=120, height=40,
                 color=C["primary"], hover_color=None, text_color=None,
                 font_size=10, state=tk.NORMAL, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=C["card"], highlightthickness=0, **kw)
        self.command = command
        self.color = color
        self.hover_color = hover_color or self._darken(color, 0.9)
        self.text_color = text_color or C["primary_text"]
        self.text_str = text
        self.font_size = font_size
        self._enabled = (state != tk.DISABLED)
        self._hover = False
        self._pressed = False
        self._draw()
        if self._enabled:
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            self.bind("<Button-1>", self._on_press)
            self.bind("<ButtonRelease-1>", self._on_release)

    def _darken(self, hex_color, factor):
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw(self):
        self.delete("all")
        r = 8
        w, h = int(self["width"]), int(self["height"])
        if self._pressed:
            c = self._darken(self.color, 0.85)
        elif self._hover and self._enabled:
            c = self.hover_color
        elif not self._enabled:
            c = "#cbd5e1"
        else:
            c = self.color
        self.create_rounded_rect(1, 1, w - 1, h - 1, r, fill=c, outline=c)
        tc = self.text_color if self._enabled else "#94a3b8"
        self.create_text(w / 2, h / 2, text=self.text_str, fill=tc,
                         font=("Microsoft YaHei", self.font_size))

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        points = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1,
                  x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                  x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
                  x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(points, smooth=True, **kw)

    def config(self, **kw):
        if "text" in kw:
            self.text_str = kw.pop("text")
        if "state" in kw:
            s = kw.pop("state")
            self._enabled = (s != tk.DISABLED)
        if "color" in kw:
            self.color = kw.pop("color")
        if "command" in kw:
            self.command = kw.pop("command")
        super().config(**kw)
        self._draw()

    def _on_enter(self, e):
        self._hover = True; self._draw()

    def _on_leave(self, e):
        self._hover = False; self._draw()

    def _on_press(self, e):
        self._pressed = True; self._draw()

    def _on_release(self, e):
        self._pressed = False; self._draw()
        if self._enabled and self.command:
            self.command()


class StepIndicator(tk.Canvas):
    def __init__(self, parent, steps, **kw):
        height = 60
        super().__init__(parent, height=height, bg=C["card"], highlightthickness=0, **kw)
        self.steps = steps
        self.current = 0
        self.bind("<Configure>", lambda e: self._draw())

    def set_current(self, idx):
        self.current = idx; self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 100:
            return
        n = len(self.steps)
        spacing = w / n
        y = 22
        r_size = 12
        for i, label in enumerate(self.steps):
            cx = int(spacing * (i + 0.5))
            if i < self.current:
                fc, tc = C["success"], "#ffffff"
                text = "\u2713"
                fw = "bold"
            elif i == self.current:
                fc, tc = C["primary"], "#ffffff"
                text = str(i + 1)
                fw = "bold"
            else:
                fc, tc = "#e2e8f0", C["text3"]
                text = str(i + 1)
                fw = "normal"
            self.create_oval(cx - r_size, y - r_size, cx + r_size, y + r_size, fill=fc, outline=fc)
            self.create_text(cx, y, text=text, fill=tc, font=("Microsoft YaHei", 10, fw))
            self.create_text(cx, y + 28, text=label, fill=C["text2"] if i <= self.current else C["text3"],
                             font=("Microsoft YaHei", 8))
            if i < n - 1:
                lx = cx + r_size + 4
                rx = int(spacing * (i + 1.5)) - r_size - 4
                lc = C["success"] if i < self.current else "#e2e8f0"
                self.create_line(lx, y, rx, y, fill=lc, width=2)


class Card(ttk.Frame):
    def __init__(self, parent, title="", padding=16, **kw):
        super().__init__(parent, style="Card.TFrame", **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        if title:
            hdr = tk.Frame(self, bg=C["card"])
            hdr.grid(row=0, column=0, sticky="ew", pady=(0, padding))
            tk.Label(hdr, text=title, font=("Microsoft YaHei", 11, "bold"),
                     fg=C["text"], bg=C["card"]).pack(side=tk.LEFT)
        self._content = tk.Frame(self, bg=C["card"])
        self._content.grid(row=1, column=0, sticky="nsew")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("新闻事件抽取分析系统")
        cfg = load_config()
        self.root.geometry(f"{cfg['win_width']}x{cfg['win_height']}")
        self.root.minsize(1000, 680)
        self.root.configure(bg=C["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style()
        style.configure("Card.TFrame", background=C["card"])
        style.configure("TScrollbar", background=C["border"], troughcolor=C["bg"])
        style.configure("TProgressbar", thickness=4, background=C["primary"], troughcolor=C["border"])

        self._build(cfg)
        self._log("系统就绪")

    def _on_close(self):
        save_config(
            target_count=self.target_var.get(),
            win_width=self.root.winfo_width(),
            win_height=self.root.winfo_height(),
        )
        self.root.destroy()

    def _build(self, cfg):
        topbar = tk.Frame(self.root, bg=C["primary"], height=48)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="新闻事件抽取分析系统", font=("Microsoft YaHei", 13, "bold"),
                 fg="#ffffff", bg=C["primary"]).pack(side=tk.LEFT, padx=20, pady=10)
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(topbar, textvariable=self.status_var, font=("Microsoft YaHei", 9),
                 fg="#cbd5e1", bg=C["primary"]).pack(side=tk.RIGHT, padx=20, pady=10)

        self.steps = StepIndicator(self.root, ["数据采集", "实体抽取", "可视化"])
        self.steps.pack(fill=tk.X, padx=1, pady=(1, 0))

        self.progress_bar = ttk.Progressbar(self.root, mode="indeterminate", style="TProgressbar")
        self.progress_bar.pack(fill=tk.X, padx=12, pady=(0, 0))

        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=C["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.columnconfigure(0, weight=1)

        right = tk.Frame(body, bg=C["bg"])
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)

        c1 = Card(left, "数据采集")
        c1.pack(fill=tk.X, pady=(0, 8))
        f = c1._content
        self.target_var = tk.StringVar(value=cfg.get("target_count", "120"))
        row = tk.Frame(f, bg=C["card"])
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="目标篇数", font=("Microsoft YaHei", 9), fg=C["text2"],
                 bg=C["card"]).pack(side=tk.LEFT)
        e = tk.Entry(row, textvariable=self.target_var, width=6, font=("Microsoft YaHei", 10),
                     bg=C["input_bg"], fg=C["text"], relief=tk.FLAT, insertbackground=C["primary"])
        e.pack(side=tk.LEFT, padx=8, ipady=2)
        e.config(highlightthickness=1, highlightbackground=C["border"])
        e.bind("<FocusIn>", lambda ev: e.config(highlightbackground=C["primary"]))
        e.bind("<FocusOut>", lambda ev: e.config(highlightbackground=C["border"]))
        self.btn_crawl = FlatButton(f, text="开始采集", command=self._start_crawl,
                                    color=C["primary"], width=160, height=36, font_size=10)
        self.btn_crawl.pack(pady=(0, 6))
        self.crawl_label = tk.Label(f, text="尚未采集", font=("Microsoft YaHei", 8), fg=C["text3"], bg=C["card"])
        self.crawl_label.pack(anchor=tk.W)

        c2 = Card(left, "实体抽取")
        c2.pack(fill=tk.X, pady=(0, 8))
        f = c2._content
        self.btn_extract = FlatButton(f, text="开始抽取", command=self._start_extraction,
                                      color="#94a3b8", width=160, height=36, font_size=10)
        self.btn_extract.pack(pady=(0, 6))
        self.btn_extract._enabled = False
        self.btn_extract._draw()
        self.extract_label = tk.Label(f, text="等待数据采集", font=("Microsoft YaHei", 8), fg=C["text3"], bg=C["card"])
        self.extract_label.pack(anchor=tk.W)

        c3 = Card(left, "可视化与导出")
        c3.pack(fill=tk.X, pady=(0, 8))
        f = c3._content
        self.btn_viz = FlatButton(f, text="生成图表", command=self._start_visualization,
                                  color="#94a3b8", width=160, height=36, font_size=10)
        self.btn_viz.pack(pady=(0, 6))
        self.btn_viz._enabled = False
        self.btn_viz._draw()

        exp_frame = tk.Frame(f, bg=C["card"])
        exp_frame.pack(fill=tk.X, pady=(0, 4))
        exports = [
            ("词云", "wordcloud_corpus"), ("单篇", "wordclouds_per_article"),
            ("图谱", "knowledge_graph"), ("统计", "entity_count_bar"),
            ("Top10", "entity_top10"), ("动词", "event_verbs"),
            ("共现", "cooccurrence"),
        ]
        for i, (label, key) in enumerate(exports):
            btn = tk.Button(exp_frame, text=label, font=("Microsoft YaHei", 8),
                            bg=C["card"], fg=C["text2"], relief=tk.FLAT,
                            activebackground=C["hover"], activeforeground=C["primary"],
                            bd=0, padx=6, pady=3,
                            command=lambda k=key: self._export_image(k))
            btn.bind("<Enter>", lambda ev, b=btn: b.config(fg=C["primary"]))
            btn.bind("<Leave>", lambda ev, b=btn: b.config(fg=C["text2"]))
            row_i, col_i = divmod(i, 4)
            btn.grid(row=row_i, column=col_i, sticky="ew", padx=1, pady=1)
        for col_i in range(4):
            exp_frame.columnconfigure(col_i, weight=1)
        all_frame = tk.Frame(f, bg=C["card"])
        all_frame.pack(fill=tk.X, pady=2)
        for i, (label, cmd) in enumerate([("全部导出", self._export_all), ("打开目录", self._open_output_dir)]):
            btn = tk.Button(all_frame, text=label, font=("Microsoft YaHei", 8, "bold"),
                            bg=C["hover"], fg=C["text"], relief=tk.FLAT,
                            activebackground=C["active"], activeforeground=C["primary"],
                            bd=0, padx=10, pady=4, command=cmd)
            btn.bind("<Enter>", lambda ev, b=btn: b.config(bg=C["active"]))
            btn.bind("<Leave>", lambda ev, b=btn: b.config(bg=C["hover"]))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        c4 = Card(left, "统计摘要")
        c4.pack(fill=tk.X, pady=(0, 8))
        self.summary_text = tk.Text(c4._content, height=4, font=("Consolas", 9),
                                    bg=C["hover"], fg=C["text"], relief=tk.FLAT,
                                    state=tk.DISABLED, bd=0, padx=10, pady=8)
        self.summary_text.pack(fill=tk.X)

        c5 = Card(left, "运行日志")
        c5.pack(fill=tk.BOTH, expand=True)
        log_frame = tk.Frame(c5._content, bg=C["border"], bd=0)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, font=("Consolas", 9),
                                bg=C["log_bg"], fg=C["log_text"], relief=tk.FLAT,
                                state=tk.DISABLED, bd=0, padx=12, pady=8,
                                insertbackground=C["log_text"])
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scroll.set)
        self.log_text.tag_configure("info", foreground="#94a3b8")
        self.log_text.tag_configure("ok", foreground="#22c55e")
        self.log_text.tag_configure("warn", foreground="#f59e0b")
        self.log_text.tag_configure("err", foreground="#ef4444")

        viz_header = tk.Frame(right, bg=C["bg"])
        viz_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tk.Label(viz_header, text="图表预览", font=("Microsoft YaHei", 11, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(side=tk.LEFT)

        self.preview_var = tk.StringVar(value="wordcloud_corpus")
        self._preview_btns = []
        preview_opts = [
            ("全文词云", "wordcloud_corpus"), ("单篇词云", "wordclouds_per_article"),
            ("知识图谱", "knowledge_graph"), ("实体统计", "entity_count_bar"),
            ("Top10", "entity_top10"), ("事件动词", "event_verbs"),
            ("共现矩阵", "cooccurrence"),
        ]
        nav = tk.Frame(viz_header, bg=C["bg"])
        nav.pack(side=tk.RIGHT)
        for text, val in preview_opts:
            b = tk.Label(nav, text=text, font=("Microsoft YaHei", 9),
                         fg=C["text2"], bg=C["bg"], padx=8, pady=3, cursor="hand2")
            b.bind("<Button-1>", lambda e, v=val: self._switch_preview(v))
            b.pack(side=tk.LEFT)
            self._preview_btns.append((b, val))
        self._update_preview_tabs()

        self.preview = tk.Canvas(right, bg=C["canvas_bg"], highlightthickness=0, bd=0, cursor="crosshair")
        self.preview.grid(row=1, column=0, sticky="nsew")
        self._orig_img = None
        self._zoom_level = 1.0
        self._zoom_pan_x = 0
        self._zoom_pan_y = 0
        self._zoom_dragging = False
        self._zoom_drag_start = None
        self._zoom_percent_id = None
        self.preview.bind("<MouseWheel>", self._on_zoom_wheel)
        self.preview.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        self.preview.bind("<Button-3>", self._on_zoom_rightclick)
        self.preview.bind("<Button-1>", self._on_zoom_drag_start)
        self.preview.bind("<B1-Motion>", self._on_zoom_drag_move)
        self.preview.bind("<ButtonRelease-1>", self._on_zoom_drag_end)
        self.preview.bind("<Double-Button-1>", self._on_zoom_reset)

        # 分析描述面板
        self.analysis_panel = tk.Text(right, height=5, font=("Microsoft YaHei", 9),
                                       bg=C["hover"], fg=C["text"], relief=tk.FLAT,
                                       state=tk.DISABLED, bd=0, padx=12, pady=8,
                                       wrap=tk.WORD)
        self.analysis_panel.grid(row=2, column=0, sticky="ew", pady=(6, 0))

    def _show_analysis_for(self, chart_key):
        if not hasattr(self, 'analysis_panel'):
            return
        # 根据图表类型显示对应描述
        if not state.all_entities or not state.all_triples:
            return
        persons = set()
        locs = set()
        orgs = set()
        events = set()
        for e in state.all_entities:
            persons.update(e.get("persons", []))
            locs.update(e.get("locations", []))
            orgs.update(e.get("organizations", []))
            events.update(e.get("events", []))
        n = len(state.articles)
        triples_n = len(state.all_triples)

        # 收集高频词
        all_freq = Counter()
        for e in state.all_entities:
            for w, c in e.get("word_freq", []):
                all_freq[w] += c
        top5 = [w for w, _ in all_freq.most_common(5)]

        texts = {
            "wordcloud_corpus": f'基于 {n} 篇新闻分析：共提取 {len(persons)} 个人名、{len(locs)} 个地名、{len(orgs)} 个机构名、{len(events)} 个事件动词，生成 {triples_n} 条实体关系三元组。高频词 Top5：{"\u3001".join(top5)}',
            "wordclouds_per_article": f'单篇词云子图展示每篇新闻的关键词分布，可对比不同新闻的主题差异。共展示 {min(n, 9)} 篇新闻。',
            "knowledge_graph": f'知识图谱展示了人物、地点、机构之间的关系网络，共 {triples_n} 条关系边。节点颜色：红色=人物，绿色=地点，蓝色=机构，紫色=事件，灰色=其他。',
            "entity_count_bar": f'实体类型统计：人物 {len(persons)}、地点 {len(locs)}、机构 {len(orgs)}、事件动词 {len(events)}。可见新闻报道中这些元素的分布比例。',
            "entity_top10": f'Top10 排行展示了各类实体的出现频率，反映新闻报道的重点人物、热点地区和活跃机构。',
            "event_verbs": f'事件动词 Top15 展示了新闻中最常见的动作，反映报道的事件类型和语义特征。',
            "cooccurrence": f'共现矩阵展示人物与地点/机构在同篇新闻中共同出现的比例，颜色越深表示关联越强。横轴=地点/机构，纵轴=人物。',
        }
        text = texts.get(chart_key, "")
        self.analysis_panel.config(state=tk.NORMAL)
        self.analysis_panel.delete(1.0, tk.END)
        self.analysis_panel.insert(tk.END, text)
        self.analysis_panel.config(state=tk.DISABLED)

    def _show_full_analysis(self, text):
        """在分析面板显示完整分析报告"""
        if not hasattr(self, 'analysis_panel'):
            return
        self.analysis_panel.config(state=tk.NORMAL)
        self.analysis_panel.delete(1.0, tk.END)
        self.analysis_panel.insert(tk.END, text)
        self.analysis_panel.config(state=tk.DISABLED)

    def _update_preview_tabs(self):
        cur = self.preview_var.get()
        for b, val in self._preview_btns:
            if val == cur:
                b.config(fg=C["primary"], font=("Microsoft YaHei", 9, "bold"))
            else:
                b.config(fg=C["text2"], font=("Microsoft YaHei", 9))

    def _switch_preview(self, val):
        self.preview_var.set(val)
        self._update_preview_tabs()
        self._show_preview(state.cached_images.get(val))
        # 如有完整分析报告则始终显示，否则显示图表简介
        if hasattr(state, '_analysis_text') and state._analysis_text:
            self._show_full_analysis(state._analysis_text)
        else:
            self._show_analysis_for(val)

    def _progress_start(self):
        self.root.after(0, self.progress_bar.start)

    def _progress_stop(self):
        def stop():
            self.progress_bar.stop()
            self.progress_bar["value"] = 0
        self.root.after(0, stop)

    def _log(self, msg, tag="info"):
        def append():
            self.log_text.config(state=tk.NORMAL)
            ts = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"{ts}  ", "info")
            self.log_text.insert(tk.END, f"{msg}\n", tag)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, append)

    def _enable_btn(self, btn, color=C["primary"]):
        def fn():
            btn._enabled = True
            btn.color = color
            btn._draw()
        self.root.after(0, fn)

    def _disable_btn(self, btn):
        def fn():
            btn._enabled = False
            btn._draw()
        self.root.after(0, fn)

    def _start_crawl(self):
        self._disable_btn(self.btn_crawl)
        self._progress_start()
        self._log("开始数据采集...")

        def run():
            try:
                target = int(self.target_var.get())
            except ValueError:
                target = 120
            t0 = time.time()
            csv_path = os.path.join(state.output_dir, "news_data.csv")

            if os.path.exists(csv_path):
                try:
                    with open(csv_path, "r", encoding="utf-8-sig") as f:
                        existing = list(csv.DictReader(f))
                except Exception:
                    existing = []
                self._log(f"已有数据 {len(existing)} 条")
                if len(existing) >= 100:
                    state.articles = existing
                    self._log(f"数据充足, 跳过采集", "ok")
                    self._crawl_done(len(existing), time.time() - t0)
                    return

            try:
                crawler = JiemianCrawler(output_dir=state.output_dir, progress_callback=self._log)
                crawler.run(target_count=target)
                with open(csv_path, "r", encoding="utf-8-sig") as f:
                    state.articles = list(csv.DictReader(f))
            except Exception as ex:
                self._log(f"采集失败: {ex}", "err")
                self._crawl_done(0, time.time() - t0)
                return

            self._crawl_done(len(state.articles), time.time() - t0)

        threading.Thread(target=run, daemon=True).start()

    def _crawl_done(self, count, elapsed):
        self._progress_stop()
        if count > 0:
            self._log(f"采集完成: {count} 篇 (耗时 {elapsed:.1f}s)", "ok")
            self.root.after(0, lambda: self.status_var.set(f"已采集 {count} 篇"))
            self.root.after(0, lambda: self.crawl_label.config(text=f"\u2713 {count} 篇文章", fg=C["success"]))
            self._enable_btn(self.btn_extract)
            self.root.after(0, lambda: self.steps.set_current(1))
        else:
            self._log("采集未获得数据", "err")
        self._enable_btn(self.btn_crawl)
        self._update_summary()

    def _start_extraction(self):
        self._disable_btn(self.btn_extract)
        self._progress_start()
        self._log("开始实体抽取...")

        def run():
            t0 = time.time()
            try:
                extractor = EntityExtractor()
                total = len(state.articles)
                results = [None] * total
                lock = threading.Lock()
                progress_lock = threading.Lock()
                completed = [0]

                def process_one(i, art):
                    content = art.get("content", "")
                    try:
                        entities = extractor.process(content)
                        triples = extractor.extract_triples(content, entities)
                    except Exception:
                        entities = {}
                        triples = []
                    with lock:
                        results[i] = (entities, triples)
                    with progress_lock:
                        completed[0] += 1
                        if completed[0] % 20 == 0 or completed[0] == total:
                            self._log(f"  进度 {completed[0]}/{total}")

                if total > 0:
                    workers = max(1, min(16, total))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                        pool.map(lambda args: process_one(*args),
                                 [(i, state.articles[i]) for i in range(total)])

                state.all_entities = [r[0] for r in results]
                all_triples = []
                for r in results:
                    all_triples.extend(r[1])
                state.all_triples = all_triples

                entity_path = os.path.join(state.output_dir, "entities.json")
                se = []
                for e in state.all_entities:
                    entry = {}
                    for k, v in e.items():
                        entry[k] = dict(v) if hasattr(v, 'most_common') else v
                    se.append(entry)
                with open(entity_path, "w", encoding="utf-8") as f:
                    json.dump(se, f, ensure_ascii=False, indent=2)
                with open(os.path.join(state.output_dir, "triples.json"), "w", encoding="utf-8") as f:
                    json.dump(all_triples, f, ensure_ascii=False, indent=2)

            except Exception as ex:
                self._log(f"抽取失败: {ex}", "err")
                self._extract_done(0, time.time() - t0)
                return

            self._extract_done(len(all_triples), time.time() - t0)

        threading.Thread(target=run, daemon=True).start()

    def _extract_done(self, triple_count, elapsed):
        self._progress_stop()
        if triple_count > 0:
            self._log(f"抽取完成: {triple_count} 条三元组 (耗时 {elapsed:.1f}s)", "ok")
            self.root.after(0, lambda: self.status_var.set(f"已抽取 {triple_count} 条三元组"))
            self.root.after(0, lambda: self.extract_label.config(text=f"\u2713 {triple_count} 条", fg=C["success"]))
            self._enable_btn(self.btn_viz)
            self.root.after(0, lambda: self.steps.set_current(2))
        self._enable_btn(self.btn_extract)
        self._update_summary()

    def _start_visualization(self):
        self._disable_btn(self.btn_viz)
        self._progress_start()
        self._log("正在生成可视化图表...")

        def run():
            t0 = time.time()
            try:
                from visualizer_gui import generate_all_charts, logger as viz_logger

                # 带缓存的日志处理器, 捕获 visualizer logger 的输出
                log_lines = []
                class LogCapture(logging.Handler):
                    def emit(self, record):
                        msg = self.format(record)
                        if msg.strip():
                            log_lines.append(msg.strip())
                cap_handler = LogCapture()
                cap_handler.setFormatter(logging.Formatter("%(message)s"))
                originally_handlers = viz_logger.handlers[:]
                originally_propagate = viz_logger.propagate
                viz_logger.handlers = [cap_handler]
                viz_logger.propagate = False

                paths = generate_all_charts(state.articles, state.all_entities,
                                            state.all_triples, state.output_dir)

                # 恢复
                viz_logger.handlers = originally_handlers
                viz_logger.propagate = originally_propagate

                for ln in log_lines:
                    self._log(ln)
                state.cached_images = paths
            except Exception as ex:
                self._log(f"可视化失败: {ex}", "err")
                self._viz_done({}, time.time() - t0)
                return
            self._viz_done(paths, time.time() - t0)

        threading.Thread(target=run, daemon=True).start()

    def _viz_done(self, paths, elapsed):
        self._progress_stop()
        if paths:
            self._log(f"可视化完成 (耗时 {elapsed:.1f}s)", "ok")
            self.root.after(0, lambda: self.status_var.set("可视化就绪"))
            first = list(paths.values())[0] if paths else None
            self.root.after(0, lambda: self._show_preview(first))
            # 将完整分析报告存入 state 并显示
            analysis_text = paths.get("analysis_text", "")
            if analysis_text:
                state._analysis_text = analysis_text
                self.root.after(0, lambda: self._show_full_analysis(analysis_text))
            else:
                self.root.after(0, lambda: self._show_analysis_for(self.preview_var.get()))
        self._enable_btn(self.btn_viz)
        self._update_summary()

    def _show_preview(self, path):
        self.preview.delete("all")
        self._orig_img = None
        self._zoom_level = 1.0
        self._zoom_pan_x = 0
        self._zoom_pan_y = 0
        w = self.preview.winfo_width() if self.preview.winfo_width() > 100 else 400
        h = self.preview.winfo_height() if self.preview.winfo_height() > 100 else 300
        cx, cy = w // 2, h // 2
        if not path:
            self.preview.create_text(cx, cy, text="请先生成图表",
                                     font=("Microsoft YaHei", 14), fill=C["text3"])
            return
        if not os.path.exists(path):
            self.preview.create_text(cx, cy,
                                     text=f"文件不存在:\n{os.path.basename(path)}",
                                     font=("Microsoft YaHei", 12), fill=C["danger"])
            self._log(f"预览文件不存在: {path}", "err")
            return
        try:
            img = Image.open(path)
            self._orig_img = img
            self._zoom_level = 1.0
            self._render_zoom()
        except Exception as e:
            self._log(f"预览失败: {e}", "err")
            self.preview.create_text(cx, cy,
                                     text=f"预览失败:\n{str(e)[:50]}",
                                     font=("Microsoft YaHei", 12), fill=C["danger"])

    def _render_zoom(self):
        self.preview.delete("all")
        if not self._orig_img:
            return
        cw = self.preview.winfo_width()
        ch = self.preview.winfo_height()
        if cw < 20 or ch < 20:
            cw, ch = 800, 600
        iw, ih = self._orig_img.size
        base_scale = min((cw - 20) / iw, (ch - 20) / ih, 1.0)
        scale = base_scale * self._zoom_level
        nw = max(1, int(iw * scale))
        nh = max(1, int(ih * scale))
        display = self._orig_img.resize((nw, nh), Image.Resampling.LANCZOS)
        cx = cw // 2 + self._zoom_pan_x
        cy = ch // 2 + self._zoom_pan_y
        self._photo = ImageTk.PhotoImage(display)
        self.preview.create_image(cx, cy, image=self._photo, anchor=tk.CENTER, tags="img")
        pct = int(self._zoom_level * 100)
        self._zoom_percent_id = self.preview.create_text(
            cw - 10, 10, text=f"{pct}%", anchor=tk.NE,
            font=("Microsoft YaHei", 9), fill=C["text3"])

    def _on_zoom_wheel(self, e):
        if not self._orig_img:
            return
        delta = e.delta if hasattr(e, 'delta') else 0
        factor = 1.15 if delta > 0 else 0.87
        self._zoom_level = max(0.1, min(20.0, self._zoom_level * factor))
        self._render_zoom()

    def _on_zoom_reset(self, e):
        if not self._orig_img:
            return
        self._zoom_level = 1.0
        self._zoom_pan_x = 0
        self._zoom_pan_y = 0
        self._render_zoom()

    def _on_zoom_rightclick(self, e):
        if not self._orig_img:
            return
        cur_val = self.preview_var.get()
        src = state.cached_images.get(cur_val)
        if src and os.path.exists(src):
            os.startfile(src)

    def _on_zoom_drag_start(self, e):
        if not self._orig_img or self._zoom_level <= 1.05:
            return
        self._zoom_dragging = True
        self._zoom_drag_start = (e.x_root, e.y_root)
        self.preview.config(cursor="fleur")

    def _on_zoom_drag_move(self, e):
        if not self._zoom_dragging or not self._zoom_drag_start:
            return
        dx = e.x_root - self._zoom_drag_start[0]
        dy = e.y_root - self._zoom_drag_start[1]
        self._zoom_pan_x += dx
        self._zoom_pan_y += dy
        self._zoom_drag_start = (e.x_root, e.y_root)
        self._render_zoom()

    def _on_zoom_drag_end(self, e):
        self._zoom_dragging = False
        self._zoom_drag_start = None
        self.preview.config(cursor="crosshair")

    def _export_image(self, key):
        src = state.cached_images.get(key)
        if not src or not os.path.exists(src):
            messagebox.showwarning("提示", "请先生成图表")
            return
        names = {
            "wordcloud_corpus": ("词云图", "wordcloud_corpus.png"),
            "wordclouds_per_article": ("单篇词云子图", "wordclouds_per_article.png"),
            "knowledge_graph": ("知识图谱", "knowledge_graph.png"),
            "entity_count_bar": ("实体统计", "entity_count_bar.png"),
            "entity_top10": ("实体Top10", "entity_top10.png"),
            "event_verbs": ("事件动词", "event_verbs.png"),
            "cooccurrence": ("共现矩阵", "cooccurrence_heatmap.png"),
        }
        label, fn = names.get(key, (key, f"{key}.png"))
        dest = filedialog.asksaveasfilename(
            title=f"导出 - {label}",
            defaultextension=".png",
            filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")],
            initialfile=fn,
            initialdir=os.path.expanduser("~\\Desktop"),
        )
        if dest:
            shutil.copy2(src, dest)
            self._log(f"已导出 {label} \u2192 {dest}", "ok")
            messagebox.showinfo("导出成功", f"{label}\n已保存到:\n{dest}")

    def _export_all(self):
        if not state.cached_images:
            messagebox.showwarning("提示", "请先生成图表")
            return
        d = filedialog.askdirectory(title="选择导出目录", initialdir=os.path.expanduser("~\\Desktop"))
        if not d:
            return
        cnt = 0
        for k, src in state.cached_images.items():
            if src and os.path.exists(src):
                shutil.copy2(src, os.path.join(d, os.path.basename(src)))
                cnt += 1
        self._log(f"批量导出 {cnt} 张 \u2192 {d}", "ok")
        messagebox.showinfo("导出成功", f"已导出 {cnt} 张图片到:\n{d}")

    def _open_output_dir(self):
        os.startfile(state.output_dir)

    def _update_summary(self):
        lines = [f"新闻文章  {len(state.articles)} 篇"]
        if state.all_triples:
            lines.append(f"三元组    {len(state.all_triples)} 条")
        if state.all_entities:
            persons, locs, orgs, events = set(), set(), set(), set()
            for e in state.all_entities:
                persons.update(e.get("persons", []))
                locs.update(e.get("locations", []))
                orgs.update(e.get("organizations", []))
                events.update(e.get("events", []))
            lines.append(f"人物 {len(persons)} \u00b7 地点 {len(locs)} \u00b7 机构 {len(orgs)} \u00b7 动词 {len(events)}")
        self.root.after(0, lambda: self._set_summary("\n".join(lines)))

    def _set_summary(self, text):
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, text)
        self.summary_text.config(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()


def main():
    App().run()


if __name__ == "__main__":
    main()
