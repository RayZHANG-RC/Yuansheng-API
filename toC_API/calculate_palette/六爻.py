# -*- coding: utf-8 -*-
import json
import datetime
import os
import argparse
try:
    from TungShing import TungShing
except Exception:
    try:
        from .TungShing import TungShing
    except Exception:
        raise ImportError("需要提供 TungShing.py 并安装其依赖（cnlunar、sxtwl）。")

# ---------------------------
# 全局数据：八卦与六十四卦
# ---------------------------
# 地支到五行映射
ELEMENT_MAP = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水"
}
# 时支到数字映射（农历时）
HOUR_MAP = {"子": 1, "丑": 2, "寅": 3, "卯": 4, "辰": 5, "巳": 6,
            "午": 7, "未": 8, "申": 9, "酉": 10, "戌": 11, "亥": 12}


# 十天干与十二地支（用于计算旬与旬空）
TIAN_GAN = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
DI_ZHI   = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']       

# 八卦（先天八卦）对应符号，注意排列顺序（下列顺序对应伏羲先天排序）
TRIGRAMS = [
  {"卦名": "乾", "卦象": "☰", "自然象征": "天", "性情": "健", "家族关系": "父", "动物": "马", "身体部位": "头", "器官": "脑", "先天八卦方位": "南", "后天八卦方位": "西北", "五行": "金", "阴阳爻": "111", "unicode": "☰"},
  {"卦名": "兑", "卦象": "☱", "自然象征": "泽", "性情": "悦", "家族关系": "少女", "动物": "羊", "身体部位": "口", "器官": "肺", "先天八卦方位": "东南", "后天八卦方位": "西", "五行": "金", "阴阳爻": "110", "unicode": "☱"},
  {"卦名": "离", "卦象": "☲", "自然象征": "火", "性情": "丽", "家族关系": "中女", "动物": "雉", "身体部位": "目", "器官": "心", "先天八卦方位": "东", "后天八卦方位": "南", "五行": "火", "阴阳爻": "101", "unicode": "☲"},
  {"卦名": "震", "卦象": "☳", "自然象征": "雷", "性情": "动", "家族关系": "长男", "动物": "龙", "身体部位": "足", "器官": "肝", "先天八卦方位": "东北", "后天八卦方位": "东", "五行": "木", "阴阳爻": "100", "unicode": "☳"},
  {"卦名": "巽", "卦象": "☴", "自然象征": "风", "性情": "入", "家族关系": "长女", "动物": "鸡", "身体部位": "股", "器官": "胆", "先天八卦方位": "西南", "后天八卦方位": "东南", "五行": "木", "阴阳爻": "011", "unicode": "☴"},
  {"卦名": "坎", "卦象": "☵", "自然象征": "水", "性情": "陷", "家族关系": "中男", "动物": "豕", "身体部位": "耳", "器官": "肾", "先天八卦方位": "西", "后天八卦方位": "北", "五行": "水", "阴阳爻": "010", "unicode": "☵"},
  {"卦名": "艮", "卦象": "☶", "自然象征": "山", "性情": "止", "家族关系": "少男", "动物": "狗", "身体部位": "手", "器官": "胃", "先天八卦方位": "西北", "后天八卦方位": "东北", "五行": "土", "阴阳爻": "001", "unicode": "☶"},
  {"卦名": "坤", "卦象": "☷", "自然象征": "地", "性情": "顺", "家族关系": "母", "动物": "牛", "身体部位": "腹", "器官": "脾", "先天八卦方位": "北", "后天八卦方位": "西南", "五行": "土", "阴阳爻": "000", "unicode": "☷"}
]

HEXAGRAMS_FULL = [
  {"后天ID": 1, "先天ID": 63, "卦名": "乾为天", "上卦": "乾", "下卦": "乾", "阴阳爻": "111111", "unicode": "䷀"},
  {"后天ID": 2, "先天ID": 0, "卦名": "坤为地", "上卦": "坤", "下卦": "坤", "阴阳爻": "000000", "unicode": "䷁"},
  {"后天ID": 3, "先天ID": 34, "卦名": "水雷屯", "上卦": "坎", "下卦": "震", "阴阳爻": "100010", "unicode": "䷂"},
  {"后天ID": 4, "先天ID": 18, "卦名": "山水蒙", "上卦": "艮", "下卦": "坎", "阴阳爻": "010001", "unicode": "䷃"},
  {"后天ID": 5, "先天ID": 59, "卦名": "水天需", "上卦": "坎", "下卦": "乾", "阴阳爻": "111010", "unicode": "䷄"},
  {"后天ID": 6, "先天ID": 22, "卦名": "天水讼", "上卦": "乾", "下卦": "坎", "阴阳爻": "010111", "unicode": "䷅"},
  {"后天ID": 7, "先天ID": 17, "卦名": "地水师", "上卦": "坤", "下卦": "坎", "阴阳爻": "010000", "unicode": "䷆"},
  {"后天ID": 8, "先天ID": 2, "卦名": "水地比", "上卦": "坎", "下卦": "坤", "阴阳爻": "000010", "unicode": "䷇"},
  {"后天ID": 9, "先天ID": 55, "卦名": "风天小畜", "上卦": "巽", "下卦": "乾", "阴阳爻": "111011", "unicode": "䷈"},
  {"后天ID": 10, "先天ID": 10, "卦名": "天泽履", "上卦": "乾", "下卦": "兑", "阴阳爻": "110111", "unicode": "䷉"},
  {"后天ID": 11, "先天ID": 57, "卦名": "地天泰", "上卦": "坤", "下卦": "乾", "阴阳爻": "111000", "unicode": "䷊"},
  {"后天ID": 12, "先天ID": 8, "卦名": "天地否", "上卦": "乾", "下卦": "坤", "阴阳爻": "000111", "unicode": "䷋"},
  {"后天ID": 13, "先天ID": 48, "卦名": "天火同人", "上卦": "乾", "下卦": "离", "阴阳爻": "101111", "unicode": "䷌"},
  {"后天ID": 14, "先天ID": 62, "卦名": "火天大有", "上卦": "离", "下卦": "乾", "阴阳爻": "111101", "unicode": "䷍"},
  {"后天ID": 15, "先天ID": 9, "卦名": "地山谦", "上卦": "坤", "下卦": "艮", "阴阳爻": "001000", "unicode": "䷎"},
  {"后天ID": 16, "先天ID": 5, "卦名": "雷地豫", "上卦": "震", "下卦": "坤", "阴阳爻": "000100", "unicode": "䷏"},
  {"后天ID": 17, "先天ID": 39, "卦名": "泽雷随", "上卦": "兑", "下卦": "震", "阴阳爻": "100110", "unicode": "䷐"},
  {"后天ID": 18, "先天ID": 30, "卦名": "山风蛊", "上卦": "艮", "下卦": "巽", "阴阳爻": "011001", "unicode": "䷑"},
  {"后天ID": 19, "先天ID": 49, "卦名": "地泽临", "上卦": "坤", "下卦": "兑", "阴阳爻": "110000", "unicode": "䷒"},
  {"后天ID": 20, "先天ID": 4, "卦名": "风地观", "上卦": "巽", "下卦": "坤", "阴阳爻": "000011", "unicode": "䷓"},
  {"后天ID": 21, "先天ID": 38, "卦名": "火雷噬嗑", "上卦": "离", "下卦": "震", "阴阳爻": "100101", "unicode": "䷔"},
  {"后天ID": 22, "先天ID": 42, "卦名": "山火贲", "上卦": "艮", "下卦": "离", "阴阳爻": "101001", "unicode": "䷕"},
  {"后天ID": 23, "先天ID": 1, "卦名": "山地剥", "上卦": "艮", "下卦": "坤", "阴阳爻": "000001", "unicode": "䷖"},
  {"后天ID": 24, "先天ID": 33, "卦名": "地雷复", "上卦": "坤", "下卦": "震", "阴阳爻": "100000", "unicode": "䷗"},
  {"后天ID": 25, "先天ID": 40, "卦名": "天雷无妄", "上卦": "乾", "下卦": "震", "阴阳爻": "100111", "unicode": "䷘"},
  {"后天ID": 26, "先天ID": 58, "卦名": "山天大畜", "上卦": "艮", "下卦": "乾", "阴阳爻": "111001", "unicode": "䷙"},
  {"后天ID": 27, "先天ID": 34, "卦名": "山雷颐", "上卦": "艮", "下卦": "震", "阴阳爻": "100001", "unicode": "䷚"},
  {"后天ID": 28, "先天ID": 31, "卦名": "泽风大过", "上卦": "兑", "下卦": "巽", "阴阳爻": "011110", "unicode": "䷛"},
  {"后天ID": 29, "先天ID": 19, "卦名": "坎为水", "上卦": "坎", "下卦": "坎", "阴阳爻": "010010", "unicode": "䷜"},
  {"后天ID": 30, "先天ID": 46, "卦名": "离为火", "上卦": "离", "下卦": "离", "阴阳爻": "101101", "unicode": "䷝"},
  {"后天ID": 31, "先天ID": 15, "卦名": "泽山咸", "上卦": "兑", "下卦": "艮", "阴阳爻": "001110", "unicode": "䷞"},
  {"后天ID": 32, "先天ID": 29, "卦名": "雷风恒", "上卦": "震", "下卦": "巽", "阴阳爻": "011100", "unicode": "䷟"},
  {"后天ID": 33, "先天ID": 16, "卦名": "天山遁", "上卦": "乾", "下卦": "艮", "阴阳爻": "001111", "unicode": "䷠"},
  {"后天ID": 34, "先天ID": 61, "卦名": "雷天大壮", "上卦": "震", "下卦": "乾", "阴阳爻": "111100", "unicode": "䷡"},
  {"后天ID": 35, "先天ID": 6, "卦名": "火地晋", "上卦": "离", "下卦": "坤", "阴阳爻": "000101", "unicode": "䷢"},
  {"后天ID": 36, "先天ID": 41, "卦名": "地火明夷", "上卦": "坤", "下卦": "离", "阴阳爻": "101000", "unicode": "䷣"},
  {"后天ID": 37, "先天ID": 44, "卦名": "风火家人", "上卦": "巽", "下卦": "离", "阴阳爻": "101011", "unicode": "䷤"},
  {"后天ID": 38, "先天ID": 54, "卦名": "火泽睽", "上卦": "离", "下卦": "兑", "阴阳爻": "110101", "unicode": "䷥"},
  {"后天ID": 39, "先天ID": 11, "卦名": "水山蹇", "上卦": "坎", "下卦": "艮", "阴阳爻": "001010", "unicode": "䷦"},
  {"后天ID": 40, "先天ID": 21, "卦名": "雷水解", "上卦": "震", "下卦": "坎", "阴阳爻": "010100", "unicode": "䷧"},
  {"后天ID": 41, "先天ID": 50, "卦名": "山泽损", "上卦": "艮", "下卦": "兑", "阴阳爻": "110001", "unicode": "䷨"},
  {"后天ID": 42, "先天ID": 32, "卦名": "风雷益", "上卦": "巽", "下卦": "震", "阴阳爻": "100011", "unicode": "䷩"},
  {"后天ID": 43, "先天ID": 60, "卦名": "泽天夬", "上卦": "兑", "下卦": "乾", "阴阳爻": "111110", "unicode": "䷪"},
  {"后天ID": 44, "先天ID": 32, "卦名": "天风姤", "上卦": "乾", "下卦": "巽", "阴阳爻": "011111", "unicode": "䷫"},
  {"后天ID": 45, "先天ID": 7, "卦名": "泽地萃", "上卦": "兑", "下卦": "坤", "阴阳爻": "000110", "unicode": "䷬"},
  {"后天ID": 46, "先天ID": 25, "卦名": "地风升", "上卦": "坤", "下卦": "巽", "阴阳爻": "011000", "unicode": "䷭"},
  {"后天ID": 47, "先天ID": 23, "卦名": "泽水困", "上卦": "兑", "下卦": "坎", "阴阳爻": "010110", "unicode": "䷮"},
  {"后天ID": 48, "先天ID": 27, "卦名": "水风井", "上卦": "坎", "下卦": "巽", "阴阳爻": "011010", "unicode": "䷯"},
  {"后天ID": 49, "先天ID": 47, "卦名": "泽火革", "上卦": "兑", "下卦": "离", "阴阳爻": "101110", "unicode": "䷰"},
  {"后天ID": 50, "先天ID": 30, "卦名": "火风鼎", "上卦": "离", "下卦": "巽", "阴阳爻": "011101", "unicode": "䷱"},
  {"后天ID": 51, "先天ID": 37, "卦名": "震为雷", "上卦": "震", "下卦": "震", "阴阳爻": "100100", "unicode": "䷲"},
  {"后天ID": 52, "先天ID": 10, "卦名": "艮为山", "上卦": "艮", "下卦": "艮", "阴阳爻": "001001", "unicode": "䷳"},
  {"后天ID": 53, "先天ID": 12, "卦名": "风山渐", "上卦": "巽", "下卦": "艮", "阴阳爻": "001011", "unicode": "䷴"},
  {"后天ID": 54, "先天ID": 53, "卦名": "雷泽归妹", "上卦": "震", "下卦": "兑", "阴阳爻": "110100", "unicode": "䷵"},
  {"后天ID": 55, "先天ID": 45, "卦名": "雷火丰", "上卦": "震", "下卦": "离", "阴阳爻": "101100", "unicode": "䷶"},
  {"后天ID": 56, "先天ID": 13, "卦名": "火山旅", "上卦": "离", "下卦": "艮", "阴阳爻": "001101", "unicode": "䷷"},
  {"后天ID": 57, "先天ID": 28, "卦名": "巽为风", "上卦": "巽", "下卦": "巽", "阴阳爻": "011011", "unicode": "䷸"},
  {"后天ID": 58, "先天ID": 55, "卦名": "兑为泽", "上卦": "兑", "下卦": "兑", "阴阳爻": "110110", "unicode": "䷹"},
  {"后天ID": 59, "先天ID": 20, "卦名": "风水涣", "上卦": "巽", "下卦": "坎", "阴阳爻": "010011", "unicode": "䷺"},
  {"后天ID": 60, "先天ID": 51, "卦名": "水泽节", "上卦": "坎", "下卦": "兑", "阴阳爻": "110010", "unicode": "䷻"},
  {"后天ID": 61, "先天ID": 52, "卦名": "风泽中孚", "上卦": "巽", "下卦": "兑", "阴阳爻": "110011", "unicode": "䷼"},
  {"后天ID": 62, "先天ID": 13, "卦名": "雷山小过", "上卦": "震", "下卦": "艮", "阴阳爻": "001100", "unicode": "䷽"},
  {"后天ID": 63, "先天ID": 43, "卦名": "水火既济", "上卦": "坎", "下卦": "离", "阴阳爻": "101010", "unicode": "䷾"},
  {"后天ID": 64, "先天ID": 21, "卦名": "火水未济", "上卦": "离", "下卦": "坎", "阴阳爻": "010101", "unicode": "䷿"}
]


# 八宫卦象次序表
# 此处按传统划分，八宫分别为：乾宫、震宫、坎宫、艮宫、坤宫、巽宫、离宫、兑宫
# 数据中括号内：[本体卦, 初爻变, 第二爻变, 第三爻变, 第四爻变, 第五爻变, 游魂卦, 归魂卦]
EIGHT_PALACES_BY_NAME = {
    "乾宫": ["乾为天","天风姤","天山遁","天地否","风地观","山地剥","火地晋","火天大有"],
    "兑宫": ["兑为泽","泽水困","泽地萃","泽山咸","水山蹇","地山谦","雷山小过","雷泽归妹"],
    "离宫": ["离为火","火山旅","火风鼎","火水未济","山水蒙","风水涣","天水讼","天火同人"],
    "震宫": ["震为雷","雷地豫","雷水解","雷风恒","地风升","水风井","泽风大过","泽雷随"],
    "巽宫": ["巽为风","风天小畜","风火家人","风雷益","天雷无妄","火雷噬嗑","山雷颐","山风蛊"],
    "坎宫": ["坎为水","水泽节","水雷屯","水火既济","泽火革","雷火丰","地火明夷","地水师"],
    "艮宫": ["艮为山","山火贲","山天大畜","山泽损","火泽睽","天泽履","风泽中孚","风山渐"],
    "坤宫": ["坤为地","地雷复","地泽临","地天泰","雷天大壮","泽天夬","水天需","水地比"]
}


# 纳甲表，含三爻（初爻，二爻，三爻）
NAJIA_TABLE = {
    "乾": {"下卦": ["子", "寅", "辰"], "上卦": ["午", "申", "戌"]},
    "坤": {"下卦": ["未", "巳", "卯"], "上卦": ["丑", "亥", "酉"]},
    "震": {"下卦": ["子", "寅", "辰"], "上卦": ["午", "申", "戌"]},
    "坎": {"下卦": ["寅", "辰", "午"], "上卦": ["申", "戌", "子"]},
    "艮": {"下卦": ["辰", "午", "申"], "上卦": ["戌", "子", "寅"]},
    "巽": {"下卦": ["丑", "亥", "酉"], "上卦": ["未", "巳", "卯"]},
    "离": {"下卦": ["卯", "丑", "亥"], "上卦": ["酉", "未", "巳"]},
    "兑": {"下卦": ["巳", "卯", "丑"], "上卦": ["亥", "酉", "未"]}
}

# 五行关系决定六亲
LIUQIN_REL = {"生我": "父母", "我生": "子孙", "克我": "官鬼", "我克": "妻财", "同我": "兄弟"}

# 五行生克表
GENERATION = {"金": ["水"], "水": ["木"], "木": ["火"], "火": ["土"], "土": ["金"]}
OVERCOME = {"金": ["木"], "木": ["土"], "土": ["水"], "水": ["火"], "火": ["金"]}

# 计算五行之间关系
def relation(me, other):
    if other in GENERATION.get(me, []):
        return "我生"
    elif other in OVERCOME.get(me, []):
        return "我克"
    elif me in GENERATION.get(other, []):
        return "生我"
    elif me in OVERCOME.get(other, []):
        return "克我"
    else:
        return "同我"

# 将爻文字转换为二值：少阴、老阴均为 0；少阳、老阳均为 1。
YAO_VALUE = {"少阴": 0, "老阴": 0, "少阳": 1, "老阳": 1}
# 动爻变换：老阴 → 少阳（0→1），老阳 → 少阴（1→0）
TRANSFORM = {"老阴": "少阳", "老阳": "少阴"}

# —— 力量（power）可配置 ——
# 你可以在这里统一调参：旺衰映射、各标记加权（含“世/应”）
POWER_CONFIG = {
    "旺衰权重": {"旺": 2.0, "相": 1.0, "休": 0.0, "囚": -1.0, "死": -2.0},
    "标记权重": {
        "动": 1.0,
        "旬空": -2.0,
        "值月": 1.0,
        "值日": 0.5,
        "世": 0.5,
        "应": 0.3
    }
}  

# —— 快速查表：卦名 <-> 三位二进制（阳=1、阴=0） —— 
TRIGRAM_BITS_BY_NAME = {t["卦名"]: t["阴阳爻"] for t in TRIGRAMS}
TRIGRAM_NAME_BY_BITS = {t["阴阳爻"]: t["卦名"] for t in TRIGRAMS}


def _compose_hex_bits(upper_name: str, lower_name: str) -> str:
    """
    由上、下卦名求六位二进制串（下三位+上三位）。
    """
    up = TRIGRAM_BITS_BY_NAME.get(upper_name, "")
    low = TRIGRAM_BITS_BY_NAME.get(lower_name, "")
    return (low + up) if (up and low) else ""

def validate_hexagram_binary():
    """
    校验 HEXAGRAMS_FULL 中每一卦的 '阴阳爻' 是否与（下三位+上三位）一致；
    若不一致，抛出详细错误，便于定位手工数据失真。
    """
    mismatches = []
    for h in HEXAGRAMS_FULL:
        expect = _compose_hex_bits(h["上卦"], h["下卦"])
        if h.get("阴阳爻") != expect:
            mismatches.append((h["卦名"], h.get("阴阳爻"), expect))
    if mismatches:
        raise ValueError("HEXAGRAMS_FULL 阴阳爻字段与上/下卦不一致: " + str(mismatches))


# ---------------------------
# 六爻排盘框架程序
# ---------------------------
# 本程序采用时间起卦方式，输入公历时间字符串和本卦六爻（从初爻到上爻，取值为 "少阴"、"老阴"、"少阳"、"老阳"）
# 程序按步骤：解析时间/农历干支、构造本卦与变卦、安世应、定卦宫、纳甲、装六亲、装六神，
# 并利用完整八卦、64卦数据用于卦象辨识（本例中仅示意卦名查找）。

class LiuYao:
    def __init__(self, time_str, yao_list):
        """
        time_str：YYYYMMDDHHMM格式的公历时间字符串
        yao_list：列表，六爻（依次自初爻到上爻），取值为 "少阴"、"老阴"、"少阳"、"老阳"
        """
        self.time_str = time_str
        self.yao_list = yao_list
        self.init_time_info()
        self.calc_hexagram()
        # 分别对本卦和变卦计算：先确定世应，再依据卦ID在64卦中的位置直接查找卦宫
        self.determine_gua_gong_for("ben")
        self.determine_gua_gong_for("bian")
        self.locate_shiying_for("ben")
        self.locate_shiying_for("bian")
        self.do_najia_for("ben")
        self.do_najia_for("bian")
        self.assign_liuqin_for("ben")
        self.assign_liuqin_for("bian")
        # 六神统一依据当前日天干确定
        self.assign_liushen()
        # 计算飞伏（基于纳甲与卦宫五行的简化版）
        self.compute_feifu()

        # 月建 / 日建 / 旬空
        self.compute_xunkong()

        # 懒加载爻辞数据
        self._load_yaoci_dataset()

    def init_time_info(self):
        year = int(self.time_str[0:4])
        month = int(self.time_str[4:6])
        day = int(self.time_str[6:8])
        hour = int(self.time_str[8:10])
        minute = int(self.time_str[10:12])
        dt = datetime.datetime(year, month, day, hour, minute)
        self.dt = dt
        ts = TungShing(self.dt) 
        self.current_ganzhi = {
            "年": ts.year8Char,
            "月": ts.month8Char,
            "日": ts.day8Char,
            "时": ts.twohour8Char
        }

        # 提前抽取“月建”“日建”（地支）
        self.yue_jian = self._extract_branch(self.current_ganzhi.get("月", ""))
        self.ri_jian  = self._extract_branch(self.current_ganzhi.get("日", ""))

    def calc_hexagram(self):
        """
        装卦：
        将输入爻转换为二值（0阴，1阳），分为下卦（前三爻）和上卦（后三爻），
        并用 TRIGRAMS 得到卦名，进而从 HEXAGRAMS_FULL 数据库中匹配完整卦资料。
        同时对原局（本卦）和动爻转换后的局（变卦）分别计算。
        """
        self.ben = [YAO_VALUE[y] for y in self.yao_list]
        self.bian = [YAO_VALUE[TRANSFORM[y]] if y in TRANSFORM else YAO_VALUE[y] for y in self.yao_list]

        def get_gua_name(bits):
            bit_str = ''.join(str(b) for b in bits)
            return TRIGRAM_NAME_BY_BITS.get(bit_str, "未知")

        # 本卦：下卦：前三爻；上卦：后三爻
        self.ben_lower = get_gua_name(self.ben[:3])
        self.ben_upper = get_gua_name(self.ben[3:])
        # 变卦：同上
        self.bian_lower = get_gua_name(self.bian[:3])
        self.bian_upper = get_gua_name(self.bian[3:])

        self.bengua = next((h for h in HEXAGRAMS_FULL if h["上卦"] == self.ben_upper and h["下卦"] == self.ben_lower), None)
        self.biangua = next((h for h in HEXAGRAMS_FULL if h["上卦"] == self.bian_upper and h["下卦"] == self.bian_lower), None)

    def do_najia_for(self, hex_type):
        """
        动态纳甲：
        根据指定 hex_type（"ben"或"bian"）的下卦和上卦名称，
        从 NAJIA_TABLE 中取出对应的地支排列，组成六爻的纳甲数据，
        分别存入 self.najia_ben 和 self.najia_bian。
        """
        if hex_type == "ben":
            lower_name = self.ben_lower
            upper_name = self.ben_upper
        else:
            lower_name = self.bian_lower
            upper_name = self.bian_upper

        lower_data = NAJIA_TABLE.get(lower_name, {})
        upper_data = NAJIA_TABLE.get(upper_name, {})
        lower_branches = lower_data.get("下卦", [])
        upper_branches = upper_data.get("上卦", [])
        if len(lower_branches) == 3 and len(upper_branches) == 3:
            result = {
                "初爻": lower_branches[0],
                "二爻": lower_branches[1],
                "三爻": lower_branches[2],
                "四爻": upper_branches[0],
                "五爻": upper_branches[1],
                "六爻": upper_branches[2]
            }
        else:
            result = {}
        if hex_type == "ben":
            self.najia_ben = result
        else:
            self.najia_bian = result

    # ---------------------------
    # 动态定位世应（分别对本卦与变卦）
    # ---------------------------
    def locate_shiying_for(self, hex_type):
        """
        动态定位“世”与“应”：
        （1）若该卦在所属宫中的序位为 0（代表卦），则固定设世爻为上爻（索引5），应为下卦第三爻（索引2）。
        （2）否则，依据下卦（三爻：索引0=地，1=人，2=天）与上卦（索引3=地，4=人，5=天）的比较，
            采用以下规则：
             - 若上卦天爻、人爻与下卦天爻、人爻全相同，则世 = 0；
             - 若仅上卦天爻与下卦天爻相同，则世 = 1；
             - 若上卦天爻与下卦天爻及上卦地爻与下卦地爻皆相同（或上下卦互错），则世 = 2；
             - 若下卦地爻与人爻分别与上卦对应相同，则世 = 3；
             - 若上卦地爻、人爻与下卦地爻、人爻全相同，则世 = 4；
             - 其他情况，默认世 = 5。
        “应”爻则取为 (世 + 3) mod 6。
        # 如果代表卦，则世固定为上爻

        if hex_type == "ben":
            bin_list = self.ben
            pos = getattr(self, "palace_pos_ben", None)
        else:
            bin_list = self.bian
            pos = getattr(self, "palace_pos_bian", None)
        if pos == 0:
            shi = 5
            ying = 2
        else:
            L1, L2, L3 = bin_list[0], bin_list[1], bin_list[2]
            U1, U2, U3 = bin_list[3], bin_list[4], bin_list[5]
            if (U3 == L3) and (U2 == L2):
                shi = 0  # 天人归一
            elif U3 == L3:
                shi = 1  # 天同
            elif ((U3 == L3) and (U1 == L1)) or ((U1 == L3) and (U3 == L1) and (U2 == L2)):
                shi = 2  # 天地或互错
            elif (L1 == L2) and (U1 == U2):
                shi = 3  # 地同人同
            elif (U1 == L1) and (U2 == L2):
                shi = 4  # 地人相同
            else:
                shi = 5  # 默认

        """
   
        pos = self.palace_pos_ben if hex_type=="ben" else self.palace_pos_bian
        # 允许 None：直接保守回退
        if pos is None:
            shi = 5  # 默认给 6 世
        else:
            idx_map = {0:5, 1:0, 2:1, 3:2, 4:3, 5:4, 6:3, 7:2}
            shi = idx_map.get(pos, 5)
        
        ying = (shi + 3) % 6

        # 世爻和应爻的索引从 1 开始，所以需要加 1
        if hex_type=="ben":
            self.shiying_ben = {"世爻": shi+1, "应爻": ying+1}
        else:
            self.shiying_bian = {"世爻": shi+1, "应爻": ying+1}

    # ---------------------------
    # 根据卦在64卦中的位置确定卦宫及宫内序位
    # ---------------------------
    def determine_gua_gong_for(self, hex_type):
        """
        根据该卦在 64 卦中的索引，在 EightPalaces 中查找所属宫及其在宫内的序位（0～7）。
        序位对应：
            0 → 本体卦，
            1 → 初爻变，
            2 → 第二爻变，
            3 → 第三爻变，
            4 → 第四爻变，
            5 → 第五爻变，
            6 → 游魂卦，
            7 → 归魂卦。
        结果分别存入 self.gua_gong_ben 与 self.palace_pos_ben（以及变卦对应的变量）。
        """
        hex_obj = self.bengua if hex_type=="ben" else self.biangua
        palace_name, pos = "未定宫", None
        if hex_obj and "卦名" in hex_obj:
            name = hex_obj["卦名"]
            for g,glist in EIGHT_PALACES_BY_NAME.items():
                if name in glist:
                    palace_name = g
                    pos = glist.index(name)  # 0..7
                    break
        if hex_type=="ben":
            self.gua_gong_ben, self.palace_pos_ben = palace_name, pos
        else:
            self.gua_gong_bian, self.palace_pos_bian = palace_name, pos


    # ---------------------------
    # 动态装六亲（分别对本卦与变卦）
    # ---------------------------
    def assign_liuqin_for(self, hex_type):
        """
        根据指定 hex_type 的纳甲结果（六爻所用的地支）以及其卦宫代表的五行（“我”），
        利用五行生克（relation函数），将每爻对应的“他”与“我”的关系映射为：
            生我 → 父母； 我生 → 子孙； 我克 → 妻财； 克我 → 官鬼； 同我 → 兄弟。
        分别存入 self.liuqin_ben 与 self.liuqin_bian。
        """
        branches = [ (self.najia_ben if hex_type=="ben" else self.najia_bian).get(k,"")
                    for k in ["初爻","二爻","三爻","四爻","五爻","六爻"] ]
        palace = self.gua_gong_ben if hex_type=="ben" else self.gua_gong_bian
        my_elem = None
        if palace and palace!="未定宫":
            trigram_char = palace[0]  # “乾宫”取“乾”
            for t in TRIGRAMS:
                if t["卦名"]==trigram_char:
                    my_elem = t["五行"]; break
        liuqin={}
        for i,br in enumerate(branches,1):
            if my_elem and br in ELEMENT_MAP:
                other = ELEMENT_MAP[br]
                r = relation(my_elem, other)
                liuqin[i] = LIUQIN_REL.get(r, "未知")
            else:
                liuqin[i] = "未知"
        if hex_type=="ben": self.liuqin_ben=liuqin
        else: self.liuqin_bian=liuqin

    # ---------------------------
    # 动态装六神（统一盘局）
    # ---------------------------
    def assign_liushen(self):
        """
        动态装六神：
        根据当前日天干（从当前八字中取“日”柱的天干）确定基础六神：
          甲、乙日起青龙；丙、丁日起朱雀；戊日起勾陈；
          己日起螣蛇；庚、辛日起白虎；壬、癸日起玄武。
        然后从该基础神开始，依次循环排列赋予六爻（自初爻至上爻）。
        """
        # 取得“日柱”天干，假设 current_ganzhi["日"] 的第一个字符为天干
        day_gan = self.current_ganzhi["日"][0] if self.current_ganzhi.get("日") else None
        if day_gan in ['甲', '乙']:
            base_god = "青龙"
        elif day_gan in ['丙', '丁']:
            base_god = "朱雀"
        elif day_gan in ['戊']:
            base_god = "勾陈"
        elif day_gan in ['己']:
            base_god = "螣蛇"
        elif day_gan in ['庚', '辛']:
            base_god = "白虎"
        elif day_gan in ['壬', '癸']:
            base_god = "玄武"
        else:
            base_god = "未知"
        # 定义六神的循环顺序（传统顺序）：青龙、朱雀、勾陈、螣蛇、白虎、玄武
        gods_order = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
        if base_god in gods_order:
            idx = gods_order.index(base_god)
        else:
            idx = 0
        liushen_dynamic = {}
        # 从初爻（最低）开始依次排列
        for i in range(6):
            liushen_dynamic[i+1] = gods_order[(idx + i) % 6]
        self.liushen = liushen_dynamic

    def compute_feifu(self):
        """
        计算飞伏（简化口径）：
        - 以本卦纳甲地支为基准，映射到五行，与卦宫五行对比：
          若某爻“他”的五行克“我”（克我=官鬼），视为可能的伏神来源；
          若某爻“他”的五行被“我”克（我克=妻财），该爻在变卦中若关系缓解（转生/同我），视作飞神。
        - 输出：每爻标记 {"飞": bool, "伏": bool, "他行": 五行, "关系": 生我/我生/我克/克我/同我}
        注：此为工程简化实现，满足断卦阅读需要，后续可替换为更严谨的飞伏神算法（含互卦、错综等）。
        """
        def palace_element(palace_name: str):
            if not palace_name or palace_name == "未定宫":
                return None
            trigram_char = palace_name[0]
            for t in TRIGRAMS:
                if t["卦名"] == trigram_char:
                    return t["五行"]
            return None

        my_elem_ben = palace_element(self.gua_gong_ben)
        my_elem_bian = palace_element(self.gua_gong_bian)

        def row_info(branch: str, my_elem_now: str):
            if not branch or branch not in ELEMENT_MAP or not my_elem_now:
                return {"飞": False, "伏": False, "他行": None, "关系": None}
            other_elem = ELEMENT_MAP[branch]
            rel_now = relation(my_elem_now, other_elem)
            mark = {"飞": False, "伏": False, "他行": other_elem, "关系": rel_now}
            return mark

        # 基于本卦与变卦的纳甲，逐爻比较关系是否由“克我/我克”转向“同我/我生/生我”
        self.feifu = {}
        for i, key in enumerate(["初爻","二爻","三爻","四爻","五爻","六爻"], start=1):
            br_ben = (self.najia_ben or {}).get(key, "")
            br_bian = (self.najia_bian or {}).get(key, "")
            ben_mark = row_info(br_ben, my_elem_ben)
            bian_mark = row_info(br_bian, my_elem_bian)
            # 简化规则：若本卦为“克我”，则视为伏；若变卦关系缓解（非克我且非我克），则本位记“飞”
            if ben_mark["关系"] == "克我":
                ben_mark["伏"] = True
            # 飞：从紧张（克向）到缓解（非克向）
            tense = ben_mark["关系"] in ("克我", "我克")
            ease = bian_mark["关系"] in ("同我", "我生", "生我")
            if tense and ease:
                ben_mark["飞"] = True
            self.feifu[i] = {"本卦": ben_mark, "变卦": bian_mark}

    # ---------------------------
    # 爻辞/断易天机 数据加载与派生
    # ---------------------------
    def _load_yaoci_dataset(self):
        """
        从 data/易经爻辞.json 懒加载爻辞数据结构：
        {
          "卦名": {
            "卦辞": "...",
            "爻辞": {"1": "初爻...", ..., "6": "上爻..."}
          }
        }
        若文件缺失或不合法，则置空不影响主流程。
        """
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(base_dir, "data", "易经爻辞.json")
            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    self.yaoci_dataset = json.load(f)
            else:
                self.yaoci_dataset = {}
        except Exception:
            self.yaoci_dataset = {}

    def _sparse_feifu(self, phase: str):
        """
        返回仅包含有“飞”或“伏”为 True 的爻位的简化映射。
        phase: "本卦" 或 "变卦"
        输出示例：{ 1: {"飞": true}, 4: {"伏": true, "飞": true} }
        """
        result = {}
        if not hasattr(self, "feifu") or not isinstance(self.feifu, dict):
            return result
        key = "本卦" if phase == "本卦" else "变卦"
        for idx, marks in self.feifu.items():
            v = marks.get(key, {}) if isinstance(marks, dict) else {}
            flags = {}
            if v.get("飞"):
                flags["飞"] = True
            if v.get("伏"):
                flags["伏"] = True
            if flags:
                result[idx] = flags
        return result

    # ---------------------------
    # 月建 / 日建 / 旬空
    # ---------------------------
    def _extract_branch(self, gz: str) -> str:
        """从干支串中提取地支（任取第一个属于地支表的字符）"""
        for ch in gz:
            if ch in DI_ZHI:
                return ch
        return ""


    def _extract_ganzhi_pair(self, text: str) -> str:
        """
        从如“癸卯日”“庚子”之类字符串内，鲁棒地抽取“天干+地支”两字。
        找不到时返回 text[:2] 作保底。
        """
        g = next((ch for ch in text if ch in TIAN_GAN), "")
        if not g:
            return text[:2]
        # 找到 g 之后的第一个地支
        rest = text[text.index(g)+1:]
        z = next((ch for ch in rest if ch in DI_ZHI), "")
        return (g + z) if z else text[:2]

    def _build_60_ganzhi(self):
        """生成从甲子开始的六十甲子序列"""
        seq = []
        gi = zi = 0
        while len(seq) < 60:
            seq.append(TIAN_GAN[gi] + DI_ZHI[zi])
            gi = (gi + 1) % 10
            zi = (zi + 1) % 12
        return seq

    def compute_xunkong(self):
        """
        依据当日干支确定所属“甲×旬”与两支旬空，
        并标出本卦/变卦纳甲中落旬空的爻位。
        """
        day_gz_full = (self.current_ganzhi.get("日") or "").strip()
        day_gz = self._extract_ganzhi_pair(day_gz_full)
        sexa = self._build_60_ganzhi()
        try:
            idx = sexa.index(day_gz)  # 更鲁棒的干支配对解析
        except ValueError:
            idx = 0  # 容错：找不到则当甲子处理



        xun_idx = idx // 10  # 0..5
        xun_names = ['甲子','甲戌','甲申','甲午','甲辰','甲寅']
        xunkong_pairs = [
            ['戌','亥'], ['申','酉'], ['午','未'],
            ['辰','巳'], ['寅','卯'], ['子','丑']
        ]
        self.xun_info = {
            "旬名": xun_names[xun_idx],
            "旬序": xun_idx,
            "旬空": xunkong_pairs[xun_idx]
        }

        def _xk_positions(najia: dict):
            if not isinstance(najia, dict):
                return []
            kong = set(self.xun_info["旬空"])
            pos = []
            for i, key in enumerate(["初爻","二爻","三爻","四爻","五爻","六爻"], start=1):
                br = najia.get(key, "")
                if br in kong:
                    pos.append(i)
            return pos

        self.xunkong_pos_ben  = _xk_positions(getattr(self, "najia_ben", {}))
        self.xunkong_pos_bian = _xk_positions(getattr(self, "najia_bian", {}))

        # —— 月建/日建落位（与纳甲地支相同的爻位） ——
        def _positions_for(branch: str, najia: dict):
            if not branch or not isinstance(najia, dict): return []
            keys = ["初爻","二爻","三爻","四爻","五爻","六爻"]
            return [i for i,k in enumerate(keys, start=1) if najia.get(k, "") == branch]
        self.yuejian_pos_ben  = _positions_for(self.yue_jian, getattr(self, "najia_ben", {}))
        self.yuejian_pos_bian = _positions_for(self.yue_jian, getattr(self, "najia_bian", {}))
        self.rijian_pos_ben   = _positions_for(self.ri_jian,  getattr(self, "najia_ben", {}))
        self.rijian_pos_bian  = _positions_for(self.ri_jian,  getattr(self, "najia_bian", {}))


     # —— 辅助：季节与旺衰 —— 
    def _season_of_branch(self, zhi: str) -> str:
        """按三会分季：寅卯辰春；巳午未夏；申酉戌秋；亥子丑冬。"""
        if zhi in ("寅","卯","辰"): return "春"
        if zhi in ("巳","午","未"): return "夏"
        if zhi in ("申","酉","戌"): return "秋"
        if zhi in ("亥","子","丑"): return "冬"
        return ""

    def _wangshuai(self, elem: str, yue_jian: str) -> str:
        """
        工程化旺衰：春木旺、夏火旺、秋金旺、冬水旺；土旺四季；
        非旺者给出相/休/囚/死的简化映射，满足断卦阅读。
        """
        if not elem or not yue_jian: return ""
        season = self._season_of_branch(yue_jian)
        if elem == "土":
            # 四季土旺：辰未戌丑为四季月，其他月视作「相」
            return "旺" if yue_jian in ("辰","未","戌","丑") else "相"
        table = {
            "春": {"木":"旺","火":"相","土":"相","金":"囚","水":"死"},
            "夏": {"火":"旺","土":"相","木":"相","金":"死","水":"囚"},
            "秋": {"金":"旺","水":"相","土":"相","火":"囚","木":"死"},
            "冬": {"水":"旺","木":"相","土":"相","金":"囚","火":"死"},
        }
        return table.get(season, {}).get(elem, "")

    def _annotate_lines(self, hex_type: str):
        """
        逐爻注解：六亲、六神、纳甲地支/五行、世应、动静、旬空、值月/值日、旺衰、飞伏、力量(power)。
        hex_type: "ben" | "bian"
       """
        najia = getattr(self, "najia_ben" if hex_type=="ben" else "najia_bian", {}) or {}
        liuqin = getattr(self, "liuqin_ben" if hex_type=="ben" else "liuqin_bian", {}) or {}
        shiying = getattr(self, "shiying_ben" if hex_type=="ben" else "shiying_bian", {}) or {}
        xk_pos = getattr(self, "xunkong_pos_ben" if hex_type=="ben" else "xunkong_pos_bian", []) or []
        # 动爻来自原始输入（对变卦也沿用原位动静标记）
        moving = {i+1: (y in ("老阴","老阳")) for i,y in enumerate(self.yao_list)}
        # 飞伏标记（相位）
        phase_key = "本卦" if hex_type=="ben" else "变卦"
        feifu = {}
        if hasattr(self, "feifu") and isinstance(self.feifu, dict):
            for i in range(1,7):
                flags = self.feifu.get(i, {}).get(phase_key, {})
                feifu[i] = {"飞": bool(flags.get("飞")), "伏": bool(flags.get("伏"))}
        # 注解汇总
        anno = {}
        for i,key in enumerate(["初爻","二爻","三爻","四爻","五爻","六爻"], start=1):
            br = najia.get(key, "")
            elem = ELEMENT_MAP.get(br, "")
            # —— 基础注解 ——
            base = {
                "地支": br,
                "五行": elem,
                "六亲": liuqin.get(i, ""),
                "六神": self.liushen.get(i, "") if hasattr(self, "liushen") else "",
                "世": (i == shiying.get("世爻")),
                "应": (i == shiying.get("应爻")),
                "动": moving.get(i, False),
                "旬空": (i in xk_pos),
                "值月": (br == getattr(self, "yue_jian", "")),
                "值日": (br == getattr(self, "ri_jian", "")),
                "旺衰": self._wangshuai(elem, getattr(self, "yue_jian", "")) if elem else "",
                "飞伏": feifu.get(i, {"飞": False, "伏": False})
            }
                
            # —— 力量计算（可配置） ——
            ws = base["旺衰"]
            score = 0.0
            score += POWER_CONFIG["旺衰权重"].get(ws, 0.0)
            w = POWER_CONFIG["标记权重"]
            if base["动"]:   score += w.get("动", 0.0)
            if base["旬空"]: score += w.get("旬空", 0.0)
            if base["值月"]: score += w.get("值月", 0.0)
            if base["值日"]: score += w.get("值日", 0.0)
            if base["世"]:   score += w.get("世", 0.0)
            if base["应"]:   score += w.get("应", 0.0)
            base["power"] = round(score, 3)
            anno[i] = base

        return anno


    def get_plate(self):
        """
        返回排盘结果，结果以格式化 JSON 字符串输出，
        包含起卦时间、当前八字、本卦、变卦、世应、卦宫、纳甲、六亲和六神。
        """
        def attach_texts(hex_name: str, hex_type: str):
            data = (self.yaoci_dataset or {}).get(hex_name, {})
            guaci = data.get("卦辞", "") if isinstance(data, dict) else ""
            yaoci = data.get("爻辞", {}) if isinstance(data, dict) else {}

            # 逐爻装配爻辞与自动断语
            per_yao = {}
            for i in range(1, 7):
                line_text = ""
                if isinstance(yaoci, dict):
                    line_text = yaoci.get(str(i), "")

                per_yao[i] = {"爻辞": line_text}
            
            # 叠加工程化注解
            detail = self._annotate_lines(hex_type)
            for i in range(1,7):
                per_yao[i]["注解"] = detail.get(i, {})     

            return guaci, per_yao

        ben_guaci, ben_lines = attach_texts(self.bengua["卦名"] if self.bengua else "", "ben")
        bian_guaci, bian_lines = attach_texts(self.biangua["卦名"] if self.biangua else "", "bian")

        # 汇总总力量（可选字段）
        try:
            ben_power_total  = round(sum(ben_lines[i]["注解"].get("power", 0) for i in range(1,7)), 3)
        except Exception:
            ben_power_total = None
        try:
            bian_power_total = round(sum(bian_lines[i]["注解"].get("power", 0) for i in range(1,7)), 3)
        except Exception:
            bian_power_total = None

        return json.dumps({
            "起卦时间": self.dt.strftime("%Y-%m-%d %H:%M"),
            "当前八字": self.current_ganzhi,
            "月建": self.yue_jian,
            "日建": self.ri_jian,
            "旬": self.xun_info,
            "本卦": {
                "爻值": self.ben,
                "阴阳爻串": ''.join(str(b) for b in self.ben),  # 自下而上
                "动爻位": [i+1 for i,y in enumerate(self.yao_list) if y in ("老阴","老阳")],
                "上卦": self.ben_upper,
                "下卦": self.ben_lower,
                "卦名": self.bengua["卦名"] if self.bengua else "未知",
                "卦资料": self.bengua,
                "卦宫": self.gua_gong_ben,
                "纳甲": self.najia_ben,
                "世应": self.shiying_ben,
                "六亲":self.liuqin_ben,
                "飞伏": self._sparse_feifu("本卦"),
                "旬空位": self.xunkong_pos_ben,
                "月建位": self.yuejian_pos_ben,
                "日建位": self.rijian_pos_ben,
                "经文": {"卦辞": ben_guaci},
                "爻注解": ben_lines
            },
            "变卦": {
                "爻值": self.bian,
                "阴阳爻串": ''.join(str(b) for b in self.bian),  # 自下而上
                "上卦": self.bian_upper,
                "下卦": self.bian_lower,
                "卦名": self.biangua["卦名"] if self.biangua else "未知",
                "卦资料": self.biangua,
                "卦宫": self.gua_gong_bian,  
                "纳甲": self.najia_bian,
                "六亲":self.liuqin_bian,
                "世应": self.shiying_bian,
                "飞伏": self._sparse_feifu("变卦"),
                "旬空位": self.xunkong_pos_bian,
                "月建位": self.yuejian_pos_bian,
                "日建位": self.rijian_pos_bian,
                "经文": {"卦辞": bian_guaci},
                "爻注解": bian_lines
            },
            
            "六神": self.liushen,
            "力量总分": {"本卦": ben_power_total, "变卦": bian_power_total}
        }, ensure_ascii=False, indent=2)


def validate_eight_palaces():
    # 1) 每卦只归一宫
    seen = {}
    for palace, names in EIGHT_PALACES_BY_NAME.items():
        for n in names:
            if n in seen:
                raise ValueError(f"卦名重复归属: {n} 同时在 {seen[n]} 和 {palace}")
            seen[n] = palace
    # 2) 覆盖完整性（可选）：是否覆盖全部64卦
    full_names = {h["卦名"] for h in HEXAGRAMS_FULL}
    not_covered = full_names - set(seen.keys())
    if not_covered:
        raise ValueError(f"未覆盖的卦名: {sorted(not_covered)}")
    print("八宫校验通过：无重复且覆盖完整")


# validate hexagram binary once at import/init (早发现手工数据出错)
validate_hexagram_binary()


import random
import time

def random_yao_coin_method(seed=None):
    """
    铜钱法随机生成六个爻值
    返回如 ["少阴", "老阳", "少阳", "老阴", "少阳", "老阳"]
    
    概率分布：老阴(12.5%) 少阳(37.5%) 少阴(37.5%) 老阳(12.5%)
    
    Args:
        seed: 可选随机种子，用于结果可复现
    
    Returns:
        list: 六个爻值的列表
    """
    yao_types = ["老阴", "少阳", "少阴", "老阳"]
    weights = [1, 3, 3, 1]  # 铜钱法权重
    
    rnd = random.Random(seed) if seed is not None else random
    return [rnd.choices(yao_types, weights=weights)[0] for _ in range(6)]


def random_yao_dayan_method(seed=None):
    """
    大衍筮法随机生成六个爻值（朱熹概率版本）
    返回如 ["少阴", "老阳", "少阳", "老阴", "少阳", "老阳"]
    
    概率分布：老阴(6.25%) 少阳(31.25%) 少阴(43.75%) 老阳(18.75%)
    
    Args:
        seed: 可选随机种子，用于结果可复现
    
    Returns:
        list: 六个爻值的列表
    """
    yao_types = ["老阴", "少阳", "少阴", "老阳"] 
    weights = [1, 5, 7, 3]  # 大衍筮法权重（朱熹概率）
    
    rnd = random.Random(seed) if seed is not None else random
    return [rnd.choices(yao_types, weights=weights)[0] for _ in range(6)]


def random_yao_time_method(time_str=None):
    """
    时间起卦法生成六个爻值（基于梅花易数）
    
    Args:
        time_str: 时间字符串，格式如 "202504141530"，如不提供则使用当前时间
    
    Returns:
        list: 六个爻值的列表
        
    注意：此方法为确定性起卦，相同时间总是产生相同结果
    """
    if time_str is None:
        # 使用当前时间
        now = datetime.datetime.now()
        time_str = now.strftime("%Y%m%d%H%M")
    
    # 解析时间
    year = int(time_str[:4]) % 100  # 取年份后两位
    month = int(time_str[4:6])
    day = int(time_str[6:8])
    hour = int(time_str[8:10])
    
    # 计算上卦和下卦
    upper_gua_num = (year + month + day) % 8
    if upper_gua_num == 0:
        upper_gua_num = 8
        
    lower_gua_num = (year + month + day + hour) % 8
    if lower_gua_num == 0:
        lower_gua_num = 8
    
    # 计算变爻
    dong_yao = (year + month + day + hour) % 6
    if dong_yao == 0:
        dong_yao = 6
    
    # 八卦数字对应的二进制表示（1为阳爻，0为阴爻）
    gua_patterns = {
        1: [1, 1, 1],  # 乾
        2: [0, 0, 0],  # 坤
        3: [1, 0, 0],  # 震
        4: [0, 1, 0],  # 坎
        5: [0, 0, 1],  # 艮
        6: [0, 1, 1],  # 巽
        7: [1, 0, 1],  # 离
        8: [1, 1, 0]   # 兑
    }
    
    # 构建本卦（下卦在前，上卦在后）
    bengua_bits = gua_patterns[lower_gua_num] + gua_patterns[upper_gua_num]
    
    # 生成变卦（变爻位置从下往上数，1表示初爻）
    biangua_bits = bengua_bits.copy()
    biangua_bits[dong_yao - 1] = 1 - biangua_bits[dong_yao - 1]  # 爻变
    
    # 将二进制转换为爻值
    def bits_to_yao(bits, dong_pos):
        yao_list = []
        for i, bit in enumerate(bits):
            pos = i + 1
            if pos == dong_pos:
                # 动爻
                yao_list.append("老阳" if bit == 1 else "老阴")
            else:
                # 静爻  
                yao_list.append("少阳" if bit == 1 else "少阴")
        return yao_list
    
    return bits_to_yao(bengua_bits, dong_yao)


def random_yao_dayan(seed=None):
    """
    随机生成六个爻值 - 当前采用铜钱法概率分布
    返回如 ["少阴", "老阳", "少阳", "老阴", "少阳", "老阳"]
    
    概率分布说明：
    - 当前使用：铜钱法 [1:3:3:1] 对应 [老阴:少阳:少阴:老阳]
    - 备注：函数名包含"dayan"是历史原因，实际使用铜钱法概率
    - 铜钱法概率：老阴(12.5%) 少阳(37.5%) 少阴(37.5%) 老阳(12.5%)
    - 大衍筮法概率：老阴(6.25%) 少阳(31.25%) 少阴(43.75%) 老阳(18.75%)
    
    详细说明请参考：docs/六爻起卦方法详解.md

    Args:
        seed: 可选随机种子，用于结果可复现。不传则使用全局随机源。
              使用 random.Random(seed) 独立发生器，避免污染全局状态。
    
    Returns:
        list: 六个爻值的列表，每个元素为 "老阴"/"少阳"/"少阴"/"老阳" 之一
    """
    yao_types = ["老阴", "少阳", "少阴", "老阳"]
    #weights = [1, 5, 7, 3]  # 顺序对应上面四个 # 这个是大衍筮法的权重 （这里用的是朱熹概率，还有另外两种概率分别是能算出来4和5的，也就是五运六气里的另外两个值）
    weights = [1, 3, 3, 1]  # 顺序对应上面四个 # 这个是铜钱卦对应的权重

    rnd = random.Random(seed) if seed is not None else random # 能保证同一 seed 产生相同序列

    # 维持原有“逐次抽取”的行为（而非一次性 k=6），以与历史结果尽量一致
    return [rnd.choices(yao_types, weights=weights)[0] for _ in range(6)]

def random_yao_auto(method="coin", seed=None, time_str=None):
    """
    自动选择起卦方法生成六个爻值
    
    Args:
        method: 起卦方法，可选值：
                - "coin": 铜钱法（默认）
                - "dayan": 大衍筮法  
                - "time": 时间起卦法
        seed: 随机种子（仅对coin和dayan方法有效）
        time_str: 时间字符串（仅对time方法有效），格式如"202504141530"
    
    Returns:
        list: 六个爻值的列表
    """
    if method == "coin":
        return random_yao_coin_method(seed)
    elif method == "dayan":
        return random_yao_dayan_method(seed)
    elif method == "time":
        return random_yao_time_method(time_str)
    else:
        raise ValueError(f"不支持的起卦方法: {method}。支持的方法：coin, dayan, time")



if __name__ == '__main__':
    # 使用argparse处理命令行参数
    parser = argparse.ArgumentParser(description='六爻排盘分析工具')
    parser.add_argument('--session-id', required=True, help='会话ID')
    parser.add_argument('--current-time', required=True, help='当前时间，用于起卦，格式为YYYYMMDDHHMM（如202508151402）')
    parser.add_argument('--output-path', required=True, help='输出JSON文件的完整路径')
    parser.add_argument('--method', choices=['coin', 'dayan', 'time'], default='coin', help='起卦方法：coin(铜钱法)、dayan(大衍筮法)、time(时间起卦法)')
    parser.add_argument('--seed', type=int, help='随机种子，用于复现随机结果')

    args = parser.parse_args()

    session_id = args.session_id
    current_time = args.current_time
    output_path = args.output_path
    method = args.method
    seed = args.seed

    # 参数验证
    if len(current_time) != 12 or not current_time.isdigit():
        print("六爻错误: current-time 格式不正确，应为12位数字 YYYYMMDDHHMM")
        exit(1)

    # 显示当前设置
    method_name = {'coin': '铜钱法', 'dayan': '大衍筮法', 'time': '时间起卦法'}[method]
    #print(f"正在分析会话 {session_id} 的六爻，起卦方法为：{method_name}")
    if seed is not None:
        print(f"[随机种子] {seed}")

    # 生成六个爻值（随机起卦）
    if method == "time":
        example_yao = random_yao_auto("time")
    else:
        example_yao = random_yao_auto(method, seed=seed)

    # 创建六爻盘
    ly = LiuYao(current_time, example_yao)

    # 获取盘面数据
    plate_data = json.loads(ly.get_plate())

    # 构建结果
    result = {
        "session_id": session_id,
        "当前时间": current_time,
        "起卦方法": method_name,
        "随机种子": seed,
        "六爻数据": plate_data
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 保存结果到指定文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [SUCCESS] [排盘] 六爻分析完成，排盘方法为：{method_name}。")
    #print(f"起卦结果: {plate_data.get('本卦', {}).get('卦名', '未知')}")

    # 调用示例:
    # python 六爻.py --session-id session_20250906_demo --current-time 202509061000 --output-path sessions/session_20250906_demo/palettes/六爻.json --method coin
    # python 六爻.py --session-id session_20250906_demo --current-time 202509061000 --output-path sessions/session_20250906_demo/palettes/六爻.json --method dayan --seed 12345