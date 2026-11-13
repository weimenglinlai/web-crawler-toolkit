"""
GUI 可视化模块 - 为 GUI 提供图表生成服务

与 visualizer.py 功能相同, 但:
1. 返回所有生成的图片路径字典 (供 GUI 预览/导出)
2. 不自动保存到固定文件 (由 GUI 决定是否导出)
"""

import os
import re
import sys
from collections import Counter
import jieba

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from wordcloud import WordCloud
from PIL import Image, ImageDraw, ImageFont
import networkx as nx
import random as _random
import numpy as np

from config import FONT_PATH, FONT_PROP, STOP_WORDS, SEMANTIC_COLORS, \
    PERSON_FALSE, LOC_FALSE, JIEBA_NR_FALSE_POSITIVES, find_chinese_font

import logging
logger = logging.getLogger(__name__)


# 各图表生成函数
def _gen_wordcloud_corpus(articles: list, output_dir: str, entities: list = None) -> str:
    """全文词云图"""
    all_text = " ".join(a.get("content", "") for a in articles)
    path = os.path.join(output_dir, "wordcloud_corpus.png")
    _generate_wordcloud(all_text, path, "全部新闻词云图", entities=entities)
    return path


def _gen_wordcloud_per_article(articles: list, output_dir: str, entities: list = None) -> str:
    """单篇新闻词云子图 - PIL直接生成并拼合为网格"""
    entity_sets = _build_entity_sets(entities) if entities else _empty_entity_sets()

    n = min(len(articles), 9)
    cols = 3
    rows = (n + cols - 1) // cols
    cell_w, cell_h = 440, 320
    title_h = 24
    gap = 12
    margin = 25

    canvas_w = margin * 2 + cols * cell_w + (cols - 1) * gap
    canvas_h = margin * 2 + rows * (cell_h + title_h) + (rows - 1) * gap

    canvas = Image.new("RGB", (canvas_w, canvas_h), "#ffffff")

    # 尝试多个系统字体路径确保中文标题正常显示
    try:
        if FONT_PATH and os.path.exists(FONT_PATH):
            title_font = ImageFont.truetype(FONT_PATH, 11)
        else:
            font_candidates = [
                "./data",
                "./data",
                "./data",
                "./data",
                "/System/Library/Fonts/PingFang.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            ]
            chosen = None
            for fp in font_candidates:
                if os.path.exists(fp):
                    chosen = fp
                    break
            title_font = ImageFont.truetype(chosen, 11) if chosen else ImageFont.load_default()
    except Exception:
        title_font = ImageFont.load_default()

    for i in range(n):
        row = i // cols
        col = i % cols
        x = margin + col * (cell_w + gap)
        y_base = margin + row * (cell_h + title_h + gap)

        text = articles[i].get("content", "")
        wc_img = _render_single_wc(text, cell_w, cell_h, entity_sets)
        if wc_img:
            canvas.paste(wc_img, (x, y_base))

        draw = ImageDraw.Draw(canvas)
        title = articles[i].get("title", f"新闻{i + 1}")
        if len(title) > 22:
            title = title[:20] + "\u2026"
        draw.text((x + 4, y_base + cell_h + 4), title, fill="#333333", font=title_font)

    path = os.path.join(output_dir, "wordclouds_per_article.png")
    canvas.save(path, optimize=True, quality=95)
    logger.info(f"  [词云子图] 已保存: {path} ({n}篇)")
    return path


def _gen_knowledge_graph(triples: list, output_dir: str, entities: list = None) -> str:
    """知识图谱网络图 — 根据实体列表动态着色"""
    G = nx.DiGraph()

    edge_count = Counter()
    for s, p, o in triples:
        edge_count[(s, o, p)] += 1

    top_edges = edge_count.most_common(80)
    for (s, o, p), weight in top_edges:
        G.add_edge(s, o, label=p, weight=weight)

    if G.number_of_nodes() == 0:
        logger.info("  [知识图谱] 无三元组可绘制")
        return ""

    # 从 entity 列表构建分类集合
    entity_sets = _build_entity_sets(entities) if entities else _empty_entity_sets()

    fig, ax = plt.subplots(figsize=(20, 16))
    pos = nx.spring_layout(G, k=2.8, iterations=100, seed=42)

    # 着色: persons=红, locations=绿, organizations=蓝, events=紫, 其余灰
    COLOR_PERSONS = "#e74c3c"
    COLOR_LOCS = "#27ae60"
    COLOR_ORGS = "#2980b9"
    COLOR_EVENTS = "#8e44ad"
    COLOR_OTHER = "#bdc3c7"

    node_colors = []
    for node in G.nodes():
        if node in entity_sets["persons"]:
            node_colors.append(COLOR_PERSONS)
        elif node in entity_sets["locations"]:
            node_colors.append(COLOR_LOCS)
        elif node in entity_sets["organizations"]:
            node_colors.append(COLOR_ORGS)
        elif node in entity_sets["events"]:
            node_colors.append(COLOR_EVENTS)
        else:
            node_colors.append(COLOR_OTHER)

    nx.draw_networkx_nodes(G, pos, node_size=1200, node_color=node_colors,
                           alpha=0.9, ax=ax, edgecolors="#333", linewidths=0.8)
    nx.draw_networkx_edges(G, pos, edge_color="#999999", alpha=0.6,
                           arrows=True, arrowsize=16, width=1.2,
                           connectionstyle="arc3,rad=0.1", ax=ax)

    if FONT_PROP:
        labels = {n: n for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, font_size=11,
                                font_family=FONT_PROP.get_name(), ax=ax)
    else:
        nx.draw_networkx_labels(G, pos, font_size=11, ax=ax)

    edge_labels = {(u, v): d["label"] for u, v, d in G.edges(data=True)}
    if FONT_PROP:
        nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=9,
                                     font_family=FONT_PROP.get_name(),
                                     alpha=0.8, ax=ax)
    else:
        nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=9, alpha=0.8, ax=ax)

    ax.set_title("新闻事件知识图谱", fontproperties=FONT_PROP, fontsize=16, pad=20)
    ax.axis("off")

    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_PERSONS,
                    markersize=12, label='人物', markeredgecolor='#333', markeredgewidth=0.5),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_LOCS,
                    markersize=12, label='地点', markeredgecolor='#333', markeredgewidth=0.5),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_ORGS,
                    markersize=12, label='机构', markeredgecolor='#333', markeredgewidth=0.5),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_EVENTS,
                    markersize=12, label='事件', markeredgecolor='#333', markeredgewidth=0.5),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_OTHER,
                    markersize=12, label='其他', markeredgecolor='#333', markeredgewidth=0.5),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10,
              prop=FONT_PROP if FONT_PROP else None,
              framealpha=0.9, edgecolor='#ccc')

    plt.tight_layout()
    path = os.path.join(output_dir, "knowledge_graph.png")
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"  [知识图谱] 已保存: {path} (节点: {G.number_of_nodes()}, 边: {G.number_of_edges()})")
    return path


def _gen_entity_charts(all_entities: list, output_dir: str) -> dict:
    """实体统计图, 返回 {key: path}"""
    # 误标过滤集合
    total = {"persons": Counter(), "locations": Counter(),
             "organizations": Counter(), "countries": Counter(),
             "events": Counter()}
    for ent in all_entities:
        for key in total:
            for item in ent.get(key, []):
                if key == "persons" and item in PERSON_FALSE:
                    continue
                if key == "locations" and item in LOC_FALSE:
                    continue
                total[key][item] += 1

    results = {}

    # 图1: 各类实体数量柱状图
    fig, ax = plt.subplots(figsize=(10, 6))
    categories = list(total.keys())
    counts = [len(total[k]) for k in categories]
    labels_cn = ["人物", "地点", "机构", "国家", "事件动词"]
    bars = ax.bar(labels_cn, counts, width=0.6, color="#87CEEB", edgecolor="#555", linewidth=0.5)
    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(count), ha='center', fontsize=11, fontproperties=FONT_PROP)
    ax.set_ylabel("去重数量", fontproperties=FONT_PROP, fontsize=12)
    ax.set_title("各类实体数量统计", fontproperties=FONT_PROP, fontsize=14)
    if FONT_PROP:
        for item in ax.get_xticklabels() + ax.get_yticklabels():
            item.set_fontproperties(FONT_PROP)
    plt.tight_layout()
    p = os.path.join(output_dir, "entity_count_bar.png")
    fig.savefig(p, dpi=100, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    results["entity_count_bar"] = p
    logger.info(f"  [实体统计] 已保存: {p}")

    # 图2: Top 10 人物 / 地点 / 机构 (带数值标签)
    fig, axes = plt.subplots(1, 3, figsize=(18, 8))
    for ax_item, (key, title_cn) in zip(axes, [
        ("persons", "Top 10 人物"),
        ("locations", "Top 10 地点"),
        ("organizations", "Top 10 机构"),
    ]):
        items = total[key].most_common(10)
        if not items:
            ax_item.axis("off")
            continue
        names, values = zip(*reversed(items))
        bars = ax_item.barh(names, values, height=0.6, color="#98FB98", edgecolor="#555", linewidth=0.5)
        for bar, val in zip(bars, values):
            ax_item.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                        str(val), ha='left', va='center', fontsize=9, fontproperties=FONT_PROP)
        ax_item.set_title(title_cn, fontproperties=FONT_PROP, fontsize=12)
        if FONT_PROP:
            for item in ax_item.get_xticklabels() + ax_item.get_yticklabels():
                item.set_fontproperties(FONT_PROP)
    plt.tight_layout()
    p = os.path.join(output_dir, "entity_top10.png")
    fig.savefig(p, dpi=100, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    results["entity_top10"] = p
    logger.info(f"  [实体Top10] 已保存: {p}")

    # 图3: 事件动词 Top 15 (带数值标签)
    fig, ax_item = plt.subplots(figsize=(12, 7))
    items = total["events"].most_common(15)
    if items:
        names, values = zip(*reversed(items))
        bars = ax_item.barh(names, values, height=0.7, color="#FFB6C1", edgecolor="#555", linewidth=0.5)
        for bar, val in zip(bars, values):
            ax_item.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                        str(val), ha='left', va='center', fontsize=9, fontproperties=FONT_PROP)
        ax_item.set_title("Top 15 事件动词", fontproperties=FONT_PROP, fontsize=14)
        if FONT_PROP:
            for item in ax_item.get_xticklabels() + ax_item.get_yticklabels():
                item.set_fontproperties(FONT_PROP)
    plt.tight_layout()
    p = os.path.join(output_dir, "event_verbs.png")
    fig.savefig(p, dpi=100, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    results["event_verbs"] = p
    logger.info(f"  [事件动词] 已保存: {p}")

    return results


def _gen_cooccurrence(entities: list, output_dir: str) -> str:
    """实体共现矩阵热力图 (前15个人物 x 前15个地点/机构)"""
    person_articles = {}
    org_articles = {}
    loc_articles = {}
    for i, ent in enumerate(entities):
        for p in ent.get("persons", []):
            if p in PERSON_FALSE:
                continue
            person_articles.setdefault(p, set()).add(i)
        for o in ent.get("organizations", []):
            org_articles.setdefault(o, set()).add(i)
        for l in ent.get("locations", []):
            if l in LOC_FALSE:
                continue
            loc_articles.setdefault(l, set()).add(i)

    # 选前15个人物和前15个地点/机构
    top_persons = sorted(person_articles.keys(),
                         key=lambda k: len(person_articles[k]), reverse=True)[:15]
    all_others = {**org_articles, **loc_articles}
    top_others = sorted(all_others.keys(),
                        key=lambda k: len(all_others[k]), reverse=True)[:15]

    if not top_persons or not top_others:
        logger.warning("  [共现矩阵] 数据不足")
        return ""

    # 计算共现矩阵
    matrix = np.zeros((len(top_persons), len(top_others)), dtype=int)
    for i, p in enumerate(top_persons):
        articles_p = person_articles.get(p, set())
        for j, o in enumerate(top_others):
            articles_o = all_others.get(o, set())
            matrix[i, j] = len(articles_p & articles_o)

    # 共现数 >= 1 才算有效
    total_co = matrix.sum()
    if total_co < 3:
        logger.warning(f"  [共现矩阵] 有效共现过少 ({int(total_co)}), 跳过")
        return ""

    fig, ax = plt.subplots(figsize=(14, max(6, len(top_persons) * 0.45)))
    max_val = matrix.max()
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto", vmin=0, vmax=max(max_val, 1))

    ax.set_xticks(range(len(top_others)))
    ax.set_yticks(range(len(top_persons)))
    ax.set_xticklabels(top_others, fontproperties=FONT_PROP, fontsize=7, rotation=40, ha="right")
    ax.set_yticklabels(top_persons, fontproperties=FONT_PROP, fontsize=8)

    # 只标注非零值
    for i in range(len(top_persons)):
        for j in range(len(top_others)):
            val = matrix[i, j]
            if val > 0:
                mid = max_val / 2 if max_val > 0 else 1
                color = "white" if val > mid else "#333"
                ax.text(j, i, str(val), ha="center", va="center",
                        fontsize=8, color=color, fontweight="bold")

    ax.set_title("人物-地点/机构共现矩阵", fontproperties=FONT_PROP, fontsize=14, pad=16)
    cbar = fig.colorbar(im, ax=ax, shrink=0.6, label="共现次数")
    plt.tight_layout()

    path = os.path.join(output_dir, "cooccurrence_heatmap.png")
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"  [共现矩阵] 已保存: {path} ({len(top_persons)}人 x {len(top_others)}实体)")
    return path



def _empty_entity_sets():
    """返回空的实体集合字典"""
    return {"persons": set(), "locations": set(), "organizations": set(), "events": set()}


def _build_entity_sets(entities: list) -> dict:
    """从实体列表构建查询集合 {persons, locations, organizations, events}
    包含清洗步骤: 将 jieba nr 误标的机构/通用词从 persons 移入正确类别"""
    result = {"persons": set(), "locations": set(), "organizations": set(), "events": set()}
    for ent in entities:
        for p in ent.get("persons", []):
            result["persons"].add(p)
        for l in ent.get("locations", []):
            result["locations"].add(l)
        for o in ent.get("organizations", []):
            result["organizations"].add(o)
        for e in ent.get("events", []):
            result["events"].add(e)

    # 清洗1: nr 误标词 — 归入 organizations 或直接删除
    for term in list(result["persons"]):
        if term in JIEBA_NR_FALSE_POSITIVES:
            result["persons"].discard(term)
            # 公司/品牌名归入 organizations
            company_keywords = {"公司", "谷歌", "高通", "百度", "联想", "华为", "小米",
                                "苹果", "三星", "英伟达", "英特尔", "特斯拉", "微软",
                                "亚马逊", "台积电", "比亚迪", "腾讯", "阿里", "阿里巴巴",
                                "OPPO", "vivo", "荣耀", "宁德时代", "OpenAI", "Meta"}
            if term in company_keywords:
                result["organizations"].add(term)

    # 清洗2: 同时出现在 persons & organizations 的词 → 归 organizations
    for term in list(result["persons"] & result["organizations"]):
        result["persons"].discard(term)

    # 清洗3: 同时出现在 persons & locations 的词 → 归 locations
    for term in list(result["persons"] & result["locations"]):
        result["persons"].discard(term)

    # 清洗4: 从 locations 中移除被误标的动词/通用词
    loc_false_positives = {"上市", "深度", "全面", "进一步"}
    for term in list(result["locations"]):
        if term in loc_false_positives:
            result["locations"].discard(term)
            result["events"].add(term)  # 归入 events

    return result


def _semantic_color_func(entity_sets: dict):
    """返回一个 color_func `callable(word, **kw) -> str` 用于 WordCloud"""

    persons      = entity_sets.get("persons", set())
    locations    = entity_sets.get("locations", set())
    organizations = entity_sets.get("organizations", set())
    events       = entity_sets.get("events", set())

    def _choose(word, font_size=None, position=None, orientation=None,
               random_state=None, font_path=None, **kw):
        if word in organizations:
            return _random.choice(SEMANTIC_COLORS["organization"])
        if word in locations:
            return _random.choice(SEMANTIC_COLORS["location"])
        if word in events:
            return _random.choice(SEMANTIC_COLORS["event"])
        if word in persons:
            return _random.choice(SEMANTIC_COLORS["person"])
        return _random.choice(SEMANTIC_COLORS["other"])

    return _choose


def _render_single_wc(text: str, width: int, height: int, entity_sets: dict) -> "Image.Image":
    """单篇词云小图, 返回 PIL Image, 失败返回 None"""
    words = jieba.cut(re.sub(r'[^\u4e00-\u9fff]', ' ', text))
    filtered = [w.strip() for w in words
                if len(w.strip()) >= 2
                and w.strip() not in STOP_WORDS
                and not w.strip().isdigit()]
    if not filtered:
        return None

    wc_kwargs = dict(
        width=width, height=height,
        background_color="#ffffff",
        max_words=50,
        max_font_size=50,
        min_font_size=12,
        prefer_horizontal=0.95,
        collocations=False,
        margin=18,
        relative_scaling=0.5,
        color_func=_semantic_color_func(entity_sets),
    )
    if FONT_PATH:
        wc_kwargs["font_path"] = FONT_PATH

    wc = WordCloud(**wc_kwargs)
    wc.generate_from_frequencies(dict(Counter(filtered).most_common(50)))
    return wc.to_image()


def _generate_wordcloud(text: str, output_path: str, title: str = "",
                        max_words: int = 120, entities: list = None):
    """生成语义着色词云图 - 1600x900, 统一微软雅黑字体, PIL直接输出"""
    words = jieba.cut(re.sub(r'[^\u4e00-\u9fff]', ' ', text))
    filtered = [w.strip() for w in words
                if len(w.strip()) >= 2
                and w.strip() not in STOP_WORDS
                and not w.strip().isdigit()]
    if not filtered:
        logger.warning(f"  [词云] 无有效词汇, 跳过: {title}")
        return

    word_freq = Counter(filtered)
    entity_sets = _build_entity_sets(entities) if entities else _empty_entity_sets()

    wc_kwargs = dict(
        width=1600, height=900,
        background_color="#ffffff",
        max_words=max_words,
        max_font_size=180,
        min_font_size=16,
        prefer_horizontal=0.95,
        collocations=False,
        margin=20,
        relative_scaling=0.5,
        color_func=_semantic_color_func(entity_sets),
    )
    if FONT_PATH:
        wc_kwargs["font_path"] = FONT_PATH

    wc = WordCloud(**wc_kwargs)
    wc.generate_from_frequencies(dict(word_freq.most_common(max_words)))

    img = wc.to_image()
    img.save(output_path, optimize=True, quality=95)
    logger.info(f"  [词云] 已保存: {output_path} (词数: {len(word_freq)})")


# 主入口: 生成全部图表, 返回路径字典
if __name__ == "__main__":
    logger.warning("这是 GUI 可视化模块, 请运行 gui_main.py 启动 GUI。")
    sys.exit(1)


def _build_analysis_text(articles: list, entities: list, triples: list, wordcloud_text: str) -> str:
    """根据分析结果生成新闻事件抽取结果描述文本"""
    n_articles = len(articles)

    # 统计实体 (带频次)
    person_freq = Counter()
    loc_freq = Counter()
    org_freq = Counter()
    event_freq = Counter()
    for ent in entities:
        for p in ent.get("persons", []):
            if p not in PERSON_FALSE:
                person_freq[p] += 1
        for l in ent.get("locations", []):
            if l not in LOC_FALSE:
                loc_freq[l] += 1
        for o in ent.get("organizations", []):
            org_freq[o] += 1
        for e in ent.get("events", []):
            event_freq[e] += 1

    n_persons = len(person_freq)
    n_locations = len(loc_freq)
    n_organizations = len(org_freq)
    n_events = len(event_freq)
    n_triples = len(triples)

    # Top 5 高频词
    words = jieba.cut(re.sub(r'[^\u4e00-\u9fff]', ' ', wordcloud_text))
    filtered = [w.strip() for w in words
                if len(w.strip()) >= 2
                and w.strip() not in STOP_WORDS
                and not w.strip().isdigit()]
    top5 = Counter(filtered).most_common(5)
    top5_str = "、".join(w for w, _ in top5) if top5 else "——"

    lines = [
        "=" * 50,
        "新闻事件抽取结果分析报告",
        "=" * 50,
        "",
        "【一、数据概览】",
        "本次分析共采集 {} 篇界面新闻报道。".format(n_articles),
        "通过 jieba 分词与实体识别，共提取：",
        "  - 人物实体 {} 个".format(n_persons),
        "  - 地点实体 {} 个".format(n_locations),
        "  - 机构实体 {} 个".format(n_organizations),
        "  - 事件动词 {} 个".format(n_events),
        "  - 实体关系三元组 {} 条".format(n_triples),
        "  - 语料高频词 Top5：{}".format(top5_str),
        "",
    ]

    # 核心人物
    if n_persons > 0:
        top5_p = person_freq.most_common(5)
        names_str = "、".join(name for name, _ in top5_p)
        lines.append("【二、核心人物】")
        lines.append("出现频次最高的人物：{}。".format(names_str))
        if top5_p[0][1] > 1:
            lines.append("其中「{}」出现 {} 次，为报道中出现最频繁的人物。".format(top5_p[0][0], top5_p[0][1]))
        lines.append("")

    # 主要地点
    if n_locations > 0:
        top5_l = loc_freq.most_common(5)
        names_str = "、".join(name for name, _ in top5_l)
        lines.append("【三、主要地点】")
        lines.append("报道涉及的主要地点：{}。".format(names_str))
        lines.append("")

    # 重要机构
    if n_organizations > 0:
        top5_o = org_freq.most_common(5)
        names_str = "、".join(name for name, _ in top5_o)
        lines.append("【四、重要机构】")
        lines.append("报道中提及的机构：{}。".format(names_str))
        lines.append("")

    # 关键事件动词
    if n_events > 0:
        top5_e = event_freq.most_common(5)
        names_str = "、".join(name for name, _ in top5_e)
        lines.append("【五、关键事件动词】")
        lines.append("高频事件动词：{}。".format(names_str))
        lines.append("这些动词反映了新闻报道中的核心动作与事件类型。")
        lines.append("")

    # 实体关系分析
    if n_triples > 0:
        rel_counter = Counter(rel for _, rel, _ in triples)
        top_rels = rel_counter.most_common(3)
        rel_str = "、".join("{}({}次)".format(r, c) for r, c in top_rels)
        lines.append("【六、实体关系分析】")
        lines.append("共构建 {} 条三元组，主要关系类型：{}。".format(n_triples, rel_str))
        # 提取部分典型三元组示例
        sample_triples = triples[:5]
        lines.append("典型三元组示例：")
        for s, r, o in sample_triples:
            lines.append("  ({}, {}, {})".format(s, r, o))
        lines.append("")

    # 词云分析
    lines.append("【七、词云分析】")
    if top5:
        lines.append("语料库中高频词汇为 {}，反映了当前新闻报道的主题倾向。".format(top5_str))
    lines.append("词云图中不同颜色代表不同实体类型：红色=人物、绿色=地点、蓝色=机构、紫色=事件、灰色=其他。")
    lines.append("")

    # 知识图谱分析
    lines.append("【八、知识图谱】")
    lines.append("知识图谱基于实体关系三元组构建，节点按类型着色（红=人物、绿=地点、蓝=机构、灰=其他）。")
    lines.append("图谱展示了新闻中人物、地点、机构之间的关联关系，核心枢纽节点反映了报道的关键实体。")
    lines.append("")

    # 共现矩阵分析
    lines.append("【九、共现矩阵】")
    lines.append("共现矩阵展示了高频人物与地点/机构在同一篇报道中共同出现的频次。")
    lines.append("颜色越深表示共现次数越多，反映了人物与地点/机构之间的关联强度。")
    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


def generate_all_charts(articles: list, entities: list, triples: list, output_dir: str) -> dict:
    """
    生成所有可视化图表, 返回 {chart_key: file_path, analysis_text: str} 字典
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    all_text = " ".join(a.get("content", "") for a in articles)

    logger.info("\n[1/6] 生成全文词云...")
    paths["wordcloud_corpus"] = _gen_wordcloud_corpus(articles, output_dir, entities)

    logger.info("\n[2/6] 生成单篇新闻词云子图...")
    paths["wordclouds_per_article"] = _gen_wordcloud_per_article(articles, output_dir, entities)

    logger.info("\n[3/6] 生成知识图谱网络图...")
    paths["knowledge_graph"] = _gen_knowledge_graph(triples, output_dir, entities)

    logger.info("\n[4/6] 生成实体统计图表...")
    chart_paths = _gen_entity_charts(entities, output_dir)
    paths.update(chart_paths)

    logger.info("\n[5/6] 生成实体共现矩阵热力图...")
    paths["cooccurrence"] = _gen_cooccurrence(entities, output_dir)

    logger.info("\n[6/6] 全部图表生成完成!")

    # 生成分析描述文本
    paths["analysis_text"] = _build_analysis_text(articles, entities, triples, all_text)

    return paths
