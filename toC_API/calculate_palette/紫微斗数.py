"""
Python implementation of 紫微斗数排盘 based strictly on 安星诀, with 星曜亮度表.
Compatible with Python 3.9.18 / IPython 8.15.0.
"""
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


from dateutil.relativedelta import relativedelta
from pprint import pprint

# 天干地支序列
FULL_STEMS    = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
FULL_BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

# 定寅首诀映射：年干→寅宫起始天干
YIN_START_MAP = {
    ("甲","己"): "丙",
    ("乙","庚"): "戊",
    ("丙","辛"): "庚",
    ("丁","壬"): "壬",
    ("戊","癸"): "甲",
}

# 十二宫名称
PALACE_NAMES = [
    "命宫","兄弟","夫妻","子女","财帛","疾厄",
    "迁移","交友","官禄","田宅","福德","父母"
]

# 命主、身主对照表
MINGZHU_MAP = {
    '子': '贪狼', '丑': '巨门', '亥': '巨门',
    '寅': '禄存', '戌': '禄存',
    '卯': '文曲', '酉': '文曲',
    '巳': '武曲', '未': '武曲',
    '辰': '廉贞', '申': '廉贞',
    '午': '破军'
}
SHENZHU_MAP = {
    '子': '火星', '午': '火星',
    '丑': '天相', '未': '天相',
    '寅': '天梁', '申': '天梁',
    '卯': '天同', '酉': '天同',
    '巳': '天机', '亥': '天机',
    '辰': '文昌', '戌': '文昌'
}


# ———— 起紫微星诀 ————
# “六五四三二，酉午亥辰丑”——取日柱日支为 n，
# 用局数（BUREAU_TABLE 中已经计算好的那些“水二局”、“金四局”……）
# 除以 n，商数 S，余数 R：
#   若 R>0，则紫微在：从“酉”宫开始，顺行前进 S 宫 + 1 宫（余数 R 对应的那一宫）
#   若 R==0，则紫微在“酉午亥辰丑”序列的第 S 项
ZIWEI_SEQUENCE = ["酉","午","亥","辰","丑"]
# 日支取值映射：地支 -> 日数（取 1–12）
DAYBRANCH_TO_NUM = {
    '子':1,'丑':2,'寅':3,'卯':4,'辰':5,'巳':6,
    '午':7,'未':8,'申':9,'酉':10,'戌':11,'亥':12
}


# 四化映射：年干→(化禄,化权,化科,化忌)
# 南派四化映射：年干 → (化禄, 化权, 化科, 化忌)
TRANSFORMS = {
    '甲': ('廉贞', '破军', '武曲', '太阳'),
    '乙': ('天机', '天梁', '紫微', '太阴'),
    '丙': ('天同', '天机', '文昌', '廉贞'),
    '丁': ('太阴', '天同', '天机', '巨门'),
    '戊': ('贪狼', '太阴', '右弼', '天机'),
    '己': ('武曲', '贪狼', '天梁', '文曲'),
    '庚': ('太阳', '武曲', '太阴', '天同'),
    '辛': ('巨门', '太阳', '文曲', '文昌'),
    '壬': ('天梁', '紫微', '左辅', '武曲'),
    '癸': ('破军', '巨门', '太阴', '贪狼'),
}

# 星曜亮度表
BRIGHTNESS = {
    '紫微': {'寅':'旺','卯':'旺','辰':'得','巳':'旺','午':'庙','未':'庙','申':'旺','酉':'旺','戌':'得','亥':'旺','子':'平','丑':'庙'},
    '天机': {'寅':'得','卯':'旺','辰':'利','巳':'平','午':'庙','未':'陷','申':'得','酉':'旺','戌':'利','亥':'平','子':'庙','丑':'陷'},
    '太阳': {'寅':'旺','卯':'庙','辰':'旺','巳':'旺','午':'旺','未':'得','申':'得','酉':'陷','戌':'不','亥':'陷','子':'陷','丑':'不'},
    '武曲': {'寅':'得','卯':'利','辰':'庙','巳':'平','午':'旺','未':'庙','申':'得','酉':'利','戌':'庙','亥':'平','子':'旺','丑':'庙'},
    '天同': {'寅':'利','卯':'平','辰':'平','巳':'庙','午':'陷','未':'不','申':'旺','酉':'平','戌':'平','亥':'庙','子':'旺','丑':'不'},
    '廉贞':{'寅':'庙','卯':'平','辰':'利','巳':'陷','午':'平','未':'利','申':'庙','酉':'平','戌':'利','亥':'陷','子':'平','丑':'利'},
    '天府':{'寅':'庙','卯':'得','辰':'庙','巳':'得','午':'旺','未':'庙','申':'得','酉':'旺','戌':'庙','亥':'得','子':'庙','丑':'庙'},
    '太阴':{'寅':'旺','卯':'陷','辰':'陷','巳':'陷','午':'不','未':'不','申':'利','酉':'不','戌':'旺','亥':'庙','子':'庙','丑':'庙'},
    '贪狼':{'寅':'平','卯':'利','辰':'庙','巳':'陷','午':'旺','未':'庙','申':'平','酉':'利','戌':'庙','亥':'陷','子':'旺','丑':'庙'},
    '巨门':{'寅':'庙','卯':'庙','辰':'陷','巳':'旺','午':'旺','未':'不','申':'庙','酉':'庙','戌':'陷','亥':'旺','子':'旺','丑':'不'},
    '天相':{'寅':'庙','卯':'陷','辰':'得','巳':'得','午':'庙','未':'得','申':'庙','酉':'陷','戌':'得','亥':'得','子':'庙','丑':'庙'},
    '天梁':{'寅':'庙','卯':'庙','辰':'庙','巳':'陷','午':'庙','未':'旺','申':'陷','酉':'得','戌':'庙','亥':'陷','子':'庙','丑':'旺'},
    '七杀':{'寅':'庙','卯':'旺','辰':'庙','巳':'平','午':'旺','未':'庙','申':'庙','酉':'庙','戌':'庙','亥':'平','子':'旺','丑':'庙'},
    '破军':{'寅':'得','卯':'陷','辰':'旺','巳':'平','午':'庙','未':'旺','申':'得','酉':'陷','戌':'旺','亥':'平','子':'庙','丑':'旺'},
    '文昌':{'寅':'陷','卯':'利','辰':'得','巳':'庙','午':'陷','未':'利','申':'得','酉':'庙','戌':'陷','亥':'利','子':'得','丑':'庙'},
    '文曲':{'寅':'平','卯':'旺','辰':'得','巳':'庙','午':'陷','未':'旺','申':'得','酉':'庙','戌':'陷','亥':'旺','子':'得','丑':'庙'},
    '火星':{'寅':'庙','卯':'利','辰':'陷','巳':'得','午':'庙','未':'利','申':'陷','酉':'得','戌':'庙','亥':'利','子':'陷','丑':'得'},
    '铃星':{'寅':'庙','卯':'利','辰':'陷','巳':'得','午':'庙','未':'利','申':'陷','酉':'得','戌':'庙','亥':'利','子':'陷','丑':'得'},
    '擎羊':{'寅':'-','卯':'陷','辰':'庙','巳':'-','午':'陷','未':'庙','申':'-','酉':'陷','戌':'庙','亥':'-','子':'陷','丑':'庙'},
    '陀罗':{'寅':'陷','卯':'-','辰':'庙','巳':'陷','午':'-','未':'庙','申':'陷','酉':'-','戌':'庙','亥':'陷','子':'-','丑':'庙'},
    '地空': {'子':'陷','丑':'平','寅':'得','卯':'平','辰':'平','巳':'旺','午':'得','未':'陷','申':'平','酉':'平','戌':'得','亥':'旺'},
    '地劫': {'子':'陷','丑':'陷','寅':'平','卯':'平','辰':'陷','巳':'庙','午':'庙','未':'平','申':'庙','酉':'平','戌':'平','亥':'旺'},
}

# 对应时辰名称与时段
SHI_NAMES = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
TIME_RANGES = {
    '子':'23:00~00:59','丑':'01:00~02:59','寅':'03:00~04:59','卯':'05:00~06:59',
    '辰':'07:00~08:59','巳':'09:00~10:59','午':'11:00~12:59','未':'13:00~14:59',
    '申':'15:00~16:59','酉':'17:00~18:59','戌':'19:00~20:59','亥':'21:00~22:59'
}

# 五行局计算辅助
STEM_NUM   = {'甲':1,'乙':1,'丙':2,'丁':2,'戊':3,'己':3,'庚':4,'辛':4,'壬':5,'癸':5}
BRANCH_NUM = {'子':1,'午':1,'丑':1,'未':1,'寅':2,'申':2,'卯':2,'酉':2,'辰':3,'戌':3,'巳':3,'亥':3}
# 基础元素映射
ELEMENTS   = {1:'木',2:'金',3:'水',4:'火',5:'土'}

# 五行局专用局数映射
# 年干对应表行索引
# 地支对应表列索引
# 局数表格
STEM_ROW_MAP = {'甲':0,'乙':1,'丙':2,'丁':3,'戊':4,'己':0,'庚':1,'辛':2,'壬':3,'癸':4}
BRANCH_COL_MAP = {'子':0,'丑':0,'寅':1,'卯':1,'辰':2,'巳':2,'午':3,'未':3,'申':4,'酉':4,'戌':5,'亥':5}
BUREAU_TABLE = [
    ["水二局","火六局","木三局","土五局","金四局","火六局"],
    ["火六局","土五局","金四局","木三局","水二局","土五局"],
    ["土五局","木三局","水二局","金四局","火六局","木三局"],
    ["木三局","金四局","火六局","水二局","土五局","金四局"],
    ["金四局","水二局","土五局","火六局","木三局","水二局"],
]

# 年干阴阳判断
YANG_STEMS = set(['甲','丙','戊','庚','壬'])

# ---------- 算法实现 ----------
class ZWChart:
    def __init__(self, time_str: str, gender: str):
        # 解析出生时间
        dt = datetime.datetime.strptime(time_str, "%Y%m%d%H%M")
        # 子时不分早晚，统一归入前一日（传统做法：子时23:00~00:59皆算前一日）
        if dt.hour in (0, 23):
            dt -= datetime.timedelta(days=1)
        self.dt, self.gender = dt, gender

        # 四柱
        ts = TungShing(self.dt)
        yg, yb = ts.year8Char
        mg, mb = ts.month8Char
        dg, db = ts.day8Char
        hg, hb = ts.twohour8Char
        
        self.lunar = ts

        self.pillars = {
            'year':  (yg, yb, FULL_STEMS.index(yg),  FULL_BRANCHES.index(yb)),
            'month': (mg, mb, FULL_STEMS.index(mg),  FULL_BRANCHES.index(mb)),
            'day':   (dg, db, FULL_STEMS.index(dg),  FULL_BRANCHES.index(db)),
            'hour':  (hg, hb, FULL_STEMS.index(hg),  FULL_BRANCHES.index(hb))
        }

        # 大限方向：阳男阴女顺行，其他逆行
        self.dir_big = 1 if ((self.pillars['year'][0] in YANG_STEMS and self.gender=='male')
                            or (self.pillars['year'][0] not in YANG_STEMS and self.gender=='female')) else -1

        # 基本信息
        self.solarDate = f"{dt.year}-{dt.month}-{dt.day}"
        leap = '闰' if ts.isLunarLeapMonth else ''
        self.lunarDate = f"{ts.lunarYearCn}年{leap}{ts.lunarMonthCn}{ts.lunarDayCn}"
        self.chineseDate = f"{yg}{yb} {mg}{mb} {dg}{db} {hg}{hb}"
        self.time = f"{hb}时"
        self.timeRange = TIME_RANGES[hb]
        self.note = {}

        # 十二宫
        self.palaces = self._calc_palaces()

        # 大限 & 小限
        self._calc_dayun()
        
        # 主星、辅星
        self._assign_main_series()
        self._assign_aux_star()
        
        # 杂曜
        self._assign_adject_star()
        self._assign_extended_shens()        
        
        # 命宫四化
        # 年干对应四化字典
        # __init__ 里
        self._assign_transformations('生年', yg, src_idx=None)


        # 根据“宫干四化（化忌）→星曜所在宫”的飞入关系，给目标宫写入“来因宫”
        self._assign_laiyin()

    def currentTime(self, time_str: str):
        # 解析当前时间
        dtNow = datetime.datetime.strptime(time_str, "%Y%m%d%H%M")
        # 动态时间同样不分早晚子时，统一归入前一日
        if dtNow.hour in (0, 23):
            dtNow -= datetime.timedelta(days=1)
        self.dtNow = dtNow

        # 四柱
        tsNow = TungShing(self.dtNow)
        ygNow, ybNow = tsNow.year8Char
        mgNow, mbNow = tsNow.month8Char
        dgNow, dbNow = tsNow.day8Char
        hgNow, hbNow = tsNow.twohour8Char
        
        self.lunarNow = tsNow

        self.pillarsNow = {
            'year':  (ygNow, ybNow),
            'month': (mgNow, mbNow),
            'day':   (dgNow, dbNow),
            'hour':  (hgNow, hbNow)
        }

        # 基本信息
        self.solarDateNow = f"{dtNow.year}-{dtNow.month}-{dtNow.day}"
        leap = '闰' if tsNow.isLunarLeapMonth else ''
        self.lunarDateNow = f"{tsNow.lunarYearCn}年{leap}{tsNow.lunarMonthCn}{tsNow.lunarDayCn}"
        self.chineseDateNow = f"{ygNow}{ybNow} {mgNow}{mbNow} {dgNow}{dbNow} {hgNow}{hbNow}"
        
        self._assign_dynamic_stars()
        

    def _shi_order(self) -> int:
        h = self.dt.hour
        if 23 <= h <= 23:  # 23:00-23:59 视为子
            return 1
        return (h + 1)//2 + 1   # 01:00→2, ... 21:00→12
    
    # 辅助：根据地支找到宫位索引
    def find_idx(self, branch):
        return next(i for i, p in enumerate(self.palaces) if p['宫支'] == branch)
    
    def _calc_palaces(self):

        # 1. 定寅首诀：年干映射起始天干
        start = next(v for ks,v in YIN_START_MAP.items() if self.pillars['year'][0] in ks)
        sb = FULL_BRANCHES.index('寅')
        si = FULL_STEMS.index(start)

        # 生成十二宫干支序列，自寅首起顺行
        stems_branches = []
        for j in range(12):
            idx_b = (sb + j) % 12
            idx_s = (si + j) % 10
            stems_branches.append((FULL_STEMS[idx_s], FULL_BRANCHES[idx_b]))

        # 2. 安命身宫诀：计算命宫(虚)与身宫位置
        month_idx = FULL_BRANCHES.index(self.pillars['month'][1])
        mo = (month_idx - sb) % 12
        shi_off = self._shi_order() - 1
        ming = (mo - shi_off) % 12  # 命宫在序列中的索引
        shen = (mo + shi_off) % 12  # 身宫在序列中的索引

        # 构建宫位字典列表，先按干支序列
        palaces = []
        for j, (stem, branch) in enumerate(stems_branches):
            palaces.append({
                '宫干': stem,
                '宫支': branch,
                '是否身宫': j == shen,
                '是否命宫': j == ming,
                '主星': [],
                '辅星': [],
                '杂曜': [],
                '神煞': [],                
                '流曜': [],
                '小限': [],
                '大限': None,
                '宫名': '',
                '备注': []
            })

        # 3. 定十二宫诀：由命宫逆数安排宫名
        for i, name in enumerate(PALACE_NAMES):
            idx = (ming - i) % 12
            palaces[idx]['宫名'] = name

        # 4. 五行局
        ming_branch = palaces[ming]['宫支']
        row = STEM_ROW_MAP.get(self.pillars['year'][0])
        col = BRANCH_COL_MAP[ming_branch]
        self.ming_branch = ming_branch
        self.fiveElementsClass = BUREAU_TABLE[row][col]

        # —— 安命主 & 身主 —— #
        # 命主：根据命宫的地支来取
        star_m = MINGZHU_MAP.get(palaces[ming]['宫支'], '')
        self.note['命主'] = star_m

        # 身主：根据出生年的地支来取
        year_branch = self.pillars['year'][1]
        star_s = SHENZHU_MAP.get(year_branch, '')
        self.note['身主'] = star_s

        return palaces

    def _assign_main_series(self):
        
        palaces = self.palaces
        
        # 紫微安置按“日支序数÷局数（先余后商）”：子=1, ... 亥=12
        # 以农历日数安紫微（先余后商）：n = 农历日(1~30)
        n = int(self.lunar.lunarDay)
        m = int({'水二局':2,'木三局':3,'金四局':4,'土五局':5,'火六局':6}[self.fiveElementsClass])
        # 先余后商：以“日数 ÷ 局数” （“先余后商；见数无余起虎口”）
        S, R = divmod(n, m)  # n=农历日号, m=局数(2/3/4/5/6)

        if R == 0:
            base = FULL_BRANCHES.index('寅')             # 虎口=寅
            zw_idx = (base + (S-1)) % 12  ## 从寅起，顺数“商数”到位（1-based）
            zw_branch = FULL_BRANCHES[zw_idx]
        else:
            start_by_bureau = {6:'酉',5:'午',4:'亥',3:'辰',2:'丑'}  # 六五四三二
            base = FULL_BRANCHES.index(start_by_bureau[m])
            yu_idx = (base + (R-1)) % 12                 # 先落“余数宫”
            zw_idx = (yu_idx + S) % 12                   # 再顺数“商数”
            zw_branch = FULL_BRANCHES[zw_idx]

        # 安放紫微（不做额外 -1 偏移）
        zw_pos = next(i for i, p in enumerate(palaces) if p["宫支"] == zw_branch)
        palaces[zw_pos]["主星"].append({"名称":"紫微", "亮度": BRIGHTNESS["紫微"][zw_branch]})
    
        # 逆布星系
        stars = ["天机", "太阳", "武曲", "天同", "廉贞"]
        offsets = [1, 3, 4, 5, 8]  # 隔一宫安太阳
        for star, offset in zip(stars, offsets):
            pos = (zw_pos - offset) % 12
            palaces[pos]["主星"].append({"名称": star, "亮度": BRIGHTNESS[star][palaces[pos]["宫支"]]})
        
        # —— 天府星与紫微星的相对位置 —— #
        TF_MAP = {
            '丑':'卯','卯':'丑',
            '未':'酉','酉':'未',
            '午':'戌','戌':'午',
            '子':'辰','辰':'子',
            '巳':'亥','亥':'巳',
            '寅':'寅','申':'申',
        }
        
        tf_branch = TF_MAP[zw_branch]
        tf_pos = next(i for i,p in enumerate(palaces)
                      if p['宫支']==tf_branch)
        
        # 3. 安放天府
        palaces[tf_pos]['主星'].append({
            '名称': '天府',
            '亮度': BRIGHTNESS['天府'][tf_branch]
        })
    
        # 4. 安天府诸星：顺行铺布
        #    “天府顺行有太阴，贪狼而后巨门临，
        #     随来天相天梁继，七杀空三是破军。”
        stars = ['太阴','贪狼','巨门','天相','天梁','七杀','破军']
        offsets = [1, 2, 3, 4, 5, 6, 10]
        for star, offset in zip(stars, offsets):
            pos = (tf_pos + offset) % 12
            palaces[pos]["主星"].append({"名称": star, "亮度": BRIGHTNESS[star][palaces[pos]["宫支"]]})

        self.palaces = palaces
        
    def _assign_aux_star(self):
        palaces = self.palaces

        # —— 辅弼、昌曲、空劫诀 —— #
        # 辰上顺正寻左辅（生月），戌上逆正右弼当（生月）
        # 辰上顺时文曲位（生时），戌上逆时觅文昌（生时）
        # 亥上子时顺安劫（生时），逆回便是地空亡（生时）

        # 左辅／右弼（以生月为时序基准，取“辰”与“戌”）
        month_no = int(self.lunar.lunarMonth)  # 1..12

        pos_zuofu = (self.find_idx('辰') + (month_no - 1)) % 12
        pos_youbi = (self.find_idx('戌') - (month_no - 1)) % 12
        palaces[pos_zuofu]['辅星'].append({"名称":'左辅'})
        palaces[pos_youbi]['辅星'].append({"名称":'右弼'})

        # 文曲／文昌（以生时为时序基准，同辰戌，1-based→统一减1）
        pos_wenqu    = (self.find_idx('辰') + (self._shi_order() - 1)) % 12
        pos_wenchang = (self.find_idx('戌') - (self._shi_order() - 1)) % 12
        palaces[pos_wenqu]['辅星'].append({"名称": '文曲', "亮度": BRIGHTNESS['文曲'][palaces[pos_wenqu]["宫支"]]})
        palaces[pos_wenchang]['辅星'].append({"名称": '文昌', "亮度": BRIGHTNESS['文昌'][palaces[pos_wenchang]["宫支"]]})

        # 地劫／地空（以子时为零点，顺回产生地劫，逆回产生地空；1-based→统一减1）
        pos_jie  = (self.find_idx('亥') + (self._shi_order() - 1)) % 12
        pos_kong = (self.find_idx('亥') - (self._shi_order() - 1)) % 12
        palaces[pos_jie]['辅星'].append({"名称":'地劫', "亮度": BRIGHTNESS['地劫'][palaces[pos_jie]["宫支"]]})
        palaces[pos_kong]['辅星'].append({"名称":'地空', "亮度": BRIGHTNESS['地空'][palaces[pos_kong]["宫支"]]})


        # —— 魁钺诀 —— #
        # 按年干取两支：前者为天魁，后者为天钺
        KUIYUE = {
            ('甲','戊','庚'): ('丑','未'),
            ('乙','己'):       ('子','申'),
            ('辛',):           ('午','寅'),
            ('壬','癸'):       ('卯','巳'),
            ('丙','丁'):       ('亥','酉'),
        }
        yg = self.pillars['year'][0]
        for stems, (b1,b2) in KUIYUE.items():
            if yg in stems:
                palaces[self.find_idx(b1)]['辅星'].append({"名称":'天魁'})
                palaces[self.find_idx(b2)]['辅星'].append({"名称":'天钺'})
                break


        # —— 禄存、羊刃、陀罗诀 —— #
        LUCUN = {
            '甲':'寅','乙':'卯','丙':'巳','戊':'巳',
            '丁':'午','己':'午','庚':'申','辛':'酉',
            '壬':'亥','癸':'子'
        }
        stem = self.pillars['year'][0]
        lu_branch = LUCUN[stem]
        i_lu = self.find_idx(lu_branch)
        palaces[i_lu]['辅星'].append({"名称":'禄存'})
        palaces[(i_lu+1)%12]['辅星'].append({"名称": '擎羊', "亮度": BRIGHTNESS['擎羊'][(palaces[(i_lu+1)%12]["宫支"])]})
        palaces[(i_lu-1)%12]['辅星'].append({"名称": '陀罗', "亮度": BRIGHTNESS['陀罗'][(palaces[(i_lu-1)%12]["宫支"])]})


        # —— 天马诀 —— #
        # 以生年地支分组，直接点出天马所在支
        TM = {
            ('寅','午','戌'): '申',
            ('申','子','辰'): '寅',
            ('巳','酉','丑'): '亥',
            ('亥','卯','未'): '巳',
        }
        yb = self.pillars['year'][1]
        for group, tm_b in TM.items():
            if yb in group:
                palaces[self.find_idx(tm_b)]['辅星'].append({"名称":'天马'})
                break


        # —— 火星、铃星诀 —— #
        # 先按年支取两宫，再以子时为 0，顺数至生时
        FB = {
            ('申','子','辰'): ('寅','戌'),
            ('寅','午','戌'): ('丑','卯'),
            ('巳','酉','丑'): ('卯','戌'),
            ('亥','卯','未'): ('酉','戌'),
        }
        for group, (base_fire, base_bell) in FB.items():
            if yb in group:
                pos_fire = (self.find_idx(base_fire) + (self._shi_order() - 1)) % 12
                pos_bell = (self.find_idx(base_bell) + (self._shi_order() - 1)) % 12
                palaces[pos_fire]['辅星'].append({"名称": '火星', "亮度": BRIGHTNESS['火星'][palaces[pos_fire]["宫支"]]})
                palaces[pos_bell]['辅星'].append({"名称": '铃星', "亮度": BRIGHTNESS['铃星'][palaces[pos_bell]["宫支"]]})
                break

        self.palaces = palaces


    def _assign_adject_star(self):
        """
        根据南派安星诀动态匹配三十七杂耀，将每颗星的 '名称' 添加到对应宫位的 '杂耀' 列表中。
        仅保留 '名称' 字段。
        """
        palaces = self.palaces
        
        # 全局地支序列
        branches = FULL_BRANCHES
        
        #  安 1. 台辅 2. 封诰 诀
        # 台辅：午宫起，顺行到时支
        start = '午'
        place = branches[(branches.index(start) + self.pillars['hour'][3]) % 12]
        palaces[self.find_idx(place)]['杂曜'].append('台辅')

        
        # 封诰：寅宫起，从子分逆行到时支
        start = '寅'
        place = branches[(branches.index(start) - self.pillars['hour'][3]) % 12]
        palaces[self.find_idx(place)]['杂曜'].append('封诰')

        # ---- 安 3. 天刑 4. 天姚 诀 ----
        # 按农历月序（正月为1），正月起顺至生月
        lunar_month_num = int(self.lunar.lunarMonth)
        # 天刑：酉宫起
        idx = branches.index('酉')
        target = branches[(idx + (lunar_month_num - 1)) % 12]
        palaces[self.find_idx(target)]['杂曜'].append('天刑')

        # 天姚：丑宫起
        idx = branches.index('丑')
        target = branches[(idx + (lunar_month_num - 1)) % 12]
        palaces[self.find_idx(target)]['杂曜'].append('天姚')
        

        #  安解神诀（5. 月解）
        month_num = int(self.lunar.lunarMonth)
        if month_num in (1,2): place = '申'
        elif month_num in (3,4): place = '戌'
        elif month_num in (5,6): place = '子'
        elif month_num in (7,8): place = '寅'
        elif month_num in (9,10): place = '辰'
        else: place = '午'
        palaces[self.find_idx(place)]['杂曜'].append('解神-月解神')


        # 安 6. 天巫 诀 
        if month_num in (1,5,9): place = '巳'
        elif month_num in (2,6,10): place = '申'
        elif month_num in (3,7,11): place = '寅'
        else: place = '亥'
        palaces[self.find_idx(place)]['杂曜'].append('天巫')

        
        
        # 7. 安天月诀
        mapping = {1:'戌',2:'巳',3:'辰',4:'寅',5:'未',6:'卯',7:'亥',8:'未',9:'寅',10:'午',11:'戌',12:'寅'}
        place = mapping.get(month_num)
        palaces[self.find_idx(place)]['杂曜'].append('天月')



        # 8. 安阴煞诀
        if month_num in (1,7): place='寅'
        elif month_num in (2,8): place='子'
        elif month_num in (3,9): place='戌'
        elif month_num in (4,10): place='申'
        elif month_num in (5,11): place='午'
        else: place='辰'
        palaces[self.find_idx(place)]['杂曜'].append( '阴煞')


        # 安截路空亡诀 -- 安 9. 截空 10. 空亡 诀 11 12   
        # 也有说阳宫为截路，阴宫为空亡
        groups = {
            ('甲','己'): ('申', '酉'), ('乙','庚'): ('午', '未'), ('丙','辛'): ('辰', '巳'),
            ('丁','壬'): ('寅', '卯'), ('戊','癸'): ('子', '丑')
        }
        for stems, b in groups.items():
            if self.pillars['year'][0] in stems:
                palaces[self.find_idx(b[1])]['杂曜'].append('截空')
                palaces[self.find_idx(b[1])]['杂曜'].append('旬空') # 阳宫

                # 同位补上“空亡”（便于使用方言名）
                palaces[self.find_idx(b[1])]['杂曜'].append('空亡')

                palaces[self.find_idx(b[0])]['杂曜'].append('副截')
                palaces[self.find_idx(b[0])]['杂曜'].append('副旬') # 阴宫
                break

        # 安13 天官 14天福贵人诀
        mapping = {
            '甲':('未','酉'),'乙':('辰','申'),'丙':('巳','子'),
            '丁':('寅','亥'),'戊':('卯','卯'),'己':('酉','寅'),
            '庚':('亥','午'),'辛':('酉','巳'),'壬':('戌','午'),'癸':('午','巳')
        }
        pair = mapping.get(self.pillars['year'][0])
        if pair:
            palaces[self.find_idx(pair[0])]['杂曜'].append('天官')  # 以生肖反推宫支
            palaces[self.find_idx(pair[1])]['杂曜'].append('天福')



        # 15 安天空诀 生年支顺数的前一位就是。
        yg_branch = self.pillars['year'][1]
        idx = branches.index(yg_branch)
        place = branches[(idx + 1 ) % 12]
        palaces[self.find_idx(place)]['杂曜'].append( '天空')


        # 16 安天哭天虚诀
        # 天哭：午宫起逆至生年支
        start='午'
        pos = (branches.index(start) -2 - idx) % 12
        palaces[pos]['杂曜'].append('天哭')

        # 17 天虚：午宫起顺至生年支
        pos = (branches.index(start) -2 + idx) % 12
        palaces[pos]['杂曜'].append('天虚')


        # 18. 安龙池凤阁诀
        # 龙池：辰宫起顺至生年支
        start='辰'
        pos = (branches.index(start) -2 + idx) % 12
        palaces[pos]['杂曜'].append('龙池')

        # 19 凤阁：戌宫起逆至生年支
        start='戌'
        pos = (branches.index(start) -2 - idx) % 12
        palaces[pos]['杂曜'].append('凤阁')

        # ---- 安红鸾天喜诀 ----
        # 20 红鸾：卯宫起，逆行至年支
        hl_place = (self.find_idx('卯') - self.pillars['year'][3]) % 12
        palaces[hl_place]['杂曜'].append( '红鸾')

        # 21 天喜：红鸾对宫
        opp = (hl_place -6) % 12
        palaces[opp]['杂曜'].append( '天喜')
        
        # ---- 安孤辰寡宿诀 ----
        # 22 孤辰：寅卯辰年生安巳宫；巳午未年生安申宫；申酉戌年生安亥宫；亥子丑年生安寅宫
        # 23 寡宿：参考孤辰逆位
        if self.pillars['year'][1] in ['寅', '卯', '辰']:
            palaces[self.find_idx('巳')]['杂曜'].append('孤辰')
            palaces[self.find_idx('丑')]['杂曜'].append('寡宿')
        
        elif self.pillars['year'][1] in ['巳', '午', '未']:
            palaces[self.find_idx('申')]['杂曜'].append('孤辰')
            palaces[self.find_idx('辰')]['杂曜'].append('寡宿')
        elif self.pillars['year'][1] in ['申', '酉', '戌']:
            palaces[self.find_idx('亥')]['杂曜'].append('孤辰')
            palaces[self.find_idx('未')]['杂曜'].append('寡宿')
        else:
            palaces[self.find_idx('寅')]['杂曜'].append('孤辰')
            palaces[self.find_idx('戌')]['杂曜'].append('寡宿')
        
# =============================================================================
#         # 24. 安蜚廉诀  
# =============================================================================
        yg_branch = self.pillars['year'][1]
        if yg_branch in ['子','丑','寅']:
            place='申'
        elif yg_branch in ['卯','辰','巳']:
            place='巳'
        elif yg_branch in ['午','未','申']:
            place='寅'
        else:
            place='亥'
        palaces[self.find_idx(place)]['杂曜'].append('蜚廉')


        # 25. 安破碎诀
        if yg_branch in ['子','午','卯','酉']:
            place='巳'
        elif yg_branch in ['寅','申','巳','亥']:
            place='酉'
        else:
            place='丑'
        palaces[self.find_idx(place)]['杂曜'].append('破碎')


        # 26. 安华盖诀
        if yg_branch in ['子','辰','申']:
            place='辰'
        elif yg_branch in ['丑','巳','酉']:
            place='丑'
        elif yg_branch in ['寅','午','戌']:
            place='戌'
        else:
            place='未'
        palaces[self.find_idx(place)]['杂曜'].append('华盖')


        # 27. 安咸池诀
        if yg_branch in ['子','辰','申']:
            place='酉'
        elif yg_branch in ['丑','巳','酉']:
            place='午'
        elif yg_branch in ['寅','午','戌']:
            place='卯'
        else:
            place='子'
        palaces[self.find_idx(place)]['杂曜'].append('咸池')


        # 28. 安天才天寿诀
        # 天才：命宫起子顺至年支
        ming_branch = next(p['宫支'] for p in palaces if p['是否命宫'])
        start = ming_branch
        
        yg_branch = self.pillars['year'][1]
        idx = branches.index(yg_branch)
        pos = (branches.index(start) -2 + idx) % 12
        palaces[pos]['杂曜'].append('天才')


        # 29 天寿：身宫起子顺至年支
        shen_branch = next(p['宫支'] for p in palaces if p['是否身宫'])
        start = shen_branch
        
        pos = (branches.index(start) -2 + idx) % 12
        palaces[pos]['杂曜'].append('天寿')


        # 30. 安三台八座诀（以日支序数起布，不用农历日数）
        day_branch = self.pillars['day'][1]
        day_order = DAYBRANCH_TO_NUM[day_branch]  # 子=1 ... 亥=12

        # 三台：左辅宫位起顺至日支
        start_branch = None
        for palace in palaces:
            for star in palace['辅星']:
                if isinstance(star, dict) and star.get('名称') == '左辅':
                    start_branch = palace['宫支']
                    break
            if start_branch:
                break
        if start_branch:
            pos = (branches.index(start_branch) + (day_order - 1)) % 12
            palaces[pos]['杂曜'].append('三台')

        # 31. 八座：右弼宫位起逆至日支
        start_branch = None
        for palace in palaces:
            for star in palace['辅星']:
                if isinstance(star, dict) and star.get('名称') == '右弼':
                    start_branch = palace['宫支']
                    break
            if start_branch:
                break
        if start_branch:
            pos = (branches.index(start_branch) - (day_order - 1)) % 12
            palaces[pos]['杂曜'].append('八座')

        # 32. 恩光：文昌宫位起逆至日支
        start_branch = None
        for palace in palaces:
            for star in palace['辅星']:
                if isinstance(star, dict) and star.get('名称') == '文昌':
                    start_branch = palace['宫支']
                    break
            if start_branch:
                break
        if start_branch:
            pos = (branches.index(start_branch) - (day_order - 1)) % 12
            palaces[(pos - 1) % 12]['杂曜'].append('恩光')


        # 33. 天贵：文曲宫位起逆至日支
        start_branch = None
        for palace in palaces:
            for star in palace['辅星']:
                if isinstance(star, dict) and star.get('名称') == '文曲':
                    start_branch = palace['宫支']
                    break
            if start_branch:
                break
        if start_branch:
            pos = (branches.index(start_branch) - (day_order - 1)) % 12
            palaces[(pos - 1) % 12]['杂曜'].append('天贵')


        # ———— 安34 天厨诀 ————
        # 甲丁食蛇口（巳）、乙戊辛马方（午）、丙从鼠口得（子）、
        # 己食于猴房（申）、庚食虎头上（寅）、壬鸡（酉）、癸猪堂（亥）
        year_to_branch = {
            '甲': '巳', '丁': '巳',
            '乙': '午', '戊': '午', '辛': '午',
            '丙': '子',
            '己': '申',
            '庚': '寅',
            '壬': '酉',
            '癸': '亥'
        }
        stem0 = self.pillars['year'][0]
        if stem0 in year_to_branch:
            branch_tc = year_to_branch[stem0]
            idx_tc = self.find_idx(branch_tc)
            palaces[idx_tc]['杂曜'].append('天厨')


        # 35天伤 36天使
        for p in palaces:
            if p['宫名'] == '交友':
                p['杂曜'].append( '天伤')
            elif p['宫名'] == '疾厄':
                p['杂曜'].append('天使')

        # 37 月德（按月支→天干，再落到宫干相同的宫）
        # 寅午戌→丙；申子辰→壬；亥卯未→甲；巳酉丑→庚
        yue_de_map = {('寅','午','戌'):'丙', ('申','子','辰'):'壬',
                      ('亥','卯','未'):'甲', ('巳','酉','丑'):'庚'}
        mb = self.pillars['month'][1]
        for grp, stem in yue_de_map.items():
            if mb in grp:
                try:
                    idx_md = next(i for i,p in enumerate(palaces) if p['宫干']==stem)
                    palaces[idx_md]['杂曜'].append('月德')
                except StopIteration:
                    pass
                break

        self.palaces = palaces



# =============================================================================
# 代码中多出的（不在神煞列表里的）
# 副截
# 
# 副旬
# 
# 这两颗杂曜是您在“截空／旬空”诀中额外加入的字段，神煞列表并未提及。是我按照文墨天机中所提到的样式主观添加的。
# =============================================================================


    def _assign_extended_shens(self):
        """
        安排  共计 24 颗神煞：
         长生十二神
         博士十二神
        """
        palaces = self.palaces
        # 辅助：根据地支找到宫位索引
        def find_idx(branch):
            return next(i for i, p in enumerate(palaces) if p['宫支'] == branch)

        # 41. 安长生十二神
        zhangsheng_map = {
            '水二局': '申', '木三局': '亥', '金四局': '巳',
            '土五局': '申', '火六局': '寅'
        }
        order_ls = ['长生','沐浴','冠带','临官','帝旺','衰','病','死','墓','绝','胎','养']
        start_branch = zhangsheng_map.get(self.fiveElementsClass)
        if start_branch:
            idx0 = find_idx(start_branch)
            # 顺行或逆行
            direction = self.dir_big
            
            for i, name in enumerate(order_ls):
                pos = (idx0 + i*direction) % 12
                palaces[pos]['神煞'].append(name)


        # 42. 安博士十二神
        # 从禄存起
        # 找禄存所在宫 阳男阴女顺行
        for p in palaces:
            if any(isinstance(s, dict) and s.get('名称')=='禄存' for s in p['辅星']):
                idx0 = palaces.index(p)
                break
        order_bs = ['博士','力士','青龙','小耗','将军','奏书','飞廉','喜神','病符','大耗','伏兵','官符']
        direction = self.dir_big
        
        for i, name in enumerate(order_bs):
            pos = (idx0 + i*direction) % 12
            palaces[pos]['神煞'].append(name)

        self.palaces = palaces


    def _assign_dynamic_stars(self):
        """
        安排 共计 24 颗神煞（流曜）：
          流年岁前十二神
          流年将前十二神
        并将——
         • 流年命宫
         • 大运命宫
         • 小限命宫
        ——写入对应宫位的 '备注' 中。
        """
        palaces = self.palaces
    
        # 计算虚岁：
        age = (self.dtNow.year - self.dt.year
               - ((self.dtNow.month, self.dtNow.day) < (self.dt.month, self.dt.day))) +1
        
        self.note['虚岁'] = age
        # —— 4. 标记“小限命宫” —— #
        for p in palaces:
            sx = p.get('小限', '')
            if sx and str(age) in sx.split(','):
                p['备注'].append('小限')
                #p['备注'].append({'小限': True})
                break

        dayun_gan = None
        dayun_branch = None
        for idx_p, p in enumerate(palaces):
            dr = p.get('大限', '')
            if dr:
                lo, hi = map(int, dr.split('-'))
                if lo <= age <= hi:
                    p['备注'].append('大运命宫')
                    dayun_gan = p['宫干']
                    dayun_branch = p['宫支']
                    break

        # —— 4. 注入四化 —— #
        # 大运命宫四化：
        if dayun_gan:
            self._assign_transformations('大运', dayun_gan, src_idx=idx_p)
            
            # 排大运各个宮
            for j, name in enumerate(PALACE_NAMES):
                idx = (idx_p + self.dir_big*j) % 12
                palaces[idx]['备注'].append( '大运' + name) 
        
            # —— 大运昌/曲：沿用你对“流年昌/曲”的起法（巳起顺、酉起逆），但以大运干计算 —— #
            start = '巳'
            place = FULL_BRANCHES[(FULL_BRANCHES.index(start) + FULL_STEMS.index(dayun_gan)) % 12]
            palaces[self.find_idx(place)]['流曜'].append('大运文昌')
            start = '酉'
            place = FULL_BRANCHES[(FULL_BRANCHES.index(start) - FULL_STEMS.index(dayun_gan)) % 12]
            palaces[self.find_idx(place)]['流曜'].append('大运文曲')


        # —— 魁钺诀 —— #
        # 按流年年干取两支：前者为天魁，后者为天钺
        KUIYUE = {
            ('甲','戊','庚'): ('丑','未'),
            ('乙','己'):       ('子','申'),
            ('辛',):           ('午','寅'),
            ('壬','癸'):       ('卯','巳'),
            ('丙','丁'):       ('亥','酉'),
        }
        yg = dayun_gan
        for stems, (b1,b2) in KUIYUE.items():
            if yg in stems:
                palaces[self.find_idx(b1)]['流曜'].append('大运天魁')
                palaces[self.find_idx(b2)]['流曜'].append('大运天钺')
                break


        # —— 禄存、羊刃、陀罗诀 —— #
        LUCUN = {
            '甲':'寅','乙':'卯','丙':'巳','戊':'巳',
            '丁':'午','己':'午','庚':'申','辛':'酉',
            '壬':'亥','癸':'子'
        }
        stem = yg = dayun_gan
        lu_branch = LUCUN[stem]
        i_lu = self.find_idx(lu_branch)
        palaces[i_lu]['流曜'].append('大运禄存')
        palaces[(i_lu+1)%12]['流曜'].append('大运擎羊')
        palaces[(i_lu-1)%12]['流曜'].append('大运陀罗')


        # —— 天马诀 —— #
        # 以流年地支分组，直接点出天马所在支
        TM = {
            ('寅','午','戌'): '申',
            ('申','子','辰'): '寅',
            ('巳','酉','丑'): '亥',
            ('亥','卯','未'): '巳',
        }
        yb = dayun_branch
        for group, tm_b in TM.items():
            if yb in group:
                palaces[self.find_idx(tm_b)]['流曜'].append('大运天马')
                break                
 
        # 天喜：红鸾对宫
        hl_place = (self.find_idx('卯') - FULL_BRANCHES.index(dayun_branch)) % 12
        palaces[hl_place]['流曜'].append( '大运红鸾')
        
        opp = (hl_place -6) % 12
        palaces[opp]['流曜'].append( '大运天喜')

        # —— 年解（流年解神）——
        # 年解（流年解神）属流曜，“自戌起子逆至流年太岁”。
        # 计算位移：以“子”为 0 点，至流年太岁（year_branch）的偏移
        offset = (FULL_BRANCHES.index(self.pillarsNow['year'][1])
                  - FULL_BRANCHES.index('子')) % 12
        place_idx = (self.find_idx('戌') - offset) % 12

        # 年解是“流年小星”，但实务上常直接归入“小星/杂曜”以便观阅
        palaces[place_idx]['流曜'].append( '年解/流年解神')

 
        # —— 48. 安流昌流曲诀 —— #
        # 流昌：始于巳宫，甲乙顺行；流曲：始于酉宫，甲乙逆行（中州派之外可忽略流曲）
        # 这里只标记“流昌起始宫”和（如需）“流曲起始宫”
        # —— 48. 安流昌流曲诀（最终：按“流年年干”）——
        start = '巳'
        place = FULL_BRANCHES[(FULL_BRANCHES.index(start) + FULL_STEMS.index(self.pillarsNow['year'][0])) % 12]
        palaces[self.find_idx(place)]['流曜'].append('流年文昌')
        start = '酉'
        place = FULL_BRANCHES[(FULL_BRANCHES.index(start) - FULL_STEMS.index(self.pillarsNow['year'][0])) % 12]
        palaces[self.find_idx(place)]['流曜'].append('流年文曲')   
 
    
 
        # —— 1. 流年岁前十二神（标为 流曜） —— #
        year_branch = self.pillarsNow['year'][1]
        idx0 = self.find_idx(year_branch)

        order_ly = ['岁建','晦气','丧门','贯索','官符','小耗',
                    '大耗','龙德','白虎','天德','吊客','病符']
        for i, name in enumerate(order_ly):
            pos = (idx0 + i) % 12
            palaces[pos]['流曜'].append(name)

        # —— 2. 流年将前十二神（标为 流曜） —— #
        group_map = {
            ('寅','午','戌'): '午',
            ('申','子','辰'): '子',
            ('巳','酉','丑'): '酉',
            ('亥','卯','未'): '卯'
        }
        for grp, br in group_map.items():
            if year_branch in grp:
                idx1 = self.find_idx(br)
                break
        order_js = ['将星','攀鞍','岁驿','息神','华盖','劫煞',
                    '灾煞','天煞','指背','咸池','月煞','亡神']
        for i, name in enumerate(order_js):
            pos = (idx1 + i) % 12
            palaces[pos]['流曜'].append(name)

        # —— 3. 标记“大运命宫” —— #
        # 根据当前年龄在各宫 '大限' 范围内查找

        # 标记“流年命宫”（避免重复）
        if '流年命宫' not in palaces[idx0]['备注']:
            palaces[idx0]['备注'].append('流年命宫')
       
        # 流年命宫四化：
        year_gan = self.pillarsNow['year'][0]
        self._assign_transformations('流年', year_gan,src_idx=idx0)
        
        # 排流年各个宮
        for j, name in enumerate(PALACE_NAMES):
            idx = (idx0 + self.dir_big*j) % 12
            palaces[idx]['备注'].append( '流年' + name)
        
        # —— 魁钺诀 —— #
        # 按流年年干取两支：前者为天魁，后者为天钺
        KUIYUE = {
            ('甲','戊','庚'): ('丑','未'),
            ('乙','己'):       ('子','申'),
            ('辛',):           ('午','寅'),
            ('壬','癸'):       ('卯','巳'),
            ('丙','丁'):       ('亥','酉'),
        }
        yg = self.pillarsNow['year'][0]
        for stems, (b1,b2) in KUIYUE.items():
            if yg in stems:
                palaces[self.find_idx(b1)]['流曜'].append('流年天魁')
                palaces[self.find_idx(b2)]['流曜'].append('流年天钺')
                break


        # —— 禄存、羊刃、陀罗诀 —— #
        LUCUN = {
            '甲':'寅','乙':'卯','丙':'巳','戊':'巳',
            '丁':'午','己':'午','庚':'申','辛':'酉',
            '壬':'亥','癸':'子'
        }
        stem = yg = self.pillarsNow['year'][0]
        lu_branch = LUCUN[stem]
        i_lu = self.find_idx(lu_branch)
        palaces[i_lu]['流曜'].append('流年禄存')
        palaces[(i_lu+1)%12]['流曜'].append('流年擎羊')
        palaces[(i_lu-1)%12]['流曜'].append('流年陀罗')


        # —— 天马诀 —— #
        # 以流年地支分组，直接点出天马所在支
        TM = {
            ('寅','午','戌'): '申',
            ('申','子','辰'): '寅',
            ('巳','酉','丑'): '亥',
            ('亥','卯','未'): '巳',
        }
        yb = self.pillarsNow['year'][1]
        for group, tm_b in TM.items():
            if yb in group:
                palaces[self.find_idx(tm_b)]['流曜'].append('流年天马')
                break


        # 流年太岁
        ly_branch = self.pillarsNow['year'][1]
        
        # 天喜：红鸾对宫
        hl_place = (self.find_idx('卯') - FULL_BRANCHES.index(ly_branch)) % 12
        palaces[hl_place]['流曜'].append( '流年红鸾')
        
        opp = (hl_place -6) % 12
        # 调试输出移除
        palaces[opp]['流曜'].append( '流年天喜')
        
        start = self.find_idx(ly_branch)
        # 逆数到生月宫
        month_num = int(self.lunar.lunarMonth)

        # 再以此宫起子时，顺数至出生时辰 
        # 流年岁建起正月，逆逢生月顺回程，回程顺至生时止 （两端皆为 1-based，统一减 1）
        dou_pos = (start - (month_num - 1) + (self._shi_order() - 1)) % 12  # 1-based→统一减1（与 文墨天机 对齐）
        if '流年斗君/流斗/流月正月' not in palaces[dou_pos]['备注']:
            palaces[dou_pos]['备注'].append('流年斗君/流斗/流月正月')
        for j, name in enumerate(PALACE_NAMES):
            idx = (dou_pos + j) % 12
            palaces[idx]['备注'].append( f'流月{j+1}月')     


        # 按本出生 月 及出生 时辰，找到正月以后 顺时针 排流月。流月四化因派别不同会有差异，有些派别是直接按 宫干 飞化，有些派别是起 五虎遁 找天干。
        dou_month_pos = (dou_pos + self.lunarNow.lunarMonth -1) % 12
        for j, name in enumerate(PALACE_NAMES):
            idx = (dou_month_pos + j) % 12          
            palaces[idx]['备注'].append( '流月' + name)

        # —— 6. 定流日 —— #
        # 以流月所在宫（流年斗君所在宫）为初一，顺行十二宫，一日一宫，直至月底
        # 在盘中只记录“流日起始宫”
        dou_day_pos = (dou_month_pos + self.lunarNow.lunarDay -1 ) % 12
        if '流日所在' not in palaces[dou_day_pos]['备注']:
            palaces[dou_day_pos]['备注'].append('流日所在')

        # —— 7. 定流时 —— #
        # 在流日所在宫起子时，顺布十二宫，每一时辰占一宫
        dou_time_pos = (dou_day_pos + self.lunarNow.twohourNum - 1) % 12
        if '流时所在' not in palaces[dou_time_pos]['备注']:
            palaces[dou_time_pos]['备注'].append('流时所在')
        # —— 统一去重（备注/杂曜/流曜）
        for p in palaces:
            for key in ('备注','杂曜','流曜'):
                if isinstance(p.get(key), list):
                    p[key] = list(dict.fromkeys(p[key]))

        self.palaces = palaces
            
    def _calc_dayun(self):

        palaces = self.palaces
        
        # 确定起运年龄（根据五行局）
        start_age = {'水二局':2,'木三局':3,'金四局':4,'土五局':5,'火六局':6}[self.fiveElementsClass]

        ming_idx = next(i for i, p in enumerate(palaces) if p["是否命宫"])

        # 大限方向：阳男阴女顺行，其他逆行
        dir_big = self.dir_big
    
        # 计算大限年龄范围
        for i in range(12):
            if dir_big == 1:
                k = (i - ming_idx) % 12
            else:
                k = (ming_idx - i) % 12
            start = start_age + k * 10
            palaces[i]["大限"] = f"{start}-{start+9}"
    
        # 小限计算
        year_branch = self.pillars["year"][1]
        start_branch = next(v for keys, v in {
            ("寅","午","戌"): "辰", ("申","子","辰"): "戌",
            ("巳","酉","丑"): "未", ("亥","卯","未"): "丑"
        }.items() if year_branch in keys)
        start_idx = next(i for i, p in enumerate(palaces) if p["宫支"] == start_branch)
        dir_small = 1 if self.gender == "male" else -1
    
        for i in range(12):
            offset = ((i - start_idx) * dir_small) % 12
            base = 1 + offset
            ages = [str(base + y * 12) for y in range(10)]  # 显示前10个周期
            palaces[i]["小限"] = ",".join(ages)
        
        # —— 5. 安子斗 —— #
        # 生年太岁
        y_branch = self.pillars['year'][1]
        start = self.find_idx(y_branch)
        # 逆数到生月宫
        month_num = int(self.lunar.lunarMonth)

        # 再以此宫起子时，顺数至出生时辰（两端皆为 1-based，统一减 1）
        dou_pos = (start - (month_num - 1) + (self._shi_order() - 1)) % 12
        self.note['生年斗君_子斗'] = palaces[dou_pos]['宫支']

        # 新增：把“本命斗君/本命流月”排到各宫备注，呈现方式与流年斗君一致
        if '生年斗君/本命斗君/本命流月正月' not in palaces[dou_pos]['备注']:
            palaces[dou_pos]['备注'].append('生年斗君/本命斗君/本命流月正月')
        for j, name in enumerate(PALACE_NAMES):
            idx = (dou_pos + j) % 12
            palaces[idx]['备注'].append(f'本命{j+1}月')


        self.palaces = palaces


    def _assign_laiyin(self):
        """
        来因宫：按【宫干四化】之【化忌】飞入对应星曜所在宫；
        在被飞入的宫位备注里写入：来因宫：<来源宫名>（若多宫飞入则并列）
        """
        # 1) 把主星/常用辅星的位置建索引，便于查“某星在哪一宫”
        name_to_pos = {}
        for i, p in enumerate(self.palaces):
            for star in p['主星'] + p['辅星']:
                if isinstance(star, dict) and '名称' in star:
                    name_to_pos.setdefault(star['名称'], set()).add(i)
        # 2) 枚举每个“来源宫”的宫干 → 取‘化忌’所对应星名
        for src_idx, p in enumerate(self.palaces):
            gan = p['宫干']
            if gan not in TRANSFORMS:
                continue
            _, _, _, hua_ji_star = TRANSFORMS[gan]
            # 3) 该星在哪些宫：即为“被飞入”的目标宫
            for tgt_idx in name_to_pos.get(hua_ji_star, []):
                if tgt_idx == src_idx:
                    # 飞到本宫也算
                    self._feihua_mark(self.palaces[src_idx]['宫名'], gan, '化忌', hua_ji_star, src_idx=src_idx)
                text = f"来因宫：{self.palaces[src_idx]['宫名']}"
                if text not in self.palaces[tgt_idx]['备注']:
                    self.palaces[tgt_idx]['备注'].append(text)

        # 去重
        for p in self.palaces:
            p['备注'] = list(dict.fromkeys(p['备注']))


    def _append_note(self, idx, text):
        if text not in self.palaces[idx]['备注']:
            self.palaces[idx]['备注'].append(text)

    def _feihua_mark(self, source_label: str, gan: str, transform_type: str,
                    star_name: str, src_idx=None):
        """
        在目标宫写‘飞入’，在来源宫（若有）写‘飞出’，同宫则写‘自化’。
        source_label: '生年'/'大运'/'流年' 或 某来源宫名（如'父母'）
        gan: 触发的天干（年干/宫干/运干）
        transform_type: '化禄'/'化权'/'化科'/'化忌'
        star_name: 被化的星名（由 TRANSFORMS[干] 给出）
        src_idx: 若为宫干四化，给来源宫索引；若为生年/大运/流年，传 None
        """
        # 找到被化星出现的位置（主星/辅星都算“可落点”）
        tgt_idxs = set()
        for i, p in enumerate(self.palaces):
            if any(isinstance(s, dict) and s.get('名称') == star_name
                for s in (p['主星'] + p['辅星'])):
                tgt_idxs.add(i)
        if not tgt_idxs:
            return

        src_text = f"{source_label}[{gan}]" if gan else source_label

        for ti in tgt_idxs:
            if src_idx is None:
                # 生年/大运/流年：只在目标宫记“飞入”
                self._append_note(ti, f"⇐ 飞入：{src_text}·{transform_type} → {star_name}")
            else:
                if ti == src_idx:
                    self._append_note(ti, f"↻ 自化：{src_text}·{transform_type} → {star_name}")
                else:
                    src_name = self.palaces[src_idx]['宫名']
                    self._append_note(src_idx, f"→ 飞出：{src_name}[{gan}]·{transform_type} → {star_name}@{self.palaces[ti]['宫名']}")
                    self._append_note(ti,       f"⇐ 飞入：{src_name}[{gan}]·{transform_type} → {star_name}")


    def _assign_transformations(self, time_class: str, gan: str, src_idx=None):
        """
        南派四化星诀：
        self.transforms 已是 {'化禄': 星名, '化权': 星名, '化科': 星名, '化忌': 星名}
        在对应星的字典中添加 '化' 字段，不改变亮度。
        """
        HUA_KEYS = ['化禄', '化权', '化科', '化忌']
        transforms = dict(zip(HUA_KEYS, TRANSFORMS[gan]))

        for transform_type, star_name in transforms.items():
            # ① 给星体本身打属性（原逻辑不变）
            found = False
            for palace in self.palaces:
                for idx, star in enumerate(palace['主星']):
                    if isinstance(star, dict) and star.get('名称') == star_name:
                        palace['主星'][idx][time_class + '四化'] = transform_type
                        found = True
                        break
                if found: break
            if not found:
                for palace in self.palaces:
                    for idx, star in enumerate(palace['辅星']):
                        if isinstance(star, dict) and star.get('名称') == star_name:
                            palace['辅星'][idx][time_class + '四化'] = transform_type
                            found = True
                            break
                    if found: break

            # ② 写“飞入/飞出/自化”备注（新逻辑）
            self._feihua_mark(
                source_label=('生年' if time_class=='生年' else time_class),
                gan=gan,
                transform_type=transform_type,
                star_name=star_name,
                src_idx=src_idx  # 生年/流年/大运传 None 或对应命宫索引
            )
    
    def get_chart(self):
        return {
            '阳历日期':self.solarDate,'农历日期':self.lunarDate,'四柱':self.chineseDate,
            '时辰':self.time,'时段':self.timeRange,'五行局':self.fiveElementsClass,
            '备注': self.note,'十二宫':self.palaces
        }

if __name__ == '__main__':
    # 使用argparse处理命令行参数
    parser = argparse.ArgumentParser(description='紫微斗数排盘分析工具')
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
        print("紫微错误: birth-string 格式不正确，应为12位数字 YYYYMMDDHHMM")
        sys.exit(1)

    if len(current_time) != 12 or not current_time.isdigit():
        print("紫微错误: current-time 格式不正确，应为12位数字 YYYYMMDDHHMM")
        sys.exit(1)

    #print(f"正在分析会话 {session_id} 的紫微斗数...")

    # 本命盘
    natal = ZWChart(birth_string, gender=gender)
    natal_chart = natal.get_chart()

    # 加入当前时间的动态流曜、斗君等（不改变另存的本命数据）
    dyn = ZWChart(birth_string, gender=gender)
    dyn.currentTime(current_time)
    dynamic_chart = dyn.get_chart()

    result = {
        "session_id": session_id,
        "出生时间": birth_string,
        "当前时间": current_time,
        "性别": gender,
        "本命盘": natal_chart,
        "当前盘": dynamic_chart,
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 保存结果到指定文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [SUCCESS] [排盘] 紫微斗数分析完成。")

    # 调用示例:
    # python 紫微斗数.py --session-id session_20250906_demo --birth-string 199001010000 --gender male --current-time 202509061000 --output-path sessions/session_20250906_demo/palettes/紫微斗数.json