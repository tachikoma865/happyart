#!/usr/bin/env python3
"""
開運日カレンダーの計算エンジン

暦の日付は「記憶で書かない」のが鉄則なので、天文計算と暦法のルールから導出する。
そのうえで、検証済みの2026年7月・8月の実データと突き合わせて答え合わせをする
（`python3 koyomi_calc.py --verify`）。

計算するもの:
  干支（60日周期）      … 甲子の日・寅の日・巳の日・己巳の日
  一粒万倍日            … 節月 × 十二支
  天赦日                … 節月 × 干支
  新月・満月            … 天文計算（Meeus）
  六曜（大安など）      … 旧暦月 + 旧暦日

出典・検証に使った実データ:
  https://uic.jp/luckyday/2026/07/  https://uic.jp/luckyday/2026/08/
  https://bestcalendar.jp/2026/7/moon  https://bestcalendar.jp/2026/8/moon
"""

import math
import sys
from datetime import date, datetime, timedelta

JST_OFFSET = 9.0 / 24.0

JIKKAN = "甲乙丙丁戊己庚辛壬癸"
JUNISHI = "子丑寅卯辰巳午未申酉戌亥"

# 干支の基準日：2026-08-18 が甲子（UIC 2026年8月カレンダーで確認済み）
KANSHI_EPOCH = date(2026, 8, 18)

ROKUYO = ["大安", "赤口", "先勝", "友引", "先負", "仏滅"]

# 節月ごとの一粒万倍日にあたる十二支
# 節月は「立春から」「啓蟄から」…という、二十四節気の“節”で区切る月
ICHIRYU_BY_SETSUGETSU = {
    1: "丑午",   # 立春〜
    2: "酉寅",   # 啓蟄〜
    3: "子卯",   # 清明〜
    4: "卯辰",   # 立夏〜
    5: "巳午",   # 芒種〜
    6: "午酉",   # 小暑〜
    7: "子未",   # 立秋〜
    8: "卯申",   # 白露〜
    9: "酉午",   # 寒露〜
    10: "亥子",  # 立冬〜
    11: "卯子",  # 大雪〜
    12: "卯子",  # 小寒〜
}

# 天赦日：季節ごとに決まった干支の日
# 春(立春〜)=戊寅、夏(立夏〜)=甲午、秋(立秋〜)=戊申、冬(立冬〜)=甲子
TENSHA = {"spring": "戊寅", "summer": "甲午", "autumn": "戊申", "winter": "甲子"}

# 節入りの黄経（度）。節月1（立春）から順に。
SETSU_LONGITUDES = [315, 345, 15, 45, 75, 105, 135, 165, 195, 225, 255, 285]


# ---------------------------------------------------------------
# ユリウス日
# ---------------------------------------------------------------

def to_jd(y, m, d, frac=0.0):
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d + b - 1524.5 + frac)


def from_jd(jd):
    jd += 0.5
    z = math.floor(jd)
    f = jd - z
    if z >= 2299161:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        z += 1 + alpha - alpha // 4
    b = z + 1524
    c = math.floor((b - 122.1) / 365.25)
    d_ = math.floor(365.25 * c)
    e = math.floor((b - d_) / 30.6001)
    day = b - d_ - math.floor(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    di = int(math.floor(day))
    return year, month, di, day - di


# ---------------------------------------------------------------
# 太陽の見かけの黄経（節気の判定に使う）
# ---------------------------------------------------------------

def sun_longitude(jd):
    t = (jd - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m)
         + (0.019993 - 0.000101 * t) * math.sin(2 * m)
         + 0.000289 * math.sin(3 * m))
    true_long = l0 + c
    omega = math.radians(125.04 - 1934.136 * t)
    return (true_long - 0.00569 - 0.00478 * math.sin(omega)) % 360.0


def solve_sun_longitude(target, jd_guess):
    """太陽黄経が target 度になる時刻（JD, UT）を二分法で求める"""
    lo, hi = jd_guess - 20, jd_guess + 20

    def diff(jd):
        return ((sun_longitude(jd) - target + 180) % 360) - 180

    flo = diff(lo)
    for _ in range(100):
        mid = (lo + hi) / 2
        fm = diff(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
        if hi - lo < 1e-6:
            break
    return (lo + hi) / 2


def solar_terms(year):
    """その年の節入り（節月の始まり）をJSTの日付で返す"""
    out = {}
    for i, lon in enumerate(SETSU_LONGITUDES, start=1):
        approx = to_jd(year, 2, 4) + (i - 1) * 30.44
        jd = solve_sun_longitude(lon, approx)
        y, m, d, _ = from_jd(jd + JST_OFFSET)
        out[i] = date(y, m, d)
    return out


# ---------------------------------------------------------------
# 新月・満月（Meeus / Astronomical Algorithms 49章）
# ---------------------------------------------------------------

def moon_phase_jd(k, phase):
    """phase: 0=新月, 0.5=満月"""
    k = k + phase
    t = k / 1236.85
    jde = (2451550.09766 + 29.530588861 * k + 0.00015437 * t * t
           - 0.000000150 * t ** 3 + 0.00000000073 * t ** 4)
    e = 1 - 0.002516 * t - 0.0000074 * t * t
    m = math.radians((2.5534 + 29.10535670 * k - 0.0000014 * t * t
                      - 0.00000011 * t ** 3) % 360)
    mp = math.radians((201.5643 + 385.81693528 * k + 0.0107582 * t * t
                       + 0.00001238 * t ** 3 - 0.000000058 * t ** 4) % 360)
    f = math.radians((160.7108 + 390.67050284 * k - 0.0016118 * t * t
                      - 0.00000227 * t ** 3 + 0.000000011 * t ** 4) % 360)
    om = math.radians((124.7746 - 1.56375588 * k + 0.0020672 * t * t
                       + 0.00000215 * t ** 3) % 360)

    if phase == 0:
        corr = (-0.40720 * math.sin(mp) + 0.17241 * e * math.sin(m)
                + 0.01608 * math.sin(2 * mp) + 0.01039 * math.sin(2 * f)
                + 0.00739 * e * math.sin(mp - m) - 0.00514 * e * math.sin(mp + m)
                + 0.00208 * e * e * math.sin(2 * m) - 0.00111 * math.sin(mp - 2 * f)
                - 0.00057 * math.sin(mp + 2 * f) + 0.00056 * e * math.sin(2 * mp + m)
                - 0.00042 * math.sin(3 * mp) + 0.00042 * e * math.sin(m + 2 * f)
                + 0.00038 * e * math.sin(m - 2 * f) - 0.00024 * e * math.sin(2 * mp - m)
                - 0.00017 * math.sin(om) - 0.00007 * math.sin(mp + 2 * m))
    else:
        corr = (-0.40614 * math.sin(mp) + 0.17302 * e * math.sin(m)
                + 0.01614 * math.sin(2 * mp) + 0.01043 * math.sin(2 * f)
                + 0.00734 * e * math.sin(mp - m) - 0.00515 * e * math.sin(mp + m)
                + 0.00209 * e * e * math.sin(2 * m) - 0.00111 * math.sin(mp - 2 * f)
                - 0.00057 * math.sin(mp + 2 * f) + 0.00056 * e * math.sin(2 * mp + m)
                - 0.00042 * math.sin(3 * mp) + 0.00042 * e * math.sin(m + 2 * f)
                + 0.00038 * e * math.sin(m - 2 * f) - 0.00024 * e * math.sin(2 * mp - m)
                - 0.00017 * math.sin(om) - 0.00007 * math.sin(mp + 2 * m))

    a = [
        (0.000325, 299.77 + 0.107408 * k - 0.009173 * t * t),
        (0.000165, 251.88 + 0.016321 * k), (0.000164, 251.83 + 26.651886 * k),
        (0.000126, 349.42 + 36.412478 * k), (0.000110, 84.66 + 18.206239 * k),
        (0.000062, 141.74 + 53.303771 * k), (0.000060, 207.14 + 2.453732 * k),
        (0.000056, 154.84 + 7.306860 * k), (0.000047, 34.52 + 27.261239 * k),
        (0.000042, 207.19 + 0.121824 * k), (0.000040, 291.34 + 1.844379 * k),
        (0.000037, 161.72 + 24.198154 * k), (0.000035, 239.56 + 25.513099 * k),
        (0.000023, 331.55 + 3.592518 * k),
    ]
    add = sum(c * math.sin(math.radians(ang % 360)) for c, ang in a)
    return jde + corr + add


def delta_t(year):
    """
    力学時(TT)と世界時(UT)の差 ΔT（秒）。

    Meeus の式は TT で結果を返すが、時計の時刻は UT なので差し引く必要がある。
    2005〜2050年向けのNASA多項式を使う（2026年で約75秒）。
    """
    t = year - 2000
    return 62.92 + 0.32217 * t + 0.005589 * t * t


def moon_events(start: date, end: date):
    """期間内の新月・満月を (日付, 種別, 時刻文字列) で返す（JST）"""
    out = []
    k0 = math.floor((start.year + (start.month - 1) / 12 - 2000) * 12.3685) - 2
    for i in range(k0, k0 + 40):
        for phase, name in ((0, "新月"), (0.5, "満月")):
            jd = moon_phase_jd(i, phase)
            # TT → UT に直してから JST にする
            jd -= delta_t(start.year) / 86400.0
            y, m, d, frac = from_jd(jd + JST_OFFSET)
            dt = date(y, m, d)
            if start <= dt <= end:
                # 「その分に起きた」という表示にするため切り捨てる
                minutes = int(frac * 24 * 60)
                out.append((dt, name, f"{minutes // 60}:{minutes % 60:02d}"))
    return sorted(out)


# ---------------------------------------------------------------
# 旧暦（六曜の計算に使う）
# ---------------------------------------------------------------

def _new_moon_days(year):
    """その年前後の朔日（新月の日）をJSTの日付で列挙する"""
    days = []
    k0 = math.floor((year - 1 - 2000) * 12.3685)
    for i in range(k0, k0 + 30):
        jd = moon_phase_jd(i, 0)
        y, m, d, _ = from_jd(jd + JST_OFFSET)
        days.append(date(y, m, d))
    return sorted(set(days))


def _chuki_longitude_at(d: date):
    """その日の太陽黄経（JST正午）"""
    return sun_longitude(to_jd(d.year, d.month, d.day, 0.5) - JST_OFFSET)


def kyureki_month_day(d: date, cache={}):
    """
    旧暦の月・日を求める。六曜の計算にのみ使う。

    天保暦の規則：
      ・朔日（新月の日）が旧暦月の1日
      ・冬至(黄経270°)を含む月を11月とする
      ・中気（黄経が30の倍数）を含まない月を閏月とする
    """
    key = d.year
    if key not in cache:
        cache[key] = _build_kyureki_table(d.year)
    table = cache[key]
    for start, month_no, is_leap in table:
        pass
    # 該当する朔日を探す
    prev = None
    for start, month_no, is_leap in table:
        if start <= d:
            prev = (start, month_no, is_leap)
        else:
            break
    if prev is None:
        cache[d.year - 1] = _build_kyureki_table(d.year - 1)
        for start, month_no, is_leap in cache[d.year - 1]:
            if start <= d:
                prev = (start, month_no, is_leap)
    start, month_no, is_leap = prev
    return month_no, (d - start).days + 1


def _build_kyureki_table(year):
    """(朔日, 旧暦月番号, 閏か) のリストを作る"""
    nm = [x for x in _new_moon_days(year) if date(year - 1, 10, 1) <= x <= date(year + 1, 3, 1)]
    months = []
    for i in range(len(nm) - 1):
        start, nxt = nm[i], nm[i + 1]
        # この月に含まれる中気（黄経30の倍数の通過）を調べる
        chuki = None
        d = start
        while d < nxt:
            l1 = _chuki_longitude_at(d)
            l2 = _chuki_longitude_at(d + timedelta(days=1))
            if math.floor(l1 / 30) != math.floor(l2 / 30) or (l2 < l1):
                chuki = int(math.floor(l2 / 30) * 30) % 360
                break
            d += timedelta(days=1)
        months.append([start, chuki])

    # 冬至(270°)を含む月を11月とする
    anchor = None
    for i, (start, chuki) in enumerate(months):
        if chuki == 270:
            anchor = i
            break
    if anchor is None:
        anchor = 0

    table = []
    month_no = 11
    leap_used = False
    for i in range(anchor, len(months)):
        start, chuki = months[i]
        if i > anchor and chuki is None and not leap_used:
            table.append((start, month_no, True))   # 閏月：前月と同じ番号
            leap_used = True
            continue
        table.append((start, month_no, False))
        month_no = month_no % 12 + 1
    # anchorより前も遡って埋める
    back = []
    month_no = 11
    for i in range(anchor - 1, -1, -1):
        month_no = 12 if month_no == 1 else month_no - 1
        back.append((months[i][0], month_no, False))
    return sorted(back[::-1] + table)


# ---------------------------------------------------------------
# 各種の判定
# ---------------------------------------------------------------

def kanshi_index(d: date):
    return (d - KANSHI_EPOCH).days % 60


def kanshi(d: date):
    n = kanshi_index(d)
    return JIKKAN[n % 10] + JUNISHI[n % 12]


def setsugetsu(d: date, terms_cache={}):
    """その日が属する節月（1=立春〜, 2=啓蟄〜, …）"""
    for y in (d.year, d.year - 1):
        if y not in terms_cache:
            terms_cache[y] = solar_terms(y)
    cur = terms_cache[d.year]
    result = None
    for i in range(1, 13):
        if cur[i] <= d:
            result = i
    if result is None:
        result = 12  # 立春前は前年の小寒節
    return result


def season(d: date):
    m = setsugetsu(d)
    if 1 <= m <= 3:
        return "spring"
    if 4 <= m <= 6:
        return "summer"
    if 7 <= m <= 9:
        return "autumn"
    return "winter"


def is_ichiryu(d: date):
    return kanshi(d)[1] in ICHIRYU_BY_SETSUGETSU[setsugetsu(d)]


def is_tensha(d: date):
    return kanshi(d) == TENSHA[season(d)]


def rokuyo(d: date):
    m, day = kyureki_month_day(d)
    return ROKUYO[(m + day) % 6]


def day_info(d: date):
    k = kanshi(d)
    tags = []
    if is_tensha(d):
        tags.append("天赦日")
    if is_ichiryu(d):
        tags.append("一粒万倍日")
    if k == "甲子":
        tags.append("甲子の日")
    if k[1] == "寅":
        tags.append("寅の日")
    if k[1] == "巳":
        tags.append("己巳の日" if k == "己巳" else "巳の日")
    return {"date": d, "kanshi": k, "rokuyo": rokuyo(d), "tags": tags}


# ---------------------------------------------------------------
# 検証：2026年7月・8月の実データと突き合わせる
# ---------------------------------------------------------------

EXPECTED = {
    "2026-07": {
        "一粒万倍日": [6, 7, 10, 19, 22, 31],
        "天赦日": [19],
        "大安": [3, 9, 19, 25, 31],
        "寅の日": [3, 15, 27],
        "巳の日": [6, 18, 30],
        "甲子の日": [],
    },
    "2026-08": {
        "一粒万倍日": [3, 13, 18, 25, 30],
        "天赦日": [],
        "大安": [6, 12, 17, 23, 29],
        "寅の日": [8, 20],
        "巳の日": [11, 23],
        "甲子の日": [18],
    },
}
EXPECTED_MOON = [
    (date(2026, 7, 29), "満月"),
    (date(2026, 8, 13), "新月", "2:36"),
    (date(2026, 8, 28), "満月", "13:18"),
]


def verify():
    ok = True
    print("=" * 62)
    print(" 暦計算の検証（UIC・bestcalendar の実データと突き合わせ）")
    print("=" * 62)

    for ym, exp in EXPECTED.items():
        y, m = map(int, ym.split("-"))
        days = []
        d = date(y, m, 1)
        while d.month == m:
            days.append(day_info(d))
            d += timedelta(days=1)

        got = {k: [] for k in exp}
        for info in days:
            for t in info["tags"]:
                key = "巳の日" if t == "己巳の日" else t
                if key in got:
                    got[key].append(info["date"].day)
            if info["rokuyo"] == "大安":
                got["大安"].append(info["date"].day)

        print(f"\n【{ym}】")
        for key, want in exp.items():
            have = sorted(set(got[key]))
            mark = "OK " if have == sorted(want) else "NG "
            if have != sorted(want):
                ok = False
            print(f"  [{mark}] {key:<8} 計算={have}")
            if have != sorted(want):
                print(f"           　　 実データ={sorted(want)}")

    print("\n【新月・満月】")
    events = moon_events(date(2026, 7, 1), date(2026, 8, 31))
    for e in EXPECTED_MOON:
        want_d, want_name = e[0], e[1]
        found = [x for x in events if x[0] == want_d and x[1] == want_name]
        if found:
            got_time = found[0][2]
            if len(e) > 2:
                same = got_time == e[2]
                if not same:
                    ok = False
                print(f"  [{'OK ' if same else 'NG '}] {want_d} {want_name} "
                      f"計算={got_time} 実データ={e[2]}")
            else:
                print(f"  [OK ] {want_d} {want_name} 計算={got_time}")
        else:
            ok = False
            print(f"  [NG ] {want_d} {want_name} が計算結果に見つかりません")

    print("\n" + "=" * 62)
    print(" 結果: すべて一致。計算エンジンは信頼できます。" if ok
          else " 結果: 不一致あり。上の NG を修正すること。")
    print("=" * 62)
    return ok


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    else:
        d = date.today()
        print(day_info(d))
