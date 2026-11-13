"""
实体识别与事件抽取模块 - v2

改进:
1. 扩充自定义词典, 避免常见人名/地名被切碎
2. 优化人名提取规则: 位置上下文+词性双重验证
3. 精简三元组抽取: 更严格的规则减少噪音
"""

import re
import os
from collections import Counter
import jieba
import jieba.posseg as pseg

class EntityExtractor:
    """新闻实体抽取器"""

    # ─── 扩充词典 ───
    CUSTOM_WORDS = [
        # 领导人/常见人名
        "习近平", "李克强", "李强", "王沪宁", "赵乐际", "丁薛祥", "李希", "蔡奇",
        "何立峰", "林武", "周乃翔", "王毅", "秦刚", "布林肯", "普京", "拜登",
        "特朗普", "马斯克", "库克", "黄仁勋", "雷军", "马云", "马化腾",
        "任正非", "张一鸣", "王传福", "曾毓群", "李彦宏", "周鸿祎",
        "刘强东", "董明珠", "俞敏洪",
        # 国际人名
        "马特维延科", "马克龙", "朔尔茨", "特拉斯", "苏纳克", "古特雷斯",
        "冯德莱恩", "拉夫罗夫", "佩洛西", "哈里斯",
        "内塔尼亚胡", "埃尔多安", "莫迪", 
        # 地名
        "山东省", "德州市", "陵城区", "长三角", "大湾区", "京津冀", "粤港澳",
        "深圳", "广州", "杭州", "成都", "武汉", "南京", "重庆", "西安",
        # 机构
        "中共中央", "国务院", "全国人大", "全国政协", "中央军委",
        "国家发展改革委", "发改委", "商务部", "财政部", "外交部", "教育部",
        "科学技术部", "工业和信息化部", "工信部", "交通运输部",
        "中国人民银行", "人民银行", "银保监会", "证监会",
        "新华社", "人民日报", "中央电视台",
        "中国式现代化", "高质量发展", "新质生产力", "乡村振兴",
        "碳达峰", "碳中和", "人工智能", "大数据", "区块链",
        "一带一路", "人类命运共同体",
    ]
    for w in CUSTOM_WORDS:
        jieba.add_word(w)

    # 中国常见姓氏 (单姓 + 复姓前缀)
    SURNAMES_SINGLE = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张"
        "孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎"
        "鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤"
        "滕殷罗毕郝邬安常乐于时傅皮下齐康伍余元卜顾孟平黄"
        "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞"
        "熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭"
        "梅盛林刁锺徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫"
        "经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚"
        "程嵇邢滑裴陆荣翁荀羊於惠甄麴家封芮羿储靳汲邴糜松"
        "井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫"
        "宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄"
        "印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴欎胥能苍双"
        "闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍卻璩桑桂濮牛寿通"
        "边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容"
        "向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东"
        "欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空"
        "曾毋沙乜养鞠须丰巢关蒯相查後荆红游竺权逯盖益桓公")

    SURNAMES_COMPOUND = {"万俟", "司马", "上官", "欧阳", "夏侯", "诸葛", "闻人", "东方",
        "赫连", "皇甫", "尉迟", "公羊", "澹台", "公冶", "宗政", "濮阳",
        "淳于", "单于", "太叔", "申屠", "公孙", "仲孙", "轩辕", "令狐",
        "锺离", "宇文", "长孙", "慕容", "鲜于", "闾丘", "司徒", "司空",
        "丌官", "司寇", "仉督", "子车", "颛孙", "端木", "巫马", "公西",
        "漆雕", "乐正", "壤驷", "公良", "拓拔", "夹谷", "宰父", "谷梁",
        "段干", "百里", "东郭", "南门", "呼延", "归海", "羊舌", "微生",
        "梁丘", "左丘", "东门", "西门", "商牟", "佘佴", "伯赏", "南宫",
        "墨哈", "谯笪", "第五", "言福"}

    ALL_SURNAMES = SURNAMES_SINGLE | SURNAMES_COMPOUND

    # 组织机构关键词
    ORG_KEYWORDS = [
        "公司", "集团", "银行", "基金", "证券", "保险", "大学", "",
        "研究所", "研究院", "中心", "委员会", "办公室", "部委",
        "协会", "商会", "联盟", "组织", "医院", "实践室", "平台",
        "央行", "国务院", "商务部", "财政部", "外交部", "卫健委",
        "证监会", "银保监会", "发改委", "工信部", "科技部", "教育部",
        "人民日报", "新华社", "中央电视台", "央视", "卫视",
        "部", "局", "厅", "委", "办",
    ]

    # 国家/地区
    COUNTRY_NAMES = {
        "中国", "美国", "日本", "韩国", "英国", "法国", "德国", "俄罗斯",
        "印度", "巴西", "加拿大", "澳大利亚", "意大利", "西班牙", "荷兰",
        "瑞士", "瑞典", "新加坡", "马来西亚", "泰国", "越南", "菲律宾",
        "印度尼西亚", "巴基斯坦", "沙特", "阿联酋", "土耳其", "伊朗",
        "朝鲜", "乌克兰", "波兰", "墨西哥", "阿根廷", "南非", "埃及",
        "台湾", "香港", "澳门", "欧盟", "北约", "东盟",
    }

    def __init__(self):
        pass

    # ─── 实体提取 ───

    def extract_persons(self, words_with_pos: list) -> list:
        """从分词结果中提取人名 (nr标签 + 姓氏规则双重验证)"""
        persons = set()

        # 方法1: jieba词性标注 nr (最可靠)
        for word, pos in words_with_pos:
            if pos == "nr" and 2 <= len(word) <= 4:
                if not word.isdigit() and word not in self.COUNTRY_NAMES:
                    skip_chars = {"和", "时", "下", "要", "在", "的", "上", "中", "各"}
                    skip_words = {"全局", "关系", "农业", "成色", "强调", "农村", "现代化",
                                 "总书记", "书记", "省长", "市长", "部长", "主任", "主席",
                                 "中国式", "高质量", "发展", "建设", "推进", "推动",
                                 "山东省委", "河北省委", "河南省委", "山西省委", "江苏省委",
                                 "伊朗", "谷歌", "高通", "百度", "联想", "华为", "小米", "OPPO",
                                 "苹果", "三星", "英伟达", "AMD", "英特尔", "特斯拉", "微软",
                                 "亚马逊", "Meta", "台积电", "比亚迪",
                                 # nr 误标词
                                 "东曹", "乌军", "乌干达", "伊朗核", "保持警惕",
                                 "养老金", "博客", "刚刚开始", "利弗莫", "华振", "华泰",
                                 "卡皮", "卡维", "占领军", "左翼", "关于", "总体",
                                 "下一代", "上市", "国内", "万桶", "关闭",
                                 "宣布", "公布", "发布", "报称", "报道", "共有", "削弱", "并称",}
                    skip_suffixes = {"委", "省委", "市委", "省", "市", "县", "区"}
                    if (not any(c in word for c in skip_chars)
                        and word not in skip_words
                        and not any(word.endswith(s) for s in skip_suffixes)):
                        persons.add(word)

        # 方法2: 上下文+结构验证 (仅当符合严格条件时补充人名)
        name_signals = {"说", "称", "表示", "指出", "认为", "透露",
                       "会见", "出席", "主持", "视察",
                       "接受", "回应", "警告", "批评", "称赞", "感谢"}
        name_suffix_blacklist = {
            "省", "市", "县", "区", "镇", "乡", "村", "路", "街", "道",
            "局", "系", "面", "度", "性", "化", "点", "力", "法", "率",
            "值", "线", "品", "体", "型", "业", "权", "量", "质", "数",
            "器", "机", "件", "片", "能", "感", "统", "态", "制", "步",
            "色", "产", "费", "选", "会", "长", "方", "间", "命", "名",
            "工作", "服务", "管理", "技术", "网络", "经济", "教育", "医疗",
            "项目", "领域", "环境", "产业", "市场", "企业", "金融", "文化",
            "社会", "科学", "研究", "活动", "安全", "体系", "系统", "工程",
            "机制", "模式", "目标", "任务", "方案", "战略", "政策", "政策",
            "组织", "机构", "平台", "中心", "小组", "大会", "论坛",
        }
        # 姓氏法额外黑名单 (常见误标: 公司/动词/量词以姓氏开头)
        surname_blacklist = {
            "伊朗", "关闭", "万桶", "宣布", "公布", "发布", "报称", "报道",
            "公司", "谷歌", "高通", "百度", "联想", "华为", "小米", "苹果",
            "三星", "英伟达", "英特尔", "特斯拉", "微软", "亚马逊",
            "台积电", "比亚迪", "腾讯", "阿里", "阿里巴巴",
            "关系", "发展", "建设", "推进", "推动", "促进",
            "加强", "加快", "提高", "增强", "全面", "深入", "重点", "大力",
            "充分", "切实", "持续", "不断", "进一步", "严格", "认真",
            "统筹", "健全", "完善", "强化", "深化", "优化", "扩大",
            "抓紧", "抓好", "确保", "保障", "履行", "落实", "部署",
            "安排", "投放", "投入", "支持", "参与", "参加",
            "考察", "调研", "陪同", "强调", "指出", "讲话", "致辞",
            "考察时", "考察调研", "调研时", "出席会议", "主持会议",
            "上市", "国内", "左翼", "养老金", "博客", "下一代",
            "保持警惕", "刚刚开始", "关于", "总体",
            "山东省", "河北省", "河南省", "山西省", "江苏省", "浙江省",
            "安徽省", "福建省", "江西省", "湖北省", "湖南省", "广东省",
            "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "辽宁省",
            "吉林省", "黑龙江省", "海南省", "青海省", "台湾省",
            "北京市", "上海市", "天津市", "重庆市",
            "深圳市", "广州市", "杭州市", "成都市", "武汉市", "南京市",
            "济南市", "青岛市", "大连市", "厦门市",
            "山东省委", "河北省委", "河南省委", "山西省委", "江苏省委",
            "新华社", "人民日报", "中国式", "高质量", "现代化",
        }
        text = "".join(w for w, p in words_with_pos)
        for word, pos in words_with_pos:
            if pos == "nr" and len(word) <= 4:
                continue
            if len(word) < 2 or re.search(r'[0-9a-zA-Z]', word):
                continue
            if word in self.COUNTRY_NAMES or word in surname_blacklist:
                continue
            if word[:2] in self.SURNAMES_COMPOUND:
                if not any(word.endswith(s) for s in name_suffix_blacklist):
                    persons.add(word)
                continue
            if word[0] in self.SURNAMES_SINGLE:
                if any(word.endswith(s) for s in name_suffix_blacklist):
                    continue
                idx = text.find(word)
                if idx == -1:
                    continue
                context_start = max(0, idx - 3)
                context_end = min(len(text), idx + len(word) + 8)
                context = text[context_start:context_end]
                if any(signal in context for signal in name_signals):
                    persons.add(word)

        return sorted(persons)

    def extract_locations(self, words_with_pos: list) -> list:
        """提取地名"""
        locations = set()
        for word, pos in words_with_pos:
            if pos == "ns" and len(word) >= 2:
                if word not in self.COUNTRY_NAMES:
                    locations.add(word)

        # 后缀匹配补充
        text = " ".join(w for w, _ in words_with_pos)
        loc_pattern = re.compile(
            r'([\u4e00-\u9fff]{2,8}(?:省|市|县|区|镇|乡|村|街道|新区|高新区|开发区|自贸区))'
        )
        for m in loc_pattern.finditer(text):
            locations.add(m.group(1))

        return sorted(locations)

    def extract_organizations(self, words_with_pos: list) -> list:
        """提取组织机构 (去重叠)"""
        raw_matches = []  # (start_pos, end_pos, name)
        text = " ".join(w for w, _ in words_with_pos)

        # 先收集所有匹配, 记录起止位置
        sorted_kw = sorted(self.ORG_KEYWORDS, key=len, reverse=True)
        for kw in sorted_kw:
            pattern = re.compile(rf'([\u4e00-\u9fff]{{2,12}}{re.escape(kw)})')
            for m in pattern.finditer(text):
                raw_matches.append((m.start(), m.end(), m.group(1)))

        # 去重叠: 按长度降序排序, 跳过被更长匹配包含的
        raw_matches.sort(key=lambda x: -(x[1] - x[0]))
        covered = set()
        orgs = set()
        for start, end, name in raw_matches:
            if any(a <= start and b >= end for a, b in covered):
                continue
            covered.add((start, end))
            orgs.add(name)

        # jieba nt 标注补充
        for word, pos in words_with_pos:
            if pos == "nt" and len(word) >= 3:
                orgs.add(word)

        return sorted(orgs)

    def extract_countries(self, words_with_pos: list) -> list:
        found = set()
        for word, _ in words_with_pos:
            if word in self.COUNTRY_NAMES:
                found.add(word)
        return sorted(found)

    def extract_events(self, words_with_pos: list) -> list:
        """提取事件动词 (v标签, 排除无意义的)"""
        event_verbs = set()
        skip = {"是", "有", "在", "为", "到", "让", "说", "会", "要", "能",
                "来", "去", "想", "看", "做", "用", "对", "和", "与", "及",
                "上", "下", "中", "大", "小", "多", "少", "等", "种", "个",
                "没有", "就是", "可以", "可能", "该", "将", "被", "把", "从",
                "给", "向", "以", "当", "因", "比", "过", "出", "还", "只",
                "又", "再", "已", "都", "最", "更", "很", "也", "只", "才",
                "就", "但", "却", "这", "那", "其", "之", "而", "或", "且",
                "使", "如", "所", "可", "并", "着", "得", "地", "的", "吗",
                "吧", "呢", "啊", "呀", "嘛", "哈", "哦", "嗯", "哟",
                "具有", "认为", "表示", "显示", "成为", "实现",
                "位于", "包括", "涉及", "达到", "超过", "发生",
                # 新闻程式化动词
                "强调", "指出", "考察", "调研", "视察", "陪同", "出席",
                "主持", "会见", "致辞", "发表", "介绍", "汇报",
                "了解", "听取", "要求", "希望", "提出", "讲话",
                "看望", "参观", "观摩", "调研时", "考察时", "强调指出",
                "要求指出", "提出要求", "主持会议", "出席会议",
                # 分析/抽象动词
                "深入", "全面", "重点", "大力", "充分", "切实",
                "加快", "促进", "推动", "推进", "提高", "增强",
                "加强", "加大", "抓紧", "抓好", "确保",
                "搞好", "用好", "管好",
                # 泛用动词
                "进行", "予以", "加以", "使用", "利用", "采用",
                "采取", "展开", "开展", "执行", "实施", "贯彻",
                "落实", "配合", "支持", "参与", "参加",
                # 非事件动词: 新闻常用语/状态描述/泛指词
                "宣布", "公布", "发布", "报道", "关注", "存在", "相关",
                "称", "称将", "表示", "认为", "显示", "成为", "实现",
                "包括", "涉及", "达到", "超过", "发生",
                "计划", "预计", "预期", "预计将", "继续", "正在",
                "已", "已经", "正在", "此前", "目前", "随后",
                "说明", "意味着", "反映出", "表明", "证明",
                "需要", "应该", "必须", "应当",
                "开始", "结束", "完成", "通过", "决定",
                "根据", "按照", "截至", "其中",
                "增长", "下降", "上涨", "下跌", "收跌", "收涨",
                "同比", "环比", "增幅", "降幅"}
        for word, pos in words_with_pos:
            if pos == "v" and len(word) >= 2:
                if word not in skip:
                    event_verbs.add(word)
        return sorted(event_verbs)

    def extract_times(self, text: str) -> list:
        """提取时间表达式"""
        times = set()
        patterns = [
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{1,2}月\d{1,2}日',
            r'\d{4}年',
            r'[一二三四五六七八九十]+月[一二三四五六七八九十]+日',
        ]
        for pat in patterns:
            for m in re.findall(pat, text):
                times.add(m)
        return sorted(times)

    # ─── 分词入口 ───

    def process(self, text: str) -> dict:
        """对一段文本进行完整的实体抽取"""
        text = re.sub(r'[\s]+', ' ', text).strip()
        if not text:
            return {}

        words_with_pos = list(pseg.cut(text))
        words = [w for w, p in words_with_pos if len(w.strip()) >= 2 and p != "x"]

        word_freq = Counter(w for w in words if len(w) >= 2)

        return {
            "persons": self.extract_persons(words_with_pos),
            "locations": self.extract_locations(words_with_pos),
            "organizations": self.extract_organizations(words_with_pos),
            "countries": self.extract_countries(words_with_pos),
            "events": self.extract_events(words_with_pos),
            "times": self.extract_times(text),
            "word_freq": word_freq.most_common(30),
        }

    # ─── 三元组抽取 ───

    def extract_triples(self, text: str, entities: dict) -> list:
        """
        从文本中抽取 (主体, 谓词/关系, 客体) 三元组
        关系类型:
          - 人物-动作-地点: 习近平 考察 山东德州
          - 人物-动作-机构: 习近平 视察 中共中央
          - 机构-位于-地点: 中共中央 位于 北京
          - 国家/地区-涉及-地点
        """
        triples = []
        sentences = re.split(r'[。！？\n；…]', text)

        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:
                continue

            # 获取该句中出现的实体
            sent_persons = [p for p in entities.get("persons", []) if p in sent]
            sent_locs = [l for l in entities.get("locations", []) if l in sent]
            sent_orgs = [o for o in entities.get("organizations", []) if o in sent]
            sent_countries = [c for c in entities.get("countries", []) if c in sent]
            sent_events = [e for e in entities.get("events", []) if e in sent]
            sent_times = [t for t in entities.get("times", []) if t in sent]

            # 规则1: 人物-事件-地点/机构 (按位置顺序)
            for person in sent_persons:
                pos_p = sent.find(person)
                for event in sent_events:
                    pos_e = sent.find(event)
                    if pos_p < pos_e < pos_p + 30:
                        for loc in sent_locs:
                            pos_l = sent.find(loc)
                            if pos_e < pos_l < pos_p + 40:
                                triples.append((person, event, loc))
                        for org in sent_orgs:
                            pos_o = sent.find(org)
                            if pos_e < pos_o < pos_p + 40:
                                triples.append((person, event, org))

            # 规则2: 人物-任职-机构
            for person in sent_persons:
                for org in sent_orgs:
                    if person != org:
                        dist = abs(sent.find(person) - sent.find(org))
                        if dist < 25:
                            triples.append((person, "任职于", org))

            # 规则3: 机构-位于-地点
            for org in sent_orgs:
                for loc in sent_locs:
                    if org != loc and loc in sent[sent.find(org) + len(org):]:
                        triples.append((org, "位于", loc))

            # 规则4: 人物-事件-时间
            for person in sent_persons:
                pos_p = sent.find(person)
                for event in sent_events:
                    pos_e = sent.find(event)
                    if pos_p < pos_e < pos_p + 30:
                        for t in sent_times:
                            if sent.find(t) > pos_e:
                                triples.append((person, event, t))

            # 规则5: 国家-涉及-地点
            for c1 in sent_countries:
                for loc in sent_locs:
                    triples.append((c1, "涉及", loc))

        # 去重
        seen = set()
        unique = []
        for t in triples:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        return unique

if __name__ == "__main__":
    extractor = EntityExtractor()
    test_text = (
        "中共中央总书记习近平24日在山东省德州市考察时强调，"
        "农业农村现代化关系中国式现代化全局和成色。"
        "习近平在山东省委书记林武和省长周乃翔陪同下考察调研。"
    )
    result = extractor.process(test_text)
    print("=== 实体抽取结果 ===")
    for key, val in result.items():
        if key != "word_freq":
            print(f"  {key}: {val}")
    print(f"  keywords (top15): {[w for w, _ in result['word_freq'][:15]]}")
    print()

    triples = extractor.extract_triples(test_text, result)
    print(f"=== 三元组 ({len(triples)} 条) ===")
    for s, p, o in triples[:15]:
        print(f"  ({s}) --[{p}]--> ({o})")
