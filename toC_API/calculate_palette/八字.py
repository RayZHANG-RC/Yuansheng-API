# -*- coding: utf-8 -*-
import datetime
import json
import sys
import os
import argparse
try:
    from TungShing import TungShing
except Exception:
    try:
        from .TungShing import TungShing
    except Exception:
        raise ImportError("需要提供 TungShing.py 并安装其依赖（cnlunar、sxtwl）。")
from zoneinfo import ZoneInfo
try:
    import sxtwl as _sx
except Exception:
    _sx = None

from dateutil.relativedelta import relativedelta

from collections import Counter  # 文件顶部任意处只需引一次


# —— 全局常量 & 规则定义 etc. —— 
# 地支关系常量定义
DIZHI_RELATIONS = {
    # 六冲（互为对冲）
    '冲': {
        '子':'午','午':'子',
        '丑':'未','未':'丑',
        '寅':'申','申':'寅',
        '卯':'酉','酉':'卯',
        '辰':'戌','戌':'辰',
        '巳':'亥','亥':'巳'
    },
    # 六合（相合为吉）
    '合': {
        '子':'丑','丑':'子',
        '寅':'亥','亥':'寅',
        '卯':'戌','戌':'卯',
        '辰':'酉','酉':'辰',
        '巳':'申','申':'巳',
        '午':'未','未':'午'
    },
    # 三刑（无恩之刑 / 恃势之刑 / 无礼之刑 / 自刑）
    '刑': [
        ('寅','巳','申'),  # 三刑合成组
        ('丑','戌','未'),
        ('子','卯'),
        ('辰','辰'), ('午','午'), ('酉','酉'), ('亥','亥')
    ],
    # 六害（互相伤害）
    '害': {
        '子':'未','未':'子',
        '丑':'午','午':'丑',
        '寅':'巳','巳':'寅',
        '卯':'辰','辰':'卯',
        '申':'亥','亥':'申',
        '酉':'戌','戌':'酉'
    },
    # 三会（木 / 火 / 金 / 水 四局）
    '会': {
        '寅卯辰':'木',
        '巳午未':'火',
        '申酉戌':'金',
        '亥子丑':'水'
    },
    # 三合（申子辰→水，寅午戌→火，巳酉丑→金，亥卯未→木）
    '三合': {
        '申子辰':'水',
        '寅午戌':'火',
        '巳酉丑':'金',
        '亥卯未':'木'
    }
}

def get_relations(zhi_list):
    """
    分析一组地支中的：冲、合、刑、害、会、三合
    :param zhi_list: ['子','丑','寅','卯',…]
    :return: {
        '冲': [[...], …], 
        '合': [[...], …],
        '刑': [[...], …],
        '害': [[...], …],
        '会': [[支列表, 五行], …],
        '三合': [[支列表, 五行], …]
    }
    """
    zs = set(zhi_list)
    from collections import Counter
    counts = Counter(zhi_list)

    out = {k: [] for k in DIZHI_RELATIONS}

    # 冲
    seen = set()
    for z in zhi_list:
        if z in seen: continue
        partner = DIZHI_RELATIONS['冲'].get(z)
        if partner and partner in zs:
            out['冲'].append([z, partner])
            seen.add(partner)

    # 合
    seen.clear()
    for z in zhi_list:
        if z in seen: continue
        partner = DIZHI_RELATIONS['合'].get(z)
        if partner and partner in zs:
            out['合'].append([z, partner])
            seen.add(partner)

    # 刑（任意两两或三合型）

    # 刑（区分：三刑 / 互刑 / 自刑）
    # 1) 三刑：寅巳申、丑戌未 —— 任意两支同现即成立
    for trio in [('寅','巳','申'), ('丑','戌','未')]:
        hit = [z for z in trio if counts[z] > 0]
        if len(hit) >= 2:
            out['刑'].append(hit)

    # 2) 互刑：子卯互刑 —— 必须两支同时出现
    if counts['子'] > 0 and counts['卯'] > 0:
        out['刑'].append(['子','卯'])

    # 3) 自刑：辰/午/酉/亥 —— 必须同支出现“至少两次”才成立
    for same in ('辰','午','酉','亥'):
        if counts[same] >= 2:
            out['刑'].append([same, same])

    # 害
    seen.clear()
    for z in zhi_list:
        if z in seen: continue
        partner = DIZHI_RELATIONS['害'].get(z)
        if partner and partner in zs:
            out['害'].append([z, partner])
            seen.add(partner)

    # 会（含半会）
    for key, wx in DIZHI_RELATIONS['会'].items():
        # 整局
        if all(ch in zs for ch in key):
            out['会'].append([list(key), wx])
        else:
            # 半会：前两 或 后两
            for combo in (key[:2], key[1:]):
                if all(ch in zs for ch in combo):
                    out['会'].append([list(combo), wx + '局半会'])

    # 三合（含半合）
    for key, wx in DIZHI_RELATIONS['三合'].items():
        if all(ch in zs for ch in key):
            out['三合'].append([list(key), wx])
        else:
            for combo in (key[:2], key[1:]):
                if all(ch in zs for ch in combo):
                    out['三合'].append([list(combo), wx + '局半合'])

    return out



# 季节映射（用于四废等需要季节判断的规则）
SEASON_MAP = {
    '寅':'春', '卯':'春', '辰':'春',
    '巳':'夏', '午':'夏', '未':'夏',
    '申':'秋', '酉':'秋', '戌':'秋',
    '亥':'冬', '子':'冬', '丑':'冬'
}

# 三合局映射（用于驿马等规则）
TRINITY_GROUP = {
    '申子辰': {'马': '寅', '将星': '子', '华盖': '辰'},
    '寅午戌': {'马': '申', '将星': '午', '华盖': '戌'},
    '巳酉丑': {'马': '亥', '将星': '酉', '华盖': '丑'},
    '亥卯未': {'马': '巳', '将星': '卯', '华盖': '未'}
}

# 24节气名称数组（注意顺序应与黄经分段对应，这里“春分”为起始节气）
JIEQI = ["春分", "清明", "谷雨", "立夏", "小满", "芒种",
         "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
         "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
         "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰"]

# 仅用于“按节定月 / 起运取节”的索引集合（以本表“春分”为0起）
# 取：清明、立夏、小满、芒种、立秋、处暑、白露、立冬、小雪、大雪、小寒、立春
JIE_INDEXES_JIE = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23}



FULL_STEMS = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
FULL_BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
# 地支藏干映射
CANGGAN = {
    "子": ["癸"],      "丑": ["己","辛","癸"], "寅": ["甲","丙","戊"],
    "卯": ["乙"],      "辰": ["戊","癸","乙"], "巳": ["丙","庚","戊"],
    "午": ["丁","己"], "未": ["己","乙","丁"], "申": ["庚","壬","戊"],
    "酉": ["辛"],      "戌": ["戊","辛","丁"], "亥": ["壬","甲"],
}
# 天干对应五行
WUXING = {'甲':'木','乙':'木','丙':'火','丁':'火',
          '戊':'土','己':'土','庚':'金','辛':'金',
          '壬':'水','癸':'水'}
# 五行相生相克
SHENGKE = {
    '木': {'生': '火', '克': '土'},
    '火': {'生': '土', '克': '金'},
    '土': {'生': '金', '克': '水'},
    '金': {'生': '水', '克': '木'},
    '水': {'生': '木', '克': '火'}
}


NAYIN = {
    '甲子': '海中金', '乙丑': '海中金',
    '丙寅': '炉中火', '丁卯': '炉中火',
    '戊辰': '大林木', '己巳': '大林木',
    '庚午': '路旁土', '辛未': '路旁土',
    '壬申': '剑锋金', '癸酉': '剑锋金',
    '甲戌': '山头火', '乙亥': '山头火',
    '丙子': '涧下水', '丁丑': '涧下水',
    '戊寅': '城头土', '己卯': '城头土',
    '庚辰': '白蜡金', '辛巳': '白蜡金',
    '壬午': '杨柳木', '癸未': '杨柳木',
    '甲申': '泉中水', '乙酉': '泉中水',
    '丙戌': '屋上土', '丁亥': '屋上土',
    '戊子': '霹雳火', '己丑': '霹雳火',
    '庚寅': '松柏木', '辛卯': '松柏木',
    '壬辰': '长流水', '癸巳': '长流水',
    '甲午': '沙中金', '乙未': '沙中金',
    '丙申': '山下火', '丁酉': '山下火',
    '戊戌': '平地木', '己亥': '平地木',
    '庚子': '壁上土', '辛丑': '壁上土',
    '壬寅': '金箔金', '癸卯': '金箔金',
    '甲辰': '覆灯火', '乙巳': '覆灯火',
    '丙午': '天河水', '丁未': '天河水',
    '戊申': '大驿土', '己酉': '大驿土',
    '庚戌': '钗钏金', '辛亥': '钗钏金',
    '壬子': '桑柘木', '癸丑': '桑柘木',
    '甲寅': '大溪水', '乙卯': '大溪水',
    '丙辰': '沙中土', '丁巳': '沙中土',
    '戊午': '天上火', '己未': '天上火',
    '庚申': '石榴木', '辛酉': '石榴木',
    '壬戌': '大海水', '癸亥': '大海水'
}


# 十二长生
CHANGSHENG_STATES = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养']

CHANGSHENG_MAP = {
    '甲': {'亥': '长生', '子': '沐浴', '丑': '冠带', '寅': '临官', '卯': '帝旺', '辰': '衰', '巳': '病', '午': '死', '未': '墓', '申': '绝', '酉': '胎', '戌': '养'},
    '乙': {'午': '长生', '巳': '沐浴', '辰': '冠带', '卯': '临官', '寅': '帝旺', '丑': '衰', '子': '病', '亥': '死', '戌': '墓', '酉': '绝', '申': '胎', '未': '养'},
    '丙': {'寅': '长生', '卯': '沐浴', '辰': '冠带', '巳': '临官', '午': '帝旺', '未': '衰', '申': '病', '酉': '死', '戌': '墓', '亥': '绝', '子': '胎', '丑': '养'},
    '丁': {'酉': '长生', '申': '沐浴', '未': '冠带', '午': '临官', '巳': '帝旺', '辰': '衰', '卯': '病', '寅': '死', '丑': '墓', '子': '绝', '亥': '胎', '戌': '养'},
    '戊': {'寅': '长生', '卯': '沐浴', '辰': '冠带', '巳': '临官', '午': '帝旺', '未': '衰', '申': '病', '酉': '死', '戌': '墓', '亥': '绝', '子': '胎', '丑': '养'},
    '己': {'酉': '长生', '申': '沐浴', '未': '冠带', '午': '临官', '巳': '帝旺', '辰': '衰', '卯': '病', '寅': '死', '丑': '墓', '子': '绝', '亥': '胎', '戌': '养'},
    '庚': {'巳': '长生', '午': '沐浴', '未': '冠带', '申': '临官', '酉': '帝旺', '戌': '衰', '亥': '病', '子': '死', '丑': '墓', '寅': '绝', '卯': '胎', '辰': '养'},
    '辛': {'子': '长生', '亥': '沐浴', '戌': '冠带', '酉': '临官', '申': '帝旺', '未': '衰', '午': '病', '巳': '死', '辰': '墓', '卯': '绝', '寅': '胎', '丑': '养'},
    '壬': {'申': '长生', '酉': '沐浴', '戌': '冠带', '亥': '临官', '子': '帝旺', '丑': '衰', '寅': '病', '卯': '死', '辰': '墓', '巳': '绝', '午': '胎', '未': '养'},
    '癸': {'卯': '长生', '寅': '沐浴', '丑': '冠带', '子': '临官', '亥': '帝旺', '戌': '衰', '酉': '病', '申': '死', '未': '墓', '午': '绝', '巳': '胎', '辰': '养'},
}

# 标准旬空定义
XUNKONG_MAP = {
    '甲子': ['戌', '亥'], '乙丑': ['戌', '亥'], '丙寅': ['戌', '亥'], '丁卯': ['戌', '亥'], '戊辰': ['戌', '亥'],
    '己巳': ['戌', '亥'], '庚午': ['戌', '亥'], '辛未': ['戌', '亥'], '壬申': ['戌', '亥'], '癸酉': ['戌', '亥'],
    '甲戌': ['申', '酉'], '乙亥': ['申', '酉'], '丙子': ['申', '酉'], '丁丑': ['申', '酉'], '戊寅': ['申', '酉'],
    '己卯': ['申', '酉'], '庚辰': ['申', '酉'], '辛巳': ['申', '酉'], '壬午': ['申', '酉'], '癸未': ['申', '酉'],
    '甲申': ['午', '未'], '乙酉': ['午', '未'], '丙戌': ['午', '未'], '丁亥': ['午', '未'], '戊子': ['午', '未'],
    '己丑': ['午', '未'], '庚寅': ['午', '未'], '辛卯': ['午', '未'], '壬辰': ['午', '未'], '癸巳': ['午', '未'],
    '甲午': ['辰', '巳'], '乙未': ['辰', '巳'], '丙申': ['辰', '巳'], '丁酉': ['辰', '巳'], '戊戌': ['辰', '巳'],
    '己亥': ['辰', '巳'], '庚子': ['辰', '巳'], '辛丑': ['辰', '巳'], '壬寅': ['辰', '巳'], '癸卯': ['辰', '巳'],
    '甲辰': ['寅', '卯'], '乙巳': ['寅', '卯'], '丙午': ['寅', '卯'], '丁未': ['寅', '卯'], '戊申': ['寅', '卯'],
    '己酉': ['寅', '卯'], '庚戌': ['寅', '卯'], '辛亥': ['寅', '卯'], '壬子': ['寅', '卯'], '癸丑': ['寅', '卯'],
    '甲寅': ['子', '丑'], '乙卯': ['子', '丑'], '丙辰': ['子', '丑'], '丁巳': ['子', '丑'], '戊午': ['子', '丑'],
    '己未': ['子', '丑'], '庚申': ['子', '丑'], '辛酉': ['子', '丑'], '壬戌': ['子', '丑'], '癸亥': ['子', '丑'],
}

# —— 使用寿星天文历（sxtwl）高效查找“上一/下一节”（不含中气） —— #
JQMC = [
    "冬至","小寒","大寒","立春","雨水","惊蛰","春分","清明","谷雨",
    "立夏","小满","芒种","夏至","小暑","大暑","立秋","处暑","白露",
    "秋分","寒露","霜降","立冬","小雪","大雪"
]
_JIE_NAMES = {"立春","惊蛰","清明","立夏","芒种","小暑","立秋","白露","寒露","立冬","大雪","小寒"}

def _cn8_to_aware(y: int, m: int, d: int, h: int, mi: int, s: float) -> datetime.datetime:
    tz = ZoneInfo("Asia/Shanghai")
    whole = int(s)
    micro = int(round((s - whole) * 1_000_000))
    return datetime.datetime(y, m, d, h, mi, whole, micro, tzinfo=tz)

def _find_nearby_terms_by_sxtwl(dt: datetime.datetime):
    if _sx is None:
        raise ImportError("缺少 sxtwl，请安装寿星天文历：pip install sxtwl")
    tz = ZoneInfo("Asia/Shanghai")
    dt_local = dt if dt.tzinfo else dt.replace(tzinfo=tz)
    dt_local = dt_local.astimezone(tz)

    def cn8_from_jd(jd):
        t = _sx.JD2DD(jd)
        return _cn8_to_aware(int(t.Y), int(t.M), int(t.D), int(t.h), int(t.m), float(t.s))

    # 以当天为锚点
    base = _sx.fromSolar(dt_local.year, dt_local.month, dt_local.day)

    # 上一“节”（需要 <= dt_local）
    prev_info = None
    day = base
    for _ in range(370):
        if day.hasJieQi():
            name = JQMC[day.getJieQi()]
            if name in _JIE_NAMES:
                cn8 = cn8_from_jd(day.getJieQiJD())
                if cn8 <= dt_local:
                    prev_info = (name, cn8)
                    break
        day = day.before(1)  # 继续往前找

    # 下一“节”（需要 > dt_local）
    next_info = None
    day = base
    for _ in range(370):
        if day.hasJieQi():
            name = JQMC[day.getJieQi()]
            if name in _JIE_NAMES:
                cn8 = cn8_from_jd(day.getJieQiJD())
                if cn8 > dt_local:
                    next_info = (name, cn8)
                    break
        day = day.after(1)   # 继续往后找

    return prev_info, next_info

def get_nearby_solar_terms(dt):
    """返回最近的上一“节”和下一“节”（不含中气），北京时间。"""
    prev_info, next_info = _find_nearby_terms_by_sxtwl(dt)
    if not prev_info and not next_info:
        return json.dumps({"previous": None, "next": None}, ensure_ascii=False)
    def to_dict(name: str, t: datetime.datetime):
        return {
            "name": name,
            "year": t.year,
            "month": t.month,
            "day": t.day,
            "hour": t.hour,
            "minute": t.minute,
            "second": round(t.second + t.microsecond/1_000_000, 1)
        }
    previous = to_dict(*prev_info) if prev_info else None
    next_term = to_dict(*next_info) if next_info else None
    return json.dumps({"previous": previous, "next": next_term}, ensure_ascii=False)

def get_shishen(day_gan: str, target_gan: str) -> str:
    """
    计算两个天干之间的十神关系：依据五行生克与阴阳判定十神。
    """
    # 五行关系
    me = WUXING[day_gan]
    other = WUXING[target_gan]
    if other == me:
        relation = "同我"
    elif SHENGKE[me]['生'] == other:
        relation = "我生"
    elif SHENGKE[me]['克'] == other:
        relation = "我克"
    elif SHENGKE[other]['生'] == me:
        relation = "生我"
    else:
        relation = "克我"
    # 阴阳同/异
    parity = (FULL_STEMS.index(day_gan) % 2) == (FULL_STEMS.index(target_gan) % 2)

    # 对应十神映射
    if relation == "同我":
        return "比肩" if parity else "劫财"
    if relation == "我生":
        return "食神" if parity else "伤官"
    if relation == "生我":
        return "偏印" if parity else "正印"
    if relation == "我克":
        return "偏财" if parity else "正财"
    # 克我
    return "七杀" if parity else "正官"



# —— 神煞规则函数 —— 

# 1. 天乙贵人 —— 《星平会海》：“甲戊庚·牛羊，乙己·鼠猴，丙丁·猪鸡，壬癸·兔蛇，辛·马虎。”
#def rule_tian_yi_guiren(*, day_gan, pillar_zhi, **kwargs):
def rule_tian_yi_guiren(**kwargs):
    """天乙贵人（甲戊庚牛羊，乙己鼠猴乡）"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '甲': ['丑','未'], '戊': ['丑','未'], '庚': ['丑','未'],
        '乙': ['子','申'], '己': ['子','申'],
        '丙': ['亥','酉'], '丁': ['亥','酉'],
        '壬': ['卯','巳'], '癸': ['卯','巳'],
        '辛': ['午','寅']
    }
    return pillar_zhi in mapping.get(day_gan, [])

# 2. 太极贵人 —— 《渊海子平》：“甲乙子午，丙丁卯酉，戊己亥辰，庚辛寅亥，壬癸巳申全见。”
def rule_tai_ji_guiren(**kwargs):
    """太极贵人（戊己四季辰戌丑未）"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        ('甲','乙'): ['子','午'],
        ('丙','丁'): ['卯','酉'],
        ('戊','己'): ['辰','戌','丑','未'],  # 扩展四季地支
        ('庚','辛'): ['寅','亥'],
        ('壬','癸'): ['巳','申'],
    }
    return any(day_gan in stems and pillar_zhi in zs
               for stems, zs in mapping.items())

# 3. 天德贵人 —— 《星平会海》：“正月丁，二月申，三月壬…十二月庚。”
def rule_tian_de_guiren(**kwargs):
    """天德贵人：按月支→指定天干判定（常用口径）"""
    month_branch = kwargs.get('month_branch')
    pillar_gan   = kwargs.get('pillar_gan')
    mapping = {
        '寅':'丁','卯':'壬','辰':'癸','巳':'甲','午':'乙','未':'丙',
        '申':'丁','酉':'庚','戌':'辛','亥':'壬','子':'癸','丑':'甲'
    }
    return pillar_gan == mapping.get(month_branch)


# 4. 月德贵人 —— 《星平会海》：“寅午戌→丙，申子辰→壬，亥卯未→甲，巳酉丑→庚。”
def rule_yue_de_guiren(**kwargs):
    """月德贵人"""
    month_branch = kwargs.get('month_branch')
    pillar_gan   = kwargs.get('pillar_gan')
    mapping = {
        ('寅','午','戌'): '丙',
        ('申','子','辰'): '壬',
        ('亥','卯','未'): '甲',
        ('巳','酉','丑'): '庚',
    }
    return any(month_branch in grp and pillar_gan == g
               for grp, g in mapping.items())

# 5. 三奇贵人 —— 《渊海子平》：“天上三奇甲戌庚，地下乙丙丁，人中壬癸辛”。
# 5. 三奇贵人 - 需验证顺布条件（《渊海子平》）
# 5. 三奇贵人 —— 修正顺布条件验证
def rule_san_qi(
    *, 
    bazi_pillars,
    **kwargs
):
    """
    《渊海子平》三奇贵人规则：
    1. 天上三奇：甲戊庚必须年、月、日或月、日、时顺次出现
    2. 地下三奇：乙丙丁必须年、月、日或月、日、时顺次出现 
    3. 人中三奇：壬癸辛必须年、月、日或月、日、时顺次出现
    """
    # 获取四柱天干列表（年、月、日、时）
    bazi = kwargs.get('bazi_pillars', {})
    stems = [bazi.get(p, ('', ''))[0] for p in ('year','month','day','hour')]
    
    # 天上三奇检查（甲戊庚）
    for i in range(2):
        if stems[i:i+3] == ['甲','戊','庚']:
            return True
    
    # 地下三奇检查（乙丙丁）
    for i in range(2):
        if stems[i:i+3] == ['乙','丙','丁']:
            return True
    
    # 人中三奇检查（壬癸辛）
    for i in range(2):
        if stems[i:i+3] == ['壬','癸','辛']:
            return True
    
    return False

# 6. 文昌贵人 —— 《果老星宗》：“甲乙见巳午，丙戊见申，丁己见酉，庚见亥，辛见戌，壬见寅，癸见卯。”
def rule_wenchang(**kwargs):
    """文昌贵人"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '甲':'巳', '乙':'午', '丙':'申', '丁':'酉', 
        '戊':'申', '己':'酉', '庚':'亥', '辛':'子',
        '壬':'寅', '癸':'卯'
    }
    return pillar_zhi == mapping.get(day_gan)

# 7. 魁罡贵人 —— “壬辰、庚戌、庚辰、戊戌”。
def rule_kui_gang(**kwargs):
    """魁罡贵人（《三命通会》：庚辰、壬辰、戊戌、庚戌四日）"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    return (day_gan + pillar_zhi) in ('壬辰','庚戌','庚辰','戊戌')

# 8. 国印贵人 —— 果老星宗：“禄前第九位”。
def rule_guo_yin(**kwargs):
    """国印贵人（禄前第九位改为禄顺行九位）《三命通会》：甲禄在寅，前九位为戌）"""
    
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    lu_map = {'甲':'寅','乙':'卯','丙':'巳','丁':'午',
              '戊':'巳','己':'午','庚':'申','辛':'酉',
              '壬':'亥','癸':'子'}
    start = lu_map.get(day_gan)
    if not start: return False
    idx = FULL_BRANCHES.index(start)
    target = FULL_BRANCHES[(idx + 9) % 12]
    return pillar_zhi == target

# 9. 学堂 —— “金见巳，木见亥，水见申，土（火）见寅”。
def rule_xuetang(**kwargs):
    """学堂"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    wx = WUXING[day_gan]
    mapping = {'金':'巳','木':'亥','水':'申','土':'寅','火':'寅'}
    return pillar_zhi == mapping.get(wx)

# 10. 词馆 —— “金见申，木见子，水见午，土见丑，火见酉”。
def rule_ciguan(**kwargs):
    """词馆"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    wx = WUXING[day_gan]
    mapping = {'金':'申','木':'子','水':'午','土':'丑','火':'酉'}
    return pillar_zhi == mapping.get(wx)

# 11. 驿马 —— 《渊海子平》诀：申子辰→寅，寅午戌→申，巳酉丑→亥，亥卯未→巳。歌诀：“申子辰马在寅，寅午戌马在申，巳酉丑马在亥，亥卯未马在巳” 
def rule_yima(**kwargs):
    """驿马"""
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        ('申','子','辰'): '寅',
        ('寅','午','戌'): '申',
        ('巳','酉','丑'): '亥',
        ('亥','卯','未'): '巳',
    }
    return any(day_zhi in grp and pillar_zhi == v
               for grp, v in mapping.items())


# 12. 华盖 —— 神峰通考：“寅午戌→戌，亥卯未→未，申子辰→辰，巳酉丑→丑”。 歌诀：“寅午戌生见戌，亥卯未生见未，申子辰生见辰，巳酉丑生见丑”
def rule_huagai(**kwargs):
    """华盖"""
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        ('寅','午','戌'): '戌',
        ('亥','卯','未'): '未',
        ('申','子','辰'): '辰',
        ('巳','酉','丑'): '丑',
    }
    return any(day_zhi in grp and pillar_zhi == v
               for grp, v in mapping.items())


# 13. 将星 —— 神峰通考：“寅午戌→午，申子辰→子，巳酉丑→酉，亥卯未→卯”。 歌诀：“寅午戌见午，巳酉丑见酉，申子辰见子，辛卯未见卯”
def rule_jiang_xing(**kwargs):
    """将星（需日支在三合局中）"""
    day_zhi = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    for grp, data in TRINITY_GROUP.items():
        if day_zhi in grp:
            return pillar_zhi == data['将星']
    return False


# 14. 金舆 —— 紫虚：“禄前二辰号金舆”。 原法：取日主禄神所在地支，向前两位即得金舆地支
def rule_jin_yu(**kwargs):
    # 日主禄神地支映射
    """金舆"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    lu_map = {'甲':'寅','乙':'卯','丙':'巳','丁':'午',
              '戊':'巳','己':'午','庚':'申','辛':'酉',
              '壬':'亥','癸':'子'}
    start = lu_map.get(day_gan)
    if not start: return False
    idx = FULL_BRANCHES.index(start)
    target = FULL_BRANCHES[(idx - 2) % 12]
    return pillar_zhi == target


# 15. 金神 —— “乙丑、己巳、癸酉”。
def rule_jin_shen(**kwargs):
    """金神"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    return (day_gan + pillar_zhi) in ('乙丑','己巳','癸酉')

# 16. 天医 —— “月后一个支”。修正后的天医星（月支前一位）
def rule_tian_yi(**kwargs):
    """天医（以月支前一位）"""
    month_branch = kwargs.get('month_branch')
    pillar_zhi   = kwargs.get('pillar_zhi')
    idx = (FULL_BRANCHES.index(month_branch) - 1) % 12  # 改为减1
    return pillar_zhi == FULL_BRANCHES[idx]

# 17. 禄神 —— “日主临官之地”。
def rule_lu_shen(**kwargs):
    """禄神"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    return CHANGSHENG_MAP.get(day_gan, {}).get(pillar_zhi) == '临官'

# 18. 拱禄 —— “日主+时支合拱禄”。补充全部十组（《三命通会》）
def rule_gong_lu(**kwargs):
    """拱禄（五日拱禄）"""
    day_gan    = kwargs.get('day_gan')
    day_zhi    = kwargs.get('day_zhi')
    hour_zhi   = kwargs.get('hour_zhi')
    # 五日拱禄特殊组合
    combos = {
        '癸': {'亥':'丑', '丑':'亥'},  # 癸亥+癸丑拱子
        '丁': {'巳':'未'},           # 丁巳+丁未拱午
        '己': {'未':'巳'},           # 己未+己巳拱午
        '戊': {'午':'辰'},           # 戊午+戊辰拱巳
    }
    # 检查日时组合是否形成拱禄
    if day_gan in combos:
        valid_zhi = combos[day_gan]
        if day_zhi in valid_zhi:
            return hour_zhi == valid_zhi[day_zhi]
    return False

# 19. 天赦 —— “春戊寅、夏甲午、秋戊申、冬甲子”。歌诀：春寅卯辰见戊寅，夏巳午未见甲午，秋申酉戌见戊申，冬亥子丑见甲子
def rule_tian_she(**kwargs):
    """天赦"""
    month_branch = kwargs.get('month_branch')
    pillar_gan   = kwargs.get('pillar_gan')
    pillar_zhi   = kwargs.get('pillar_zhi')
    seasons = {
        ('寅','卯','辰'): ('戊','寅'),
        ('巳','午','未'): ('甲','午'),
        ('申','酉','戌'): ('戊','申'),
        ('亥','子','丑'): ('甲','子'),
    }
    return any(month_branch in grp and
               (pillar_gan, pillar_zhi) == pair
               for grp, pair in seasons.items())


# 20. 天罗地网 —— “辰为天罗、戌为地网”。
def rule_tian_luo_di_wang(**kwargs):
    """天罗地网"""
    pillar_zhi = kwargs.get('pillar_zhi')
    return pillar_zhi in ('辰','戌')

# 21. 羊刃 —— 禄前一位为刃（甲禄在寅，卯为羊刃）
def rule_yang_ren(**kwargs):
    """羊刃（《三命通会》：禄前一位为刃）"""
    '''
    《三命通会》卷七：

    "甲刃在卯，乙刃在辰，丙戊刃在午，丁己刃在未，庚刃在酉，辛刃在戌，壬刃在子，癸刃在丑"
    
    《渊海子平》论羊刃：
    
    "甲刃卯，乙刃辰，丙戊刃午，丁己刃未，庚刃酉，辛刃戌，壬刃子，癸刃丑"
    '''
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    # 禄位映射（甲禄在寅...癸禄在子）
    lu_map = {'甲':'寅','乙':'卯','丙':'巳','丁':'午',
              '戊':'巳','己':'午','庚':'申','辛':'酉',
              '壬':'亥','癸':'子'}
    # 羊刃为禄位顺行一位
    lu_zhi = lu_map.get(day_gan)
    if not lu_zhi: return False
    idx = FULL_BRANCHES.index(lu_zhi)
    yang_ren_zhi = FULL_BRANCHES[(idx + 1) % 12]  # 禄位+1即羊刃
    return pillar_zhi == yang_ren_zhi


# 22. 亡神 —— “寅午戌→巳，巳酉丑→申，申子辰→亥，亥卯未→寅”。
def rule_wang_shen(**kwargs):
    """亡神"""
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        ('寅','午','戌'):'巳',
        ('巳','酉','丑'):'申',
        ('申','子','辰'):'亥',
        ('亥','卯','未'):'寅',
    }
    return any(day_zhi in grp and pillar_zhi == v
               for grp, v in mapping.items())

# 23. 劫煞 —— “寅午戌→亥，亥卯未→申，申子辰→巳，巳酉丑→寅”。
def rule_jie_sha(**kwargs):
    """劫煞"""
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        ('寅','午','戌'):'亥',
        ('亥','卯','未'):'申',
        ('申','子','辰'):'巳',
        ('巳','酉','丑'):'寅',
    }
    return any(day_zhi in grp and pillar_zhi == v
               for grp, v in mapping.items())

# 24. 灾煞 —— “冲将星”：
# 寅午戌将星午→冲子；申子辰将星子→冲午；巳酉丑将星酉→冲卯；亥卯未将星卯→冲酉。
def rule_zai_sha(**kwargs):
    """灾煞"""
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        ('寅','午','戌'):'子',
        ('申','子','辰'):'午',
        ('巳','酉','丑'):'卯',
        ('亥','卯','未'):'酉',
    }
    return any(day_zhi in grp and pillar_zhi == v
               for grp, v in mapping.items())

# 25. 勾绞煞 —— 小儿关煞之一，因地支而论（此处示例，仅保留原逻辑）。
def rule_gou_jiao(**kwargs):
    """勾绞煞"""
    gender      = kwargs.get('gender')
    year_branch = kwargs.get('year_branch')
    return (gender=='male'   and year_branch in ('子','丑','寅')) \
       or (gender=='female' and year_branch in ('辰','巳','午'))

# 26. 孤辰寡宿 —— 《三命通会》：“亥子丑进位寅→孤，退位戌→寡；其余依此推”。
def rule_gu_chan(**kwargs):
    """孤辰寡宿"""
    month_branch = kwargs.get('month_branch')
    pillar_zhi   = kwargs.get('pillar_zhi')
    mapping = {
        '亥子丑': ('寅','戌'), '寅卯辰': ('巳','丑'),
        '巳午未': ('申','辰'), '申酉戌': ('亥','未')
    }
    for grp, (gu, gua) in mapping.items():
        if month_branch in grp:
            return pillar_zhi in (gu, gua)
    return False

# 27. 元辰 —— “阳男阴女取冲年支前一支；阴男阳女取后一支”。
def rule_yuan_cheng(**kwargs):
    """元辰"""
    gender      = kwargs.get('gender')
    year_branch = kwargs.get('year_branch')
    pillar_zhi  = kwargs.get('pillar_zhi')
    male_map = {'子':'未','丑':'申','寅':'酉','卯':'戌','辰':'亥',
                '巳':'子','午':'丑','未':'寅','申':'卯','酉':'辰','戌':'巳','亥':'午'}
    female_map = {v:k for k,v in male_map.items()}
    return pillar_zhi == (male_map if gender=='male' else female_map)[year_branch]

# 28. 空亡 —— 用旬空表 XUNKONG_MAP 判断。
def rule_kong_wang(**kwargs):
    """空亡"""
    day_gan    = kwargs.get('day_gan')
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    return pillar_zhi in XUNKONG_MAP.get(day_gan+day_zhi, [])

# 29. 十恶大败 —— “甲辰乙巳丙申丁亥戊戌己丑庚辰辛巳壬申癸亥”。
def rule_shi_e(**kwargs):
    """十恶大败"""
    day_gan    = kwargs.get('day_gan')
    day_zhi    = kwargs.get('day_zhi')
    return (day_gan + day_zhi) in [
        '甲辰','乙巳','丙申','丁亥','戊戌',
        '己丑','庚辰','辛巳','壬申','癸亥'
    ]

# 30. 咸池（桃花） —— “寅午戌→卯，申子辰→酉，巳酉丑→午，亥卯未→子”。
def rule_xian_chi(**kwargs):
    """咸池/桃花"""
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        ('寅','午','戌'):'卯',
        ('申','子','辰'):'酉',
        ('巳','酉','丑'):'午',
        ('亥','卯','未'):'子',
    }
    return any(day_zhi in grp and pillar_zhi == v
               for grp, v in mapping.items())

# 31. 孤鸾煞 —— “乙巳丁巳辛亥戊申壬寅戊午壬子丙午（加丙午）”。
def rule_gu_luan(**kwargs):
    """《三命通会》乙巳、丁巳、辛亥等日"""
    day_gan = kwargs.get('day_gan')
    day_zhi = kwargs.get('day_zhi')
    return (day_gan + day_zhi) in [
        '乙巳','丁巳','辛亥','戊申',
        '壬寅','戊午','壬子','丙午'
    ]

# 32. 阴阳差错 —— “丙子丁丑戊寅辛卯壬辰癸巳丙午丁未戊申辛酉壬戌癸亥”。
def rule_yin_yang(**kwargs):
    """阴阳差错"""
    day_gan    = kwargs.get('day_gan')
    day_zhi    = kwargs.get('day_zhi')
    return (day_gan + day_zhi) in [
        '丙子','丁丑','戊寅','辛卯','壬辰','癸巳',
        '丙午','丁未','戊申','辛酉','壬戌','癸亥'
    ]

# 33. 四废 —— “庚申辛酉→春；壬子癸亥→夏；甲寅乙卯→秋；丙午丁未→冬”。增加季节判断（《三命通会》）
def rule_si_fei(**kwargs):
    """四废"""
    day_gan      = kwargs.get('day_gan')
    day_zhi      = kwargs.get('day_zhi')
    month_branch = kwargs.get('month_branch')
    season_map = {
        ('寅','卯','辰'): ['庚申','辛酉'],
        ('巳','午','未'): ['壬子','癸亥'],
        ('申','酉','戌'): ['甲寅','乙卯'],
        ('亥','子','丑'): ['丙午','丁未']
    }
    for grp, gz in season_map.items():
        if month_branch in grp:
            return (day_gan + day_zhi) in gz
    return False

# 34. 六厄（《三命通会》）
def rule_liu_e(**kwargs):
    """六厄（按日支所属三合局定唯一宫位）"""
    day_zhi    = kwargs.get('day_zhi')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {'申子辰':'卯','寅午戌':'酉','巳酉丑':'子','亥卯未':'午'}
    group = next((k for k in mapping if day_zhi in k), None)
    if not group:
        return False
    return pillar_zhi == mapping[group]

# 35. 披麻（《渊海子平》）
def rule_pi_ma(**kwargs):
    """披麻"""
    year_branch = kwargs.get('year_branch')
    pillar_zhi  = kwargs.get('pillar_zhi')
    groups = {
        '子':'卯','丑':'卯','寅':'巳','卯':'巳','辰':'申','巳':'申',
        '午':'亥','未':'亥','申':'寅','酉':'寅','戌':'巳','亥':'巳'
    }
    return pillar_zhi == groups.get(year_branch)

# 36. 隔角（《神峰通考》）
def rule_ge_jiao(**kwargs):
    """隔角"""
    day_zhi    = kwargs.get('day_zhi')
    hour_zhi   = kwargs.get('hour_zhi')
    idx = FULL_BRANCHES.index(day_zhi)
    return hour_zhi == FULL_BRANCHES[(idx + 2) % 12]

# 37. 血刃（《果老星宗》）
def rule_xue_ren(**kwargs):
    """血刃"""
    day_zhi      = kwargs.get('day_zhi')
    month_branch = kwargs.get('month_branch')
    mapping = {
        '子':'戌','丑':'酉','寅':'申','卯':'未','辰':'午','巳':'巳',
        '午':'辰','未':'卯','申':'寅','酉':'丑','戌':'子','亥':'亥'
    }
    return day_zhi == mapping.get(month_branch)

# 丧门吊客映射表（年支→丧门地支）
SANGMEN_MAP = {'子':'寅','丑':'卯','寅':'辰','卯':'巳','辰':'午','巳':'未',
               '午':'申','未':'酉','申':'戌','酉':'亥','戌':'子','亥':'丑'}

# 38. 丧门（《三命通会》）
def rule_sang_men(**kwargs):
    """丧门"""
    year_branch = kwargs.get('year_branch')
    pillar_zhi  = kwargs.get('pillar_zhi')
    return pillar_zhi == SANGMEN_MAP.get(year_branch)

# 39. 吊客（《三命通会》）
def rule_diao_ke(**kwargs):
    """吊客"""
    year_branch = kwargs.get('year_branch')
    idx = FULL_BRANCHES.index(SANGMEN_MAP.get(year_branch, '')) + 2
    if idx < 0: return False
    return kwargs.get('pillar_zhi') == FULL_BRANCHES[idx % 12]

# 40. 血支（《神峰通考》）
def rule_xue_zhi(**kwargs):
    """血支"""
    month_branch = kwargs.get('month_branch')
    pillar_zhi   = kwargs.get('pillar_zhi')
    idx = (FULL_BRANCHES.index(month_branch) - 3) % 12
    return pillar_zhi == FULL_BRANCHES[idx]

# 41. 流霞（《渊海子平》）
def rule_liu_xia(**kwargs):
    """流霞"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '甲':'酉','乙':'戌','丙':'未','丁':'申','戊':'巳',
        '己':'午','庚':'辰','辛':'寅','壬':'亥','癸':'卯'
    }
    return pillar_zhi == mapping.get(day_gan)

# 42. 飞刃（《三命通会》）
def rule_fei_ren(**kwargs):
    """飞刃"""
    day_gan    = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    yang = next((k for k,v in CHANGSHENG_MAP.get(day_gan, {}).items()
                 if v == '帝旺'), None)
    if not yang: return False
    idx = (FULL_BRANCHES.index(yang) + 6) % 12
    return pillar_zhi == FULL_BRANCHES[idx]

# 43.福星贵人  修正后的福星贵人规则（《渊海子平》甲日见寅，乙日见丑...）
def rule_fu_xing(**kwargs):
    """福星贵人"""
    day_gan = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '甲':'寅', '乙':'丑', '丙':'子', '丁':'酉', '戊':'申',
        '己':'未', '庚':'午', '辛':'巳', '壬':'辰', '癸':'卯'
    }
    return pillar_zhi == mapping.get(day_gan)

# 44. 红鸾（以年支查）
def rule_hong_luan(**kwargs):
    """红鸾"""
    year_branch = kwargs.get('year_branch')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '子':'卯', '丑':'寅', '寅':'丑', '卯':'子',
        '辰':'亥', '巳':'戌', '午':'酉', '未':'申',
        '申':'未', '酉':'午', '戌':'巳', '亥':'辰'
    }
    return pillar_zhi == mapping.get(year_branch, '')

# 45. 天喜（红鸾的对冲支）
def rule_tian_xi(**kwargs):
    """天喜"""
    year_branch = kwargs.get('year_branch')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '子':'酉', '丑':'申', '寅':'未', '卯':'午',
        '辰':'巳', '巳':'辰', '午':'卯', '未':'寅',
        '申':'丑', '酉':'子', '戌':'亥', '亥':'戌'
    }
    return pillar_zhi == mapping.get(year_branch, '') 

# 46. 天厨（以日干查）
def rule_tian_chu(**kwargs):
    """天厨贵人"""
    day_gan = kwargs.get('day_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '甲':'巳', '乙':'午', '丙':'子', '丁':'巳',
        '戊':'午', '己':'申', '庚':'寅', '辛':'午',
        '壬':'酉', '癸':'亥'
    }
    return pillar_zhi == mapping.get(day_gan, '')


# 47
def rule_tian_guan(**kwargs):
    """天官贵人"""
    year_gan = kwargs.get('year_gan')
    pillar_zhi = kwargs.get('pillar_zhi')
    mapping = {
        '甲':'未', '乙':'辰', '丙':'巳', '丁':'酉', '戊':'戌',
        '己':'卯', '庚':'丑', '辛':'申', '壬':'午', '癸':'寅'
    }
    return pillar_zhi == mapping.get(year_gan)

# 48
def rule_tian_fu(**kwargs):
    """天福贵人"""
    day_gan = kwargs.get('day_gan')
    hour_zhi = kwargs.get('hour_zhi')
    mapping = {
        '甲':'酉', '乙':'午', '丙':'子', '丁':'亥', '戊':'卯',
        '己':'寅', '庚':'巳', '辛':'辰', '壬':'申', '癸':'戌'
    }
    return hour_zhi == mapping.get(day_gan)

#49
def rule_tian_xing(**kwargs):
    """天刑煞：寅巳申/丑戌未互刑，子卯二刑；并并入常见“自刑”（辰午酉亥）"""
    day_zhi = kwargs.get('day_zhi')
    hour_zhi = kwargs.get('hour_zhi')
    include_self = kwargs.get('include_self_punish', True)

    tri = [('寅','巳','申'), ('丑','戌','未')]
    if (day_zhi in ('子','卯')) and (hour_zhi in ('子','卯')):
        return True
    if any(day_zhi in g and hour_zhi in g for g in tri):
        return True
    if include_self and day_zhi == hour_zhi and day_zhi in ('辰','午','酉','亥'):
        return True
    return False


# 50
def rule_tongzi(**kwargs):
    """童子煞（春秋寅子贵，冬夏卯未辰）"""
    month_branch = kwargs['month_branch']
    day_zhi = kwargs['day_zhi']
    hour_zhi = kwargs['hour_zhi']
    
    season = SEASON_MAP.get(month_branch, '')
    tongzi_zhi = []
    if season in ['春','秋']:
        tongzi_zhi = ['寅','子']
    elif season in ['夏','冬']:
        tongzi_zhi = ['卯','未','辰']
    
    return day_zhi in tongzi_zhi or hour_zhi in tongzi_zhi

# 51
def rule_dahao(**kwargs):
    """大耗（年支对冲前五辰）"""
    year_branch = kwargs['year_branch']
    pillar_zhi = kwargs['pillar_zhi']
    
    chong_index = (FULL_BRANCHES.index(year_branch) + 6) % 12
    dahao_index = (chong_index - 5) % 12
    return pillar_zhi == FULL_BRANCHES[dahao_index]

# 规则映射
SHENSHA_RULES = {
    '天乙贵人': rule_tian_yi_guiren,
    '太极贵人': rule_tai_ji_guiren,
    '天德贵人': rule_tian_de_guiren,
    '月德贵人': rule_yue_de_guiren,
    '三奇贵人': rule_san_qi,
    '文昌贵人': rule_wenchang,
    '魁罡贵人': rule_kui_gang,
    '国印贵人': rule_guo_yin,
    '学堂':      rule_xuetang,
    '词馆':      rule_ciguan,
    '驿马':      rule_yima,
    '华盖':      rule_huagai,
    '将星':      rule_jiang_xing,
    '金舆':      rule_jin_yu,
    '金神':      rule_jin_shen,
    '天医':      rule_tian_yi,
    '禄神':      rule_lu_shen,
    '拱禄':      rule_gong_lu,
    '天赦':      rule_tian_she,
    '天罗地网':  rule_tian_luo_di_wang,
    '羊刃':      rule_yang_ren,
    '亡神':      rule_wang_shen,
    '劫煞':      rule_jie_sha,
    '灾煞':      rule_zai_sha,
    '勾绞煞':    rule_gou_jiao,
    '孤辰寡宿':  rule_gu_chan,
    '元辰':      rule_yuan_cheng,
    '空亡':      rule_kong_wang,
    '十恶大败':  rule_shi_e,
    '咸池/桃花':      rule_xian_chi,
    '孤鸾煞':    rule_gu_luan,
    '阴阳差错':  rule_yin_yang,
    '四废':      rule_si_fei,
    '六厄':      rule_liu_e,
    '披麻':      rule_pi_ma,
    '隔角':      rule_ge_jiao,
    '血刃':      rule_xue_ren,
    '丧门':      rule_sang_men,
    '吊客':      rule_diao_ke,
    '血支':      rule_xue_zhi,
    '流霞':      rule_liu_xia,
    '飞刃':      rule_fei_ren,
    '福星':  rule_fu_xing,
    '红鸾':      rule_hong_luan,
    '天喜':      rule_tian_xi,
    '天厨':  rule_tian_chu,
    '天官贵人': rule_tian_guan,
    '天福贵人': rule_tian_fu,
    '天刑煞': rule_tian_xing,
    '童子煞': rule_tongzi,
    '大耗':   rule_dahao,
}


class BaziChart:
    def __init__(self, time_str: str, gender: str):
        """
        :param time_str: 'YYYYMMDDHHMM' 格式的出生时间
        :param gender: 'male' 或 'female'
        """
        # 解析输入时间并生成八字
        dt = datetime.datetime.strptime(time_str, "%Y%m%d%H%M")
        # 不再整体回推日期；子时规则仅用于“日柱”单独修正
        self.dt = dt
        self.gender = gender
        # 由 TungShing 承担全部边界裁定（年/节月/晚子时等）
        ts = TungShing(self.dt)
        yg, yz = ts.year8Char[0], ts.year8Char[1]
        mg, mz = ts.month8Char[0], ts.month8Char[1]
        dg, dz = ts.day8Char[0], ts.day8Char[1]
        hg, hz = ts.twohour8Char[0], ts.twohour8Char[1]

        leap = '闰' if ts.isLunarLeapMonth else ''
        self.lunarDate = f"{ts.lunarYearCn}年{leap}{ts.lunarMonthCn}{ts.lunarDayCn}"

        self.pillars = {
            'year':  (yg, yz),
            'month': (mg, mz),
            'day':   (dg, dz),
            'hour':  (hg, hz)
        }
    
    def ten_god(self) -> str:
        """
        计算四柱主干及其藏干的十神。
        日柱本干设为“元男”或“元女”，其余干支用 get_shishen 计算。
        返回结构：
        {
            'year':   {'干': '甲', '十神': '正财', '藏干十神': {'癸': '偏印'}},
            'month':  {...},
            'day':    {'干': '甲', '十神': '元男', '藏干十神': {}},
            'hour':   {...}
        }
        """
        day_gan = self.pillars['day'][0]
        gender_title = "元男" if self.gender == "male" else "元女"
        result = {}
        for pillar, (gan, zhi) in self.pillars.items():
            # 主干十神
            if pillar == 'day':
                shishen_main = gender_title
            else:
                shishen_main = get_shishen(day_gan, gan)
            # 藏干十神
            latent= CANGGAN.get(zhi, [])
            latent_map = {}
            for stem in latent:
                    latent_map[stem] = get_shishen(day_gan, stem)
            
            main_qi = CANGGAN.get(zhi, [''])[0]  # 取第一个藏干为主气
            zhi_shishen = get_shishen(day_gan, main_qi) if main_qi else ''
            
            result[pillar] = {
                '干': gan,
                '十神': shishen_main,
                '地支主气十神': zhi_shishen,
                '藏干十神': latent_map
            }
        return result
    
    def get_xunkong_by_ganzhi(self, gz: str) -> list[str]:
        """
        给定一个干支（如 '乙丑'），返回它所在旬的空亡地支。
        """
        return XUNKONG_MAP.get(gz, [])

    def analyze_xunkong(self) -> dict:
        """
        标准旬空口径（只以“日柱”定空亡）：
        - 先取日柱干支所在“六甲旬”的两支为空亡
        - 再标注四柱中哪些命位的地支“落空”
        - 仅返回本日旬空与命位落空，不逐柱自算空亡
        """
        day_gan, day_zhi = self.pillars['day']
        day_gz = day_gan + day_zhi
        xk_list = XUNKONG_MAP.get(day_gz, [])

        hits = {}
        hit_list = []
        for name, (_, zhi) in self.pillars.items():
            flag = (zhi in xk_list)
            hits[name] = flag
            if flag:
                hit_list.append(f"{name}支{zhi}")

        return {
            "口径": "只以日柱定旬空，不逐柱自算；本日旬空两支如下，凡四柱落此二支者为‘落空’。",
            "本日旬空": xk_list,                # 例如 ['午','未']
            "命局落空命位": hit_list,            # 例如 ['month支未','hour支午']
            "是否日支落空": self.pillars['day'][1] in xk_list,
            "命位落空标记": hits                 # {'year': False, 'month': True, 'day': False, 'hour': True}
        }
    
    def analyze_nayin(self):
        """返回四柱纳音（按天干地支组合查表）"""
        return {
            name: NAYIN.get(g + z, "未知")
            for name, (g, z) in self.pillars.items()
        }

    def analyze_changsheng(self):
        """
        返回四柱地支在日干主导下的长生状态
        """
        dg, _ = self.pillars['day']  # 日干决定查哪一行
        changsheng_order = CHANGSHENG_MAP.get(dg, {})
        result = {}
        for pillar, (_, zhi) in self.pillars.items():
            result[pillar] = changsheng_order.get(zhi, "未知")
        return result

    def analyze_shensha(self) -> dict[str, list[str]]:
        res = {p: [] for p in self.pillars}
        pillars_data = self.pillars
        day_gan, day_zhi = pillars_data['day']
        month_gan, month_zhi = pillars_data['month']
        year_gan, year_zhi  = pillars_data['year']
        hour_gan, hour_zhi = pillars_data['hour']

        # 把所有规则可能用到的参数，一次性装好
        common_kw = {
            'gender':        self.gender,
            'day_gan':       day_gan,
            'day_zhi':       day_zhi,
            'month_gan':  month_gan,
            'month_branch':  month_zhi,
            'year_gan':   year_gan,
            'year_branch':   year_zhi,
            'hour_gan':      hour_gan,
            'hour_zhi':      hour_zhi,
            'trinity_group': TRINITY_GROUP,
            'bazi_pillars':  pillars_data,
        }

        for pillar, (gan, zhi) in pillars_data.items():
            # 每柱独有的两个：pillar_gan / pillar_zhi
            kw = {
                **common_kw,
                'pillar_gan': gan,
                'pillar_zhi': zhi,
            }

            # 先三奇
            if rule_san_qi(**kw):
                res[pillar].append('三奇贵人')

            # 再所有通用规则：直接把完整 kw 扔进去
            for name, fn in SHENSHA_RULES.items():
                if name == '三奇贵人':
                    continue
                try:
                    if fn(**kw):
                        res[pillar].append(name)
                except Exception as e:
                    # 仍然保留异常打印，便于调试
                    print(f"规则{name}执行异常: {e}")

        return res
        
    def analyze_palace(self):
        """
        命宫/身宫（单一定式）
        - 命宫：从寅起顺数（月序 + 时序 - 1）
        - 身宫：从申起顺数（月序 + 时序 - 1）
        月序：寅=1…丑=12（以寅起月）
        时序：子=1…亥=12（以子起时）
        天干：以月干为起点，顺推同样步数
        """
        month_stem, month_branch = self.pillars['month']
        hour_branch = self.pillars['hour'][1]

        SEQ_YUE = ['寅','卯','辰','巳','午','未','申','酉','戌','亥','子','丑']
        SEQ_SHI = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
        SHEN_SEQ = ['申','酉','戌','亥','子','丑','寅','卯','辰','巳','午','未']

        m = SEQ_YUE.index(month_branch) + 1
        h = SEQ_SHI.index(hour_branch) + 1
        steps = m + h - 2  # 0-based

        ming_branch = SEQ_YUE[steps % 12]
        ming_stem   = FULL_STEMS[(FULL_STEMS.index(month_stem) + steps) % 10]
        shen_branch = SHEN_SEQ[steps % 12]
        shen_stem   = FULL_STEMS[(FULL_STEMS.index(month_stem) + steps) % 10]

        minggong = ming_stem + ming_branch
        shengong = shen_stem + shen_branch

        ty_stem = FULL_STEMS[(FULL_STEMS.index(month_stem) + 1) % 10]
        ty_branch = FULL_BRANCHES[(FULL_BRANCHES.index(month_branch) + 3) % 12]
        taiyuan = ty_stem + ty_branch

        return {
            '胎元': {'干支': taiyuan, '纳音': NAYIN.get(taiyuan)},
            '命宫': {'干支': minggong, '纳音': NAYIN.get(minggong)},
            '身宫': {'干支': shengong, '纳音': NAYIN.get(shengong)}
        }

    def analyze_wuxing_state(self):
        """
        五行能量旺衰判断与身强身弱分析
        返回结构：
        {
            '日主': '甲木',
            '月令': '寅',
            '五行能量': {...},                 # 原始五行总量（便于可视化）
            '旺衰状态': {'木': '旺', ...},      # 传统口径
            '日主计分': {
                '得令': x, '通根': y, '得助': z, '泄耗': w, '三合/半合修正': r, '空亡修正': q,
                '支持分': S, '消耗分': D, '强弱比': R
            },
            '格局': '身强/中和/身弱'
        }

        身强身弱（五行势能）重构版：
            - 得令（季节旺相休囚死）→ 决定基准；月令权重最高
            - 通根（支中根气：比劫/印）→ 第二要素（位置加权）
            - 得助（干上比印） vs 泄耗（食伤/财/官杀）→ 第三要素（柱位加权）
            - 空亡（按“日柱旬空”）→ 对【位置类贡献】轻度折减
            - 长生十二神（位置加权）→ 轻度微调（仅作细化，不喧宾夺主）
            - 强弱细分为：弱、偏弱、中和、偏强、强；并输出构成细目与指标
        """

        # —— 基本信息 —— #
        day_gan, day_zhi = self.pillars['day']
        day_wx = WUXING[day_gan]
        month_branch = self.pillars['month'][1]
        
        # 当令季节 → 旺相休囚死（用于“得令”）
        season_state = {
            '春': {'木':'旺','火':'相','水':'休','金':'囚','土':'死'},
            '夏': {'火':'旺','土':'相','木':'休','水':'囚','金':'死'},
            '秋': {'金':'旺','水':'相','土':'休','火':'囚','木':'死'},
            '冬': {'水':'旺','木':'相','金':'休','土':'囚','火':'死'},
            '季': {'土':'旺','金':'相','火':'休','木':'囚','水':'死'}
        }
        if month_branch in ['寅','卯','辰']:
            season = '春' if month_branch != '辰' else '季'
        elif month_branch in ['巳','午','未']:
            season = '夏' if month_branch != '未' else '季'
        elif month_branch in ['申','酉','戌']:
            season = '秋' if month_branch != '戌' else '季'
        else:
            season = '冬' if month_branch != '丑' else '季'
        state = season_state[season]  # 当前季节下各五行的“旺相休囚死”

        # —— 权重体系（更贴合实务） —— #
        STEM_W = {'year':0.6, 'month':1.0, 'day':1.0, 'hour':0.8}  # 透干权重
        BRCH_W = {'year':0.7, 'month':1.6, 'day':1.2, 'hour':0.9}  # 通根/位置权重（提升月支权重）

        STATE_MUL = {'旺':1.2,'相':1.05,'休':0.85,'囚':0.60,'死':0.40}  # 得令系数（略加强“旺相”）

        ROLE = {  # 角色系数
            '比劫': +1.00,
            '印':   +0.75,
            '食伤': -0.60,
            '财':   -0.75,   # ← 稍重
            '正官': -0.80,   # ← 与七杀分开
            '七杀': -1.00
        }

        # —— 空亡（按“日柱旬空”）对位置贡献的折减 —— #
        xk = self.analyze_xunkong()
        xk_set = set(xk['本日旬空'])
        def xk_penalty(zhi: str) -> float:
            # 落空 → 仅对“通根/位置”项温和折减
            return 0.85 if zhi in xk_set else 1.00  # 落空→位置贡献×0.8；不作用于“得令”与“透干”

        # —— 通根与长生位置微调 —— #
        CHANG_BONUS = {'帝旺':0.12,'临官':0.10,'长生':0.08,'冠带':0.06,'沐浴':0.04,
                    '养':0.03,'胎':0.02,'衰':-0.02,'病':-0.05,'死':-0.08,'墓':-0.10,'绝':-0.12}
        chang_map = CHANGSHENG_MAP.get(day_gan, {})

        # 工具：反向映射
        def inv_sheng(me):
            for k,v in SHENGKE.items():
                if v['生'] == me: return k     # 生我 → 印
        def inv_ke(me):
            for k,v in SHENGKE.items():
                if v['克'] == me: return k     # 克我 → 官杀

        sheng_wo = inv_sheng(day_wx)           # 印
        wo_sheng = SHENGKE[day_wx]['生']       # 食伤
        wo_ke    = SHENGKE[day_wx]['克']       # 财
        ke_wo    = inv_ke(day_wx)              # 官杀

        # —— 1) 得令 —— #
        de_ling = STATE_MUL[state.get(day_wx, '休')]

        # —— 2) 通根（支中根气：比劫/印）+ 长生小修正（位置项） —— #
        tong_gen = 0.0
        for pillar, (_, zhi) in self.pillars.items():
            # 藏干三气权重
            cangs = CANGGAN.get(zhi, [])
            weights = []
            if len(cangs) >= 1: weights.append((cangs[0], 0.60))
            if len(cangs) >= 2: weights.append((cangs[1], 0.30))
            if len(cangs) >= 3: weights.append((cangs[2], 0.10))

            loc_mul = BRCH_W[pillar] * xk_penalty(zhi)  # 位置与空亡折减

            for stem, wt in weights:
                wx = WUXING[stem]
                if wx == day_wx:             # 比劫
                    tong_gen += loc_mul * wt * ROLE['比劫']
                elif sheng_wo and wx == sheng_wo:  # 印
                    tong_gen += loc_mul * wt * ROLE['印']

            # 长生微调（仅对“日主五行”位置起小幅作用）
            pos = chang_map.get(zhi)
            if pos:
                tong_gen += BRCH_W[pillar] * CHANG_BONUS.get(pos, 0.0) * 0.20  # 再缩小20%，避免过度

        # —— 3) 得助（干）与泄耗（干） —— #
        de_zhu_total = 0.0
        de_zhu_break = {'比劫':0.0,'印':0.0}
        drain_total = 0.0
        drain_break = {'食伤':0.0, '财':0.0, '官杀':0.0}

        for pillar, (gan, _) in self.pillars.items():
            if pillar == 'day':
                continue  # ← 关键修正：日干本身不计入“得助”以免自我加分

            w = STEM_W[pillar]
            ss = get_shishen(day_gan, gan)
            if ss in ('比肩','劫财'):
                val = w * ROLE['比劫']; de_zhu_total += val; de_zhu_break['比劫'] += val
            elif ss in ('正印','偏印'):
                val = w * ROLE['印'];   de_zhu_total += val; de_zhu_break['印'] += val
            elif ss in ('食神','伤官'):
                val = w * (-ROLE['食伤']); drain_total += val; drain_break['食伤'] += val
            elif ss in ('正财','偏财'):
                val = w * (-ROLE['财']);    drain_total += val; drain_break['财'] += val
            elif ss == '正官':
                val = w * (-ROLE['正官']);  drain_total += val; drain_break['官杀'] += val
            elif ss == '七杀':
                val = w * (-ROLE['七杀']);  drain_total += val; drain_break['官杀'] += val

        # —— 3.1) 泄耗（支藏干） —— #
        # 把地支藏干中的 食伤/财/官杀 也计入总消耗（避免与“通根/位置”中比印重复）
        for pillar, (_, zhi) in self.pillars.items():
            # 藏干三气权重（与你前面通根的口径保持一致）
            cangs = CANGGAN.get(zhi, [])
            weights = []
            if len(cangs) >= 1: weights.append((cangs[0], 0.60))
            if len(cangs) >= 2: weights.append((cangs[1], 0.30))
            if len(cangs) >= 3: weights.append((cangs[2], 0.10))

            loc_mul = BRCH_W[pillar] * xk_penalty(zhi)

            for stem, wt in weights:
                ss = get_shishen(day_gan, stem)
                if ss in ('食神','伤官'):
                    val = loc_mul * wt * (-ROLE['食伤'])
                    drain_total += val; drain_break['食伤'] += val
                elif ss in ('正财','偏财'):
                    val = loc_mul * wt * (-ROLE['财'])
                    drain_total += val; drain_break['财'] += val
                elif ss == '正官':
                    val = loc_mul * wt * (-ROLE['正官'])
                    drain_total += val; drain_break['官杀'] += val
                elif ss == '七杀':
                    val = loc_mul * wt * (-ROLE['七杀'])
                    drain_total += val; drain_break['官杀'] += val
                # 比肩/劫财/印在“通根/位置”里已经作为支持分处理，这里不再重复

        # —— 4) 合局小加分（只对“整三合”且合到日主本行或“印”） —— #
        relations = self.analyze_relations()
        sanhe_bonus = 0.0
        for trio, wx5 in DIZHI_RELATIONS['三合'].items():
            trio_list = list(trio)
            if any(sorted(item[0]) == sorted(trio_list) for item in relations.get('三合', [])):
                if wx5 == day_wx: sanhe_bonus += 0.50
                elif sheng_wo and wx5 == sheng_wo: sanhe_bonus += 0.30

        # 若整三合“锁”在克我之行（例如甲木被金局锁），给轻微扣分
        if relations.get('三合'):
            ke_wo = inv_ke(day_wx)  # 克我之行（甲木→金）
            for trio, wx5 in DIZHI_RELATIONS['三合'].items():
                trio_list = list(trio)
                if any(sorted(item[0]) == sorted(trio_list) for item in relations.get('三合', [])):
                    if wx5 == ke_wo:
                        sanhe_bonus -= 0.15

        # —— 汇总 —— #
        support = de_ling + tong_gen + de_zhu_total + sanhe_bonus
        drain   = drain_total
        R = support / (drain + 1e-9)

        # 五档细分
        if   R < 0.75:    level = '弱'
        elif R < 0.95:    level = '偏弱'
        elif R <= 1.20:   level = '中和'
        elif R <= 1.40:   level = '偏强'
        else:             level = '强'

        # 承官杀指数：看“能任官杀”的相对能力（>1 更能承）
        carry_kill = support / (drain_break['官杀'] + 1e-9)

        # 从势候选（仅提示，不做定从）：极弱且克我/我克两端势能远超本身
        # 用能量近似：以全五行势能估算（非十神）
        energy = {'木':0.0,'火':0.0,'土':0.0,'金':0.0,'水':0.0}
        # 天干势能（按柱位）
        for pillar in self.pillars:
            gan = self.pillars[pillar][0]
            energy[WUXING[gan]] += STEM_W[pillar]
        # 地支藏干势能（按柱位+藏干权重）
        ZANG_WEIGHTS = {
            '子':{'癸':1.0}, '丑':{'己':0.6,'癸':0.3,'辛':0.1}, '寅':{'甲':0.6,'丙':0.3,'戊':0.1},
            '卯':{'乙':1.0}, '辰':{'戊':0.6,'乙':0.3,'癸':0.1}, '巳':{'丙':0.6,'庚':0.3,'戊':0.1},
            '午':{'丁':0.7,'己':0.3}, '未':{'己':0.6,'丁':0.3,'乙':0.1}, '申':{'庚':0.6,'壬':0.3,'戊':0.1},
            '酉':{'辛':1.0}, '戌':{'戊':0.6,'辛':0.3,'丁':0.1}, '亥':{'壬':0.7,'甲':0.3}
        }
        for pillar in self.pillars:
            zhi = self.pillars[pillar][1]
            loc_mul = BRCH_W[pillar] * xk_penalty(zhi)
            for stem, wt in ZANG_WEIGHTS.get(zhi, {}).items():
                energy[WUXING[stem]] += loc_mul * wt

        energy_day    = energy[day_wx]
        energy_sheng  = energy.get(sheng_wo, 0.0)
        energy_wosheng= energy.get(wo_sheng, 0.0)
        energy_woke   = energy.get(wo_ke, 0.0)
        energy_kewo   = energy.get(ke_wo, 0.0)

        cong_hint = (R < 0.60) and ((energy_woke + energy_kewo) > 1.5*(energy_day + energy_sheng))

        # 需至少有 ≥2 个“官/杀/财”透干，才提示“从势候选”
        qigan_count = sum(
            1 for p,(gan,_) in self.pillars.items() if p!='day'
            if get_shishen(day_gan, gan) in ('正官','七杀','正财','偏财')
        )
        cong_hint = cong_hint and (qigan_count >= 2)
        
        return {
            '日主': f"{day_gan}{day_wx}",
            '月令': month_branch,
            '旺衰状态': state,
            '支持分构成': {
                '得令': round(de_ling, 3),
                '通根/位置': round(tong_gen, 3),
                '得助(比劫+印)': round(de_zhu_total, 3),
                '三合加分': round(sanhe_bonus, 3)
            },
            '消耗分构成': {
                '总消耗': round(drain, 3),
                '食伤': round(drain_break['食伤'], 3),
                '财': round(drain_break['财'], 3),
                '官杀': round(drain_break['官杀'], 3)
            },
            '强弱比R': round(R, 3),
            '强弱判定': level,
            '承官杀指数': round(carry_kill, 3),
            '从势候选': cong_hint,
            '空亡口径': xk['口径'],
            '本日旬空': xk['本日旬空'],
            '命位落空标记': xk['命位落空标记']
        }

    def get_solar_terms(self):
        """
        调用 ephem 计算上下一个节气时间和名称。
        """
        return json.loads(get_nearby_solar_terms(self.dt))

    def generate_da_yun(self, num_pillars: int = 10) -> dict:
        """
        大运计算经典版（严格遵循古籍算法）
        返回结构：
        {
            "起运时间": "3岁4个月10天",
            "大运列表": [
                {
                    "序号": 1,
                    "干支": "丙子",
                    "十神": "比肩",
                    "纳音": "涧下水",
                    "起止时间": "1998-03-12 至 2008-03-12",
                    "起运年龄": 3.3
                },
                ...
            ]
        }
        有可能他们所指的节气，意思是下一个气？？
        """
        def calculate_days(start_dt, end_dt):
            """计算两个日期之间的天数（按子时划分日界）"""
            delta = end_dt - start_dt
            return delta.days + delta.seconds/(24*3600)  # 按当日时辰比例计算（24小时制）
        
        def convert_days(total_days):
            """严格按古籍规则转换天数"""
            years = total_days // 3
            remainder_days = total_days % 3
            
            months = remainder_days * 4  # 1天=4个月
            days = (remainder_days - int(remainder_days)) * 30  # 小数部分按月30天计算
            
            return {
                'years': int(years),
                'months': int(months),
                'days': round(days)
            }
    
        # 判断顺逆排
        year_gan = self.pillars['year'][0]
        is_yang_year = FULL_STEMS.index(year_gan) % 2 == 0
        is_forward = (is_yang_year and self.gender == 'male') or \
                    (not is_yang_year and self.gender == 'female')
    
        # 获取关键节气  （不含中气）
        terms = self.get_solar_terms()
        
        # 计算到节气的天数
       
        term = terms['next'] if is_forward else terms['previous']
        if not term:
            raise ValueError("未能定位用于起运的“节”时刻；请检查节气筛选与sxtwl环境。")

        sec = float(term['second'])
        whole = int(sec); micro = int(round((sec - whole)*1_000_000))
        term_dt = datetime.datetime(term['year'], term['month'], term['day'],
                                    term['hour'], term['minute'], whole, micro)

        


        if not term:
            raise ValueError("未能定位用于起运的“节”时刻；请检查节气筛选与sxtwl环境。")

        # 精确计算天数（包含时辰）
        total_days = calculate_days(self.dt, term_dt) if is_forward \
                    else calculate_days(term_dt, self.dt)
        
        # 转换为起运时间
        age_info = convert_days(total_days)
        start_desc = f"{age_info['years']}岁{age_info['months']}个月{age_info['days']}天"
        
        # 计算基准交运时间（生日+起运时间）
        base_date = self.dt + relativedelta(
            years=age_info['years'],
            months=age_info['months'],
            days=age_info['days']
        )
        
        # 排大运干支
        month_gan, month_zhi = self.pillars['month']
        step = 1 if is_forward else -1
        pillars = []
        for i in range(num_pillars):
            new_gan = FULL_STEMS[(FULL_STEMS.index(month_gan) + step*(i+1)) % 10]
            new_zhi = FULL_BRANCHES[(FULL_BRANCHES.index(month_zhi) + step*(i+1)) % 12]
            pillars.append(new_gan + new_zhi)
        
        # 生成大运列表
        da_yun_list = []
        for i, gz in enumerate(pillars):
            start_age = round(total_days/3 + i*10, 1)
            start_date = base_date + relativedelta(years=i*10)
            end_date = start_date + relativedelta(years=10)
            
            # 天干
            day_gan = self.pillars['day'][0]
            # 天干十神
            gan_shishen = get_shishen(day_gan, gz[0])

            # 藏干十神
            latent= CANGGAN.get(gz[1], [''])
            latent_map = {}
            for stem in latent:
                    latent_map[stem] = get_shishen(day_gan, stem)    
            
            # 地支主气十神
            zhi_main_qi = CANGGAN.get(gz[1], [''])[0]
            zhi_shishen = get_shishen(day_gan, zhi_main_qi) if zhi_main_qi else ''
            
            da_yun_list.append({
                "序号": i+1,
                "干支": gz,
                "天干十神": gan_shishen,       
                "地支主气十神": zhi_shishen,  
                "藏干十神": latent_map,  
                "纳音": NAYIN.get(gz, ""),
                "起止时间": f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
                "起运年龄": start_age
            })
        
        return {
            "起运时间": start_desc,
            "大运列表": da_yun_list
        }


    def analyze_relations(self, include_liunian=False, liunian_pillars=None):
        """
        分析本命局（及可选流年局）的刑冲合害会三合关系。
        :param include_liunian: 是否合并流年地支一起分析
        :param liunian_pillars: 流年四柱 dict，格式同 self.pillars
        :return: get_relations 返回的字典
        """
        # 收集本命地支
        zhi_list = [zhi for _, zhi in self.pillars.values()]

        # 如果要合并流年
        if include_liunian and liunian_pillars:
            zhi_list += [zhi for _, zhi in liunian_pillars.values()]

        return get_relations(zhi_list)

    def analyze_liunian_bazi(self, dt_str: str) -> dict:
        """
        流年八字及十神（相对于原命主日柱天干计算）。
        :param dt_str: 'YYYYMMDDHHMM' 格式的新时刻
        :return: 四柱结构，每柱含 天干、十神、地支主气十神、藏干十神
        """
        # 1. 构造新的日期对象并交由 TungShing 裁边
        dt_new = datetime.datetime.strptime(dt_str, "%Y%m%d%H%M")
        ts_new = TungShing(dt_new)

        yg, yz = ts_new.year8Char
        mg, mz = ts_new.month8Char
        hg, hz = ts_new.twohour8Char
        dg, dz = ts_new.day8Char
        
        new_pillars = {
            'year':  (yg, yz),
            'month': (mg, mz),
            'day':   (dg, dz),
            'hour':  (hg, hz)
        }
        # 3. 日主不变，仍取原命主日柱天干
        orig_ri_gan = self.pillars['day'][0]
        # 4. 对新四柱逐柱计算十神
        liunian = {}
        for pillar, (gan, zhi) in new_pillars.items():
            #天干十神
            shishen_main = get_shishen(orig_ri_gan, gan)
            # 藏干十神
            latent = CANGGAN.get(zhi, [])
            latent_map = {stem: get_shishen(orig_ri_gan, stem) for stem in latent}
            # 地支主气十神（取第一个藏干）
            main_qi = latent[0] if latent else ''
            zhi_shishen = get_shishen(orig_ri_gan, main_qi) if main_qi else ''
            liunian[pillar] = {
                '干支': (gan, zhi),
                '十神': shishen_main,
                '地支主气十神': zhi_shishen,
                '藏干十神': latent_map
            }
        
        # 本命 + 流年一起分析
        relations = self.analyze_relations(include_liunian=True, liunian_pillars=new_pillars)
        
        liunian['relations'] = relations
        return liunian

if __name__ == "__main__":
    # 使用argparse处理命令行参数
    parser = argparse.ArgumentParser(description='八字排盘分析工具')
    parser.add_argument('--session-id', required=True, help='会话ID')
    parser.add_argument('--birth-string', required=True, help='出生时间，格式为YYYYMMDDHHMM（如199001010000）')
    parser.add_argument('--gender', required=True, choices=['male', 'female'], help='性别')
    parser.add_argument('--current-time', required=True, help='当前时间，用于流年分析，格式为YYYYMMDDHHMM（如202508151402）')
    parser.add_argument('--output-path', required=True, help='输出JSON文件的完整路径')

    args = parser.parse_args()

    session_id = args.session_id
    birth_string = args.birth_string
    gender = args.gender
    current_time = args.current_time
    output_path = args.output_path

    # 参数验证
    if len(birth_string) != 12 or not birth_string.isdigit():
        print(f"八字错误: birth-string 格式不正确，应为12位数字 YYYYMMDDHHMM， 当前值: {birth_string!r}")
        sys.exit(1)

    if len(current_time) != 12 or not current_time.isdigit():
        print(f"八字错误: current-time 格式不正确，应为12位数字 YYYYMMDDHHMM，当前值: {current_time!r}")
        sys.exit(1)

    #print(f"正在分析会话 {session_id} 的八字...")
    chart = BaziChart(birth_string, gender=gender)

    result = {
        "session_id": session_id,
        "出生时间": birth_string,
        "当前时间": current_time,
        "农历时间": chart.lunarDate,
        "性别": gender,
        "四柱干支": chart.pillars,
        "四柱刑冲合害": chart.analyze_relations(),
        "十神": chart.ten_god(),
        "空亡": chart.analyze_xunkong(),
        "纳音": chart.analyze_nayin(),
        "地势": chart.analyze_changsheng(),
        **chart.analyze_palace(),
        **chart.analyze_shensha(),
        "五行能量": chart.analyze_wuxing_state(),
        **chart.get_solar_terms(),
        "da_yun_list": chart.generate_da_yun(10),
        "流年十神": chart.analyze_liunian_bazi(current_time)
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 保存结果到指定文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [SUCCESS] [排盘] 八字分析完成。")

    # 调用示例:
    # python 八字.py --session-id session_20250906_demo --birth-string 199001010000 --gender male --current-time 202509061000 --output-path sessions/session_20250906_demo/palettes/八字.json

