# -*- coding: utf-8 -*-
"""
严格口径的 cnlunar“替身”：
- 年柱：立春分界（分秒级）
- 月柱：以“节”交节时刻分界（分秒级）
- 日柱：晚子时=23:00 起算“次日”的日柱
其余字段/方法：与原 cnlunar 完全一致（通过转发）。
参考：官方 README 字段/示例；节气时刻以 HKO/Beijing(UTC+8) 口径。 
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Any
from zoneinfo import ZoneInfo

# 依赖原 cnlunar 与 sxtwl（寿星天文历）
import cnlunar as _cn
import sxtwl as _sx


# —— 基础常量 —— #
GAN = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
ZHI = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
JQMC = ["冬至","小寒","大寒","立春","雨水","惊蛰","春分","清明","谷雨",
        "立夏","小满","芒种","夏至","小暑","大暑","立秋","处暑","白露",
        "秋分","寒露","霜降","立冬","小雪","大雪"]
# 以“节”而非“中气”换月
_JIE_IDX = {JQMC.index(n) for n in ["立春","惊蛰","清明","立夏","芒种","小暑",
                                    "立秋","白露","寒露","立冬","大雪","小寒"]}


# —— 小工具 —— #
def _gz_str(gz) -> str:
    return GAN[gz.tg] + ZHI[gz.dz]

def _to_local(dt: datetime, tz: str) -> datetime:
    z = ZoneInfo(tz)
    return (dt if dt.tzinfo else dt.replace(tzinfo=z)).astimezone(z)

def _aware_to_naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)

def _term_on_day_in_rule_tz(y: int, m: int, d: int, rule_tz: str):
    """
    若该（rule_tz 口径的）公历日有节气：
      返回 (节气名, 交节时刻@rule_tz[aware], 交节时刻@UTC+8[aware])
    否则 None
    说明：_sx.JD2DD 输出按 UTC+8 给“年月日时分秒”，再转到 rule_tz。
    """
    day = _sx.fromSolar(y, m, d)
    if not day.hasJieQi():
        return None
    k = day.getJieQi()
    name = JQMC[k]
    t = _sx.JD2DD(day.getJieQiJD())
    cn8 = datetime(int(t.Y), int(t.M), int(t.D), int(t.h), int(t.m), 0,
                   tzinfo=ZoneInfo("Asia/Shanghai")) + timedelta(seconds=float(t.s))
    return (name, cn8.astimezone(ZoneInfo(rule_tz)), cn8)


class TungShing: # 严格口径的 cnlunar“替身”，通胜、也叫黄历、农历，我用了个有意思的名词
    """
    与 cnlunar.Lunar 同名同用法的“严格口径”包装器：
      - 位置参数/关键字参数与原类保持兼容（date, godType='8char', year8Char=...）
      - 额外可选 keyword：tz（输出/原库口径，默认 'Asia/Shanghai'）、
                         rule_tz（裁边口径，默认 'Asia/Shanghai'）
      - 属性与方法：除 year8Char/month8Char/day8Char 采“严格口径”
      
      夜子时(23:00–23:59)：且农历日数字在 23:00 同步滚动，整对象以“次日口径”转发（__getattr__ → 次日 _forward）
    """
    # --- 兼容原构造签名：date, godType='8char', year8Char=... --- #
    def __init__(self, date: datetime = None, *args, **kwargs):
        if date is None:
            date = datetime.now()

        # 额外可选：输出时区与裁边时区（默认都按 UTC+8）
        self._tz = kwargs.pop("tz", "Asia/Shanghai")
        self._rule_tz = kwargs.pop("rule_tz", "Asia/Shanghai")

        # 原库对象：注意其期望“本地 naive”
        dt_local = _to_local(date, self._tz)                 # aware@tz
        dt_naive = _aware_to_naive(dt_local)                 # naive@tz
        self._base = _cn.Lunar(dt_naive, *args, **kwargs)    # 保持原库参数兼容
        self.date = self._base.date                          # 与原库一致

        # —— 严格口径：年/月/日柱裁边（按 rule_tz） —— #
        dt_rule = _to_local(date, self._rule_tz)             # aware@rule_tz
        dt_rule_naive = _aware_to_naive(dt_rule)
        y8, m8, d8, hh8 = dt_rule.year, dt_rule.month, dt_rule.day, dt_rule.hour

        # —— 夜子时：构造“次日口径”的 forward 对象 —— #
        self._forward = self._base
        if hh8 == 23:
            alt_naive = _aware_to_naive(dt_local + timedelta(hours=1))  # +1h 的本地“naive”
            self._forward = _cn.Lunar(alt_naive, *args, **kwargs)       # 次日口径的整对象

        # 年柱：立春分界（分秒）
        self.year8Char = self._calc_year_gz_strict(y8, dt_rule_naive)

        # 月柱：以“节”交节分界（分秒）
        self.month8Char = self._calc_month_gz_strict(y8, m8, d8, dt_rule_naive)

        # 日柱：晚子时 23:00 起算“次日”（只影响日柱，不滚动农历日数字）
        self.day8Char = self._calc_day_gz_strict(hh8, dt_local, dt_naive)

        # 时柱：保持原库（常见口径即可）；若你要“早/晚子时联动日干”，可在此改写
        self.twohour8Char = self._base.twohour8Char

        # —— 农历日数字/中文纪日/闰月：夜子时同步滚动 —— #
        src = self._forward  # 夜子时用次日；平时用当日
        self.lunarYear   = src.lunarYear
        self.lunarMonth  = src.lunarMonth
        self.lunarDay    = src.lunarDay
        # 兼容不同版本的闰月命名
        if hasattr(src, "isLunarLeapMonth"):
            self.isLunarLeapMonth = src.isLunarLeapMonth
        if hasattr(src, "lunarIsLeapMonth"):
            self.lunarIsLeapMonth = src.lunarIsLeapMonth
        self.lunarYearCn  = src.lunarYearCn
        self.lunarMonthCn = src.lunarMonthCn
        self.lunarDayCn   = src.lunarDayCn

    # —— 内部：年柱（立春分界） —— #
    def _calc_year_gz_strict(self, y: int, dt_rule_naive: datetime) -> str:
        lichun = None  # (name, dt@rule, dt@cn8)
        for md in [(2, 3), (2, 4), (2, 5)]:
            info = _term_on_day_in_rule_tz(y, md[0], md[1], self._rule_tz)
            if info and info[0] == "立春":
                lichun = info
                break
        if lichun:
            _, lc_rule_aware, _ = lichun
            passed = dt_rule_naive >= _aware_to_naive(lc_rule_aware)
            # sxtwl 的 getYearGZ 默认以立春为界
            y_curr = _gz_str(_sx.fromSolar(y, 7, 1).getYearGZ())
            y_prev = _gz_str(_sx.fromSolar(y - 1, 7, 1).getYearGZ())
            return y_curr if passed else y_prev
        # 找不到立春（极少见，兜底用原库）
        return self._base.year8Char

    # —— 内部：月柱（交“节”分界） —— #
    def _calc_month_gz_strict(self, y: int, m: int, d: int, dt_rule_naive: datetime) -> str:
        day_obj = _sx.fromSolar(y, m, d)
        mgz = _gz_str(day_obj.getMonthGZ())
        if day_obj.hasJieQi():
            k = day_obj.getJieQi()
            info = _term_on_day_in_rule_tz(y, m, d, self._rule_tz)
            if info:
                _, t_rule, _ = info
                if (k in _JIE_IDX) and dt_rule_naive < _aware_to_naive(t_rule):
                    mgz = _gz_str(day_obj.before(1).getMonthGZ())
        return mgz

    # —— 内部：日柱（晚子时=23:00 起算“次日”） —— #
    def _calc_day_gz_strict(self, hour_rule: int,
                            dt_local_aware: datetime,
                            dt_naive_for_base: datetime) -> str:
        # 以“裁边时区”的 23 点作为判据；检测原库是否已在该时刻换日
        base = self._base.day8Char
        if hour_rule == 23:
            # 注意：要把“+1小时（真实时间）”换算到原库的 naive 口径
            alt_naive = _aware_to_naive(dt_local_aware + timedelta(hours=1))
            alt = _cn.Lunar(alt_naive, godType='8char', year8Char='beginningOfSpring')
            return alt.day8Char if alt.day8Char != base else base
        return base

    # —— 其余字段：一律从 “次日口径/当日口径” 的 forward 对象转发 —— #
    def __getattr__(self, name: str) -> Any:
        return getattr(self._forward, name)

    # —— 可选：把“今日精确交节时刻”暴露为两个便捷字段（不影响兼容性） —— #
    @property
    def termTodayExact_ruleTz(self) -> Optional[str]:
        y, m, d = _to_local(self.date, self._rule_tz).date().timetuple()[:3]
        info = _term_on_day_in_rule_tz(y, m, d, self._rule_tz)
        return info[1].isoformat() if info else None

    @property
    def termTodayExact_cn8(self) -> Optional[str]:
        y, m, d = _to_local(self.date, self._rule_tz).date().timetuple()[:3]
        info = _term_on_day_in_rule_tz(y, m, d, self._rule_tz)
        return info[2].isoformat() if info else None


# ======================== 自检 / 单元测试 ========================
if __name__ == "__main__":
    """
    重要边界的权威时刻（台北/香港时间=UTC+8）：
      - 2024 立春：2024-02-04 16:27   （CWA 2024）
      - 2025 立春：2025-02-03 22:10   （CWA 2025）
      - 2025 惊蛰：2025-03-05 16:07   （CWA 2025）
      - 2025 立秋：2025-08-07 13:52   （CWA 2025）
      - 2025 立冬：2025-11-07 12:04   （CWA 2025）
      - 2025 秋分（中气，非换月“节”）：2025-09-23 02:19（CWA 2025）
    """

    TAIPEI = ZoneInfo("Asia/Shanghai")   # HKT/TST 口径（UTC+8）
    LA     = ZoneInfo("America/Los_Angeles")

    def _same_forward_fields(a, b):
        """23–0 整体算次日：forward 对象应让一切对齐"""
        keys = [
            "lunarYear","lunarMonth","lunarDay",
            "lunarYearCn","lunarMonthCn","lunarDayCn",
            "day8Char","twohour8Char",
            "todaySolarTerms","nextSolarTerm","nextSolarTermDate","weekNo"
        ]
        for k in keys:
            if hasattr(a, k) and hasattr(b, k):
                va, vb = getattr(a, k), getattr(b, k)
                assert va == vb, f"{k} mismatch: {va} != {vb}"

    # ---------- A. 立春换“年柱”（分秒级） ----------
    # 2024 立春：2024-02-04 16:27 UTC+8
    t_before = datetime(2024, 2, 4, 16, 26, 30, tzinfo=TAIPEI)
    t_after  = datetime(2024, 2, 4, 16, 27, 30, tzinfo=TAIPEI)
    A = TungShing(t_before)
    B = TungShing(t_after)
    print("2024 立春前后 年柱：", A.year8Char, "=>", B.year8Char)
    assert A.year8Char != B.year8Char, "【2024】立春分界未切换年柱"

    # 2025 立春：2025-02-03 22:10 UTC+8
    t_before = datetime(2025, 2, 3, 22, 9, 50, tzinfo=TAIPEI)
    t_after  = datetime(2025, 2, 3, 22, 10, 30, tzinfo=TAIPEI) # 这里的边界是22：10不切换，22：11切换
    C = TungShing(t_before)
    D = TungShing(t_after)
    print("2025 立春前后 年柱：", C.year8Char, "=>", D.year8Char)
    assert C.year8Char != D.year8Char, "【2025】立春分界未切换年柱"

    # 跨时区（输出 tz=洛杉矶；裁边 rule_tz=UTC+8 不变）
    # 2025-02-03 22:10(UTC+8) ≙ 2025-02-03 06:10(PST)
    la_before = TungShing(datetime(2025, 2, 3, 6, 9, 30, tzinfo=LA), tz="America/Los_Angeles", rule_tz="Asia/Shanghai")
    la_after  = TungShing(datetime(2025, 2, 3, 6, 11, 00, tzinfo=LA), tz="America/Los_Angeles", rule_tz="Asia/Shanghai")
    print("跨区(洛杉矶) 立春前后 年柱：", la_before.year8Char, "=>", la_after.year8Char)
    assert la_before.year8Char != la_after.year8Char, "【跨区】立春分界未切换年柱"

    # ---------- B. “节”过换“月柱”（分秒级） ----------
    # 惊蛰 2025-03-05 16:07
    jz_pre  = TungShing(datetime(2025, 3, 5, 16, 6, 30, tzinfo=TAIPEI))
    jz_post = TungShing(datetime(2025, 3, 5, 16, 7, 30, tzinfo=TAIPEI))
    print("惊蛰前后 月柱：", jz_pre.month8Char, "=>", jz_post.month8Char)
    assert jz_pre.month8Char != jz_post.month8Char, "【惊蛰】前后月柱应切换"

    # 立秋 2025-08-07 13:52
    lq_pre  = TungShing(datetime(2025, 8, 7, 13, 51, 00, tzinfo=TAIPEI))
    lq_post = TungShing(datetime(2025, 8, 7, 13, 52, 00, tzinfo=TAIPEI))
    print("立秋前后 月柱：", lq_pre.month8Char, "=>", lq_post.month8Char)
    assert lq_pre.month8Char != lq_post.month8Char, "【立秋】前后月柱应切换"

    # 立冬 2025-11-07 12:04
    ld_pre  = TungShing(datetime(2025, 11, 7, 12, 3, 30, tzinfo=TAIPEI))
    ld_post = TungShing(datetime(2025, 11, 7, 12, 4, 30, tzinfo=TAIPEI))
    print("立冬前后 月柱：", ld_pre.month8Char, "=>", ld_post.month8Char)
    assert ld_pre.month8Char != ld_post.month8Char, "【立冬】前后月柱应切换"

    # 反例：中气“秋分” 2025-09-23 02:19 —— 不应触发换月
    qf_pre  = TungShing(datetime(2025, 9, 23, 2, 18, 30, tzinfo=TAIPEI))
    qf_post = TungShing(datetime(2025, 9, 23, 2, 20, 00, tzinfo=TAIPEI))
    print("秋分前后 月柱（不切换）：", qf_pre.month8Char, "=>", qf_post.month8Char)
    assert qf_pre.month8Char == qf_post.month8Char, "【秋分】不应切换月柱（只在“节”换月）"

    # ---------- C. 23–0 整体算“次日”（整对象前滚） ----------
    def check_2300_block(y, m, d):
        # 23:30 vs 次日 00:30 —— 全部“转发字段”一致
        e = TungShing(datetime(y, m, d, 23, 30, tzinfo=TAIPEI))
        f = TungShing(datetime(y, m, d,  0, 30, tzinfo=TAIPEI) + timedelta(days=1))
        print(f"[{y}-{m:02d}-{d:02d}] 23:30 vs 次日00:30：日柱 {e.day8Char}/{f.day8Char}")
        _same_forward_fields(e, f)

        # 22:59 与 23:00 —— 23:00 已前滚，应与“次日00:30”一致，而不同于 22:59
        p2259 = TungShing(datetime(y, m, d, 22, 59, tzinfo=TAIPEI))
        p2300 = TungShing(datetime(y, m, d, 23,  0, tzinfo=TAIPEI))
        _same_forward_fields(p2300, f)  # 23:00 ≈ 次日 00:30
        # 不必强求“数字+1”，只要与次日一致即可；但至少要不同于 22:59
        changed = (
            (p2259.lunarDay, p2259.lunarDayCn, p2259.day8Char)
            != (p2300.lunarDay, p2300.lunarDayCn, p2300.day8Char)
        )
        assert changed, "22:59→23:00 未体现“夜子时前滚”"

    # 覆盖：普通日、节气日、中气日、年界附近
    check_2300_block(2025, 1, 20)  # 普通日
    check_2300_block(2025, 2, 18)  # 雨水日（当日有节气）
    check_2300_block(2025, 9, 23)  # 秋分日（中气）
    check_2300_block(2025, 12, 21) # 冬至日（中气）
    check_2300_block(2025, 8, 7)   # 立秋日（节），23:30 已在节后

    # 23:30（2/3，立春已过）与次日 00:30 的“年柱”一致；且与立春前夜 21:30 不同
    e = TungShing(datetime(2025, 2, 3, 23, 30, tzinfo=TAIPEI))
    f = TungShing(datetime(2025, 2, 4,  0, 30, tzinfo=TAIPEI))
    pre = TungShing(datetime(2025, 2, 3, 21, 30, tzinfo=TAIPEI))
    print("立春当夜 23:30/次日00:30 年柱：", e.year8Char, "/", f.year8Char, "；立春前 21:30 年柱：", pre.year8Char)
    assert e.year8Char == f.year8Char and pre.year8Char != e.year8Char, "立春夜：年柱应已切到新年"

    print("All strict boundary tests passed ✅")
