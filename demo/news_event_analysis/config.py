"""
配置模块 - 集中管理颜色、字体、停用词、误标过滤等配置
"""

import os
import json

# ─── 颜色主题 ───
C = {
    "bg":            "#f0f2f5",
    "card":          "#ffffff",
    "primary":       "#4f6ef7",
    "primary_hover": "#3b5de7",
    "primary_text":  "#ffffff",
    "success":       "#22c55e",
    "warning":       "#f59e0b",
    "danger":        "#ef4444",
    "text":          "#1e293b",
    "text2":         "#64748b",
    "text3":         "#94a3b8",
    "border":        "#e2e8f0",
    "input_bg":      "#f8fafc",
    "hover":         "#f1f5f9",
    "active":        "#eef2ff",
    "log_bg":        "#1e293b",
    "log_text":      "#e2e8f0",
    "canvas_bg":     "#fafafa",
}

# ─── 配置持久化 ───
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_config.json")

def load_config() -> dict:
    defaults = {"target_count": "120", "win_width": 1200, "win_height": 800}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults

def save_config(**kw):
    try:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg.update(kw)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ─── 字体配置 ───
def find_chinese_font():
    candidates = [
        "./data",
        "./data",
        "./data",
        "./data",
    ]
    for f in candidates:
        if os.path.exists(f):
            return f
    import matplotlib.font_manager as fm
    for font in fm.findSystemFonts():
        if any(k in font.lower() for k in ['msyh', 'simhei', 'simsun', 'yahei', 'songti']):
            return font
    return None

FONT_PATH = find_chinese_font()
FONT_PROP = None
if FONT_PATH:
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
    FONT_PROP = fm.FontProperties(fname=FONT_PATH)
    plt.rcParams["font.family"] = FONT_PROP.get_name()
    plt.rcParams["axes.unicode_minus"] = False

# ─── 停用词表 ───
STOP_WORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你
会 着 没有 看 好 自己 这 他 她 它 们 那 些 所 为 所以 因为 但是
然而 不过 可以 还是 只是 已经 并且 而且 吗 呢 吧 啊 哦 嗯 啦
被 把 从 让 对 与 等 及 或 其 将 以 之 而 于 则 又 能 能够
进行 开始 自己 什么 怎么 怎样 如何 如果 虽然 但是 不是 就是 这个
那个 这些 那些 其中 其他 以及 已经 需要 应该 可能 对于 关于
目前 现在 目前 今天 昨天 明天 之后 之前 以后 以前 以内 以外
方面 问题 情况 事情 作用 关系 影响 发展 变化 过程 结果 原因
表示 认为 指出 据悉 报道 消息 新闻 记者 编辑 来源 图片 视频
""".split())
for c in "0123456789０１２３４５６７８９":
    STOP_WORDS.add(c)

# ─── 误标过滤 ───
PERSON_FALSE = {"谷歌", "高通", "百度", "联想", "华为", "小米", "苹果",
                "三星", "英伟达", "英特尔", "特斯拉", "微软", "亚马逊",
                "台积电", "比亚迪", "腾讯", "阿里", "阿里巴巴",
                "OPPO", "vivo", "荣耀", "宁德时代", "OpenAI", "Meta",
                "伊朗", "关闭", "万桶", "宣布", "公布", "发布",
                "报称", "报道", "上市", "国内", "左翼", "养老金",
                "东曹", "乌军", "乌干达", "伊朗核", "保持警惕",
                "博客", "刚刚开始", "利弗莫", "华振", "华泰",
                "卡皮", "卡维", "占领军", "关于", "总体", "下一代"}

LOC_FALSE = {"上市", "深度", "全面", "进一步", "同比", "环比"}

# ─── 语义着色 ───
SEMANTIC_COLORS = {
    "person":       ["#DC143C", "#E53935", "#F44336", "#EF5350", "#FF1744"],
    "location":     ["#00897B", "#00BFA5", "#26A69A", "#4DB6AC", "#1DE9B6"],
    "organization": ["#1565C0", "#1E88E5", "#42A5F5", "#64B5F6", "#2979FF"],
    "event":        ["#6A1B9A", "#8E24AA", "#AB47BC", "#CE93D8", "#D500F9"],
    "other":        ["#546E7A", "#78909C", "#90A4AE", "#B0BEC5", "#CFD8DC"],
}

# ─── jieba nr 误标词 ───
JIEBA_NR_FALSE_POSITIVES = {
    "国家", "国务院", "全国人大", "全国政协", "中央", "中共中央",
    "省政府", "省委", "市委", "市政府", "县委", "县政府",
    "新华社", "人民日报", "央视", "中央台",
    "发改委", "商务部", "外交部", "财政部", "教育部", "科技部",
    "军委", "中央军委",
    "谷歌", "高通", "百度", "联想", "华为", "小米", "苹果",
    "三星", "英伟达", "英特尔", "特斯拉", "微软", "亚马逊",
    "台积电", "比亚迪", "腾讯", "阿里", "阿里巴巴", "Meta",
    "OPPO", "vivo", "荣耀", "宁德时代", "OpenAI",
    "宣布", "公布", "发布", "报称", "报道", "关闭", "共有",
    "削弱", "并称", "称将", "表示将",
    "万桶", "日桶", "亿吨", "万亿",
    "下一代", "保持警惕", "刚刚开始", "关于", "总体",
    "伊朗", "乌军", "乌干达", "左翼", "华振", "华泰",
    "养老金", "博客", "东曹", "利弗莫", "卡皮",
    "伊朗核", "上市", "国内",
}

# ─── App State ───
class AppState:
    def __init__(self):
        self.articles = []
        self.all_entities = []
        self.all_triples = []
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.cached_images = {}
