#!/usr/bin/env python3
"""
開運日カレンダーのサイトを生成する

LINEのリッチメニューから飛ばすページ。毎月テキストを書き換える手間をなくすため、
「今月と来月」を自動で表示する。日付は koyomi_calc.py の計算エンジンから生成する。

  出力: koyomi/index.html
  URL : https://tachikoma865.github.io/happyart/koyomi/

数年分のデータをJSONとしてページに埋め込み、表示する月は開いた日付から
JavaScriptが選ぶ。サーバーは不要で、こちらの更新作業も不要。

使い方:
    python3 build_koyomi_site.py
"""

import json
import os
from datetime import date, timedelta

from koyomi_calc import day_info, moon_events

OUT_DIR = "koyomi"
START = date(2026, 7, 1)
END = date(2029, 12, 31)

WEEK = "月火水木金土日"

# タグごとの説明（ページ下部の凡例に使う）
MEANINGS = {
    "一粒万倍日": "一粒の籾が万倍に実る、という意味の日。「始めること」に向くとされてきました。"
                  "財布の使い始め、口座を開く、習い事のスタートなどを合わせる人が多い日です。"
                  "一方で「増える」意味の日なので、借金は避けたほうがいいとも言われます。",
    "天赦日": "暦の上で最上の吉日とされる日。年に5〜6回しかありません。"
              "天がすべてを赦す日、という意味で、何かを始めるならこの日が選ばれることが多いです。",
    "甲子の日": "十干十二支のいちばん最初の組み合わせ。60日でひと回りする暦のスタート地点です。"
                "ここから始めたことは長く続く、と言われてきました。",
    "寅の日": "寅は「千里を行って千里を帰る」と言われてきた動物。"
              "出したものが戻ってくる日とされ、旅立ちや財布の使い始めに選ばれます。",
    "巳の日": "蛇は弁財天の遣いとされてきました。"
              "弁財天は水と音楽、そして財をつかさどるとされる神さまです。",
    "己巳の日": "巳の日のなかでも60日に一度しか巡ってこない日。"
                "弁財天とのご縁がとくに深い日とされています。",
    "新月": "月が姿を消して、そこからまた満ちていく起点の日。"
            "昔から「願いを立てるタイミング」と言われてきました。",
    "満月": "月が満ちきる日。ここから欠けていくので「手放し」と結びつけられてきました。",
}

PRIORITY = ["天赦日", "一粒万倍日", "甲子の日", "己巳の日", "巳の日", "寅の日", "新月", "満月"]


def build_data():
    """START〜END の全日をひと通り計算して、月ごとにまとめる"""
    moons = {}
    for d, name, t in moon_events(START, END):
        moons.setdefault(d, []).append((name, t))

    months = {}
    d = START
    while d <= END:
        info = day_info(d)
        tags = list(info["tags"])
        times = {}
        for name, t in moons.get(d, []):
            tags.append(name)
            times[name] = t

        if tags:
            key = f"{d.year}-{d.month:02d}"
            months.setdefault(key, []).append({
                "d": d.day,
                "w": WEEK[d.weekday()],
                "tags": sorted(tags, key=lambda x: PRIORITY.index(x) if x in PRIORITY else 99),
                "times": times,
                "rokuyo": info["rokuyo"],
            })
        d += timedelta(days=1)
    return months


HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>開運日カレンダー｜ひかり</title>
<meta name="description" content="一粒万倍日・天赦日・寅の日・巳の日・新月・満月がひと目でわかる開運日カレンダー。今月と来月を自動で表示します。">
<style>
  :root{
    --bg:#fcfaf6; --ink:#2e2822; --sub:#847c72; --gold:#c69c4a;
    --line:#e8e0d2; --card:#fffdfa;
  }
  *{box-sizing:border-box}
  body{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:"Hiragino Sans","Noto Sans JP",system-ui,sans-serif;
    line-height:1.7; -webkit-text-size-adjust:100%;
  }
  .wrap{max-width:680px;margin:0 auto;padding:28px 18px 64px}
  header{text-align:center;margin-bottom:8px}
  h1{
    font-family:"Hiragino Mincho ProN","Noto Serif JP",serif;
    font-size:26px;font-weight:600;margin:0 0 6px;letter-spacing:.04em;
  }
  .lead{color:var(--sub);font-size:13px;margin:0}
  .today{
    margin:22px 0 10px;padding:16px 18px;background:var(--card);
    border:1px solid var(--line);border-radius:14px;
  }
  .today .label{font-size:12px;color:var(--sub);letter-spacing:.08em}
  .today .date{
    font-family:"Hiragino Mincho ProN","Noto Serif JP",serif;
    font-size:21px;margin:2px 0 6px;
  }
  .today .tags{display:flex;flex-wrap:wrap;gap:6px}
  .today .none{color:var(--sub);font-size:13px}
  h2{
    font-family:"Hiragino Mincho ProN","Noto Serif JP",serif;
    font-size:19px;font-weight:600;margin:30px 0 12px;
    padding-bottom:8px;border-bottom:1px solid var(--line);
  }
  ul{list-style:none;margin:0;padding:0}
  li{
    display:flex;gap:12px;align-items:flex-start;
    padding:11px 2px;border-bottom:1px solid #f0ebe1;
  }
  li:last-child{border-bottom:none}
  .day{
    flex:0 0 58px;font-family:"Hiragino Mincho ProN","Noto Serif JP",serif;
    font-size:17px;padding-top:1px;
  }
  .day small{font-size:12px;color:var(--sub);margin-left:3px}
  .sat{color:#5b83a8}.sun{color:#b06a72}
  .tags{display:flex;flex-wrap:wrap;gap:6px;flex:1}
  .tag{
    font-size:12px;padding:3px 9px;border-radius:999px;
    background:#f6f1e6;color:#7d6636;border:1px solid #ece2cd;white-space:nowrap;
  }
  .tag.strong{background:var(--gold);color:#fff;border-color:var(--gold)}
  .tag.moon{background:#eef4f8;color:#4a6c86;border-color:#dde8ef}
  .tag time{font-variant-numeric:tabular-nums;opacity:.85;margin-left:4px}
  .hl{
    margin:16px 0 0;padding:14px 16px;background:#fdf8ec;
    border:1px solid #f0e4c8;border-radius:12px;font-size:13.5px;
  }
  .hl b{color:#8a6d2f}
  details{margin-top:34px;border-top:1px solid var(--line);padding-top:18px}
  summary{cursor:pointer;font-size:14px;color:var(--sub)}
  dl{margin:14px 0 0}
  dt{font-weight:600;margin-top:14px;font-size:14px}
  dd{margin:4px 0 0;color:#5f574e;font-size:13.5px}
  footer{margin-top:38px;text-align:center;color:var(--sub);font-size:12px;line-height:1.9}
  footer a{color:var(--sub)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>開運日カレンダー</h1>
    <p class="lead">一粒万倍日・天赦日・新月・満月がひと目でわかる</p>
  </header>

  <div class="today" id="today"></div>
  <div id="months"></div>

  <details>
    <summary>それぞれの日の意味</summary>
    <dl id="legend"></dl>
  </details>

  <footer>
    どれも「そう言われてきた」という言い伝えです。<br>
    たのしむ範囲で使ってもらえたらうれしいです。<br><br>
    <a href="https://www.instagram.com/kodoshi_hikari/">Instagram @kodoshi_hikari</a>
  </footer>
</div>

<script>
const DATA = __DATA__;
const MEANINGS = __MEANINGS__;
const STRONG = ["天赦日","一粒万倍日","甲子の日","己巳の日"];
const MOON = ["新月","満月"];

function tagHtml(t, times){
  let cls = "tag";
  if (STRONG.includes(t)) cls += " strong";
  if (MOON.includes(t)) cls += " moon";
  const time = times && times[t] ? `<time>${times[t]}</time>` : "";
  return `<span class="${cls}">${t}${time}</span>`;
}

function monthTitle(key){
  const [y,m] = key.split("-").map(Number);
  return `${y}年${m}月`;
}

// 重なりが多い日を拾って、ひとこと添える
function highlights(rows){
  const out = [];
  rows.forEach(r=>{
    const strong = r.tags.filter(t=>STRONG.includes(t) || MOON.includes(t));
    if (strong.length >= 2){
      out.push(`<b>${r.d}日</b>（${r.w}）${strong.join(" と ")}が重なります`);
    } else if (r.tags.includes("天赦日")){
      out.push(`<b>${r.d}日</b>（${r.w}）天赦日。年に5〜6回だけの日です`);
    }
  });
  return out;
}

function render(){
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth()+1, d = now.getDate();
  const k1 = `${y}-${String(m).padStart(2,"0")}`;
  const n = new Date(y, m, 1);
  const k2 = `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,"0")}`;

  // 今日の状態
  const todayRow = (DATA[k1]||[]).find(r=>r.d===d);
  const wd = "日月火水木金土"[now.getDay()];
  document.getElementById("today").innerHTML =
    `<div class="label">きょう</div>
     <div class="date">${m}月${d}日（${wd}）</div>` +
    (todayRow
      ? `<div class="tags">${todayRow.tags.map(t=>tagHtml(t,todayRow.times)).join("")}</div>`
      : `<div class="none">暦の上では、とくに名前のついた日ではありません。</div>`);

  // 収録期間を過ぎた場合の案内（データは2029年末まで）
  if(!DATA[k1] && !DATA[k2]){
    document.getElementById("months").innerHTML =
      `<h2>${monthTitle(k1)}</h2>
       <p style="color:var(--sub);font-size:14px">
       この月のデータはまだ用意できていません。<br>
       お手数ですが、Instagramのプロフィールからお知らせください。</p>`;
    document.getElementById("legend").innerHTML =
      Object.entries(MEANINGS).map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join("");
    return;
  }

  // 今月と来月
  let html = "";
  [k1,k2].forEach(key=>{
    const rows = DATA[key];
    if(!rows) return;
    html += `<h2>${monthTitle(key)}</h2><ul>`;
    rows.forEach(r=>{
      const cls = r.w==="土" ? "sat" : (r.w==="日" ? "sun" : "");
      html += `<li><div class="day ${cls}">${r.d}<small>${r.w}</small></div>
               <div class="tags">${r.tags.map(t=>tagHtml(t,r.times)).join("")}</div></li>`;
    });
    html += `</ul>`;
    const hl = highlights(rows);
    if (hl.length) html += `<div class="hl">${hl.join("<br>")}</div>`;
  });
  document.getElementById("months").innerHTML = html;

  document.getElementById("legend").innerHTML =
    Object.entries(MEANINGS).map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join("");
}
render();
</script>
</body>
</html>
"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    data = build_data()

    html = (HTML
            .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("__MEANINGS__", json.dumps(MEANINGS, ensure_ascii=False)))

    path = f"{OUT_DIR}/index.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    months = sorted(data)
    total = sum(len(v) for v in data.values())
    kb = os.path.getsize(path) / 1024
    print(f"生成: {path}  ({kb:.0f}KB)")
    print(f"収録: {months[0]} 〜 {months[-1]}（{len(months)}か月 / 該当日 {total}件）")
    print(f"URL : https://tachikoma865.github.io/happyart/koyomi/")


if __name__ == "__main__":
    main()
