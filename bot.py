"""
FX YIELD SPREAD BOT — TELEGRAM
Group: PETILASAN | Topic: Valuasi (Thread ID: 7)
"""

import os, time, threading, logging, requests, schedule, re
from datetime import datetime, timedelta

TOKEN     = os.environ.get("BOT_TOKEN",     "8752357076:AAHVDQckEFwiRafaUfduHTOLwH5IC6A7fE4")
CHAT_ID   = os.environ.get("CHAT_ID",      "-1003890278221")
THREAD_ID = int(os.environ.get("THREAD_ID",  "7"))
HOUR      = int(os.environ.get("SEND_HOUR",  "1"))
MINUTE    = int(os.environ.get("SEND_MINUTE","0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ──────────────────────────────────────────
# FALLBACK YIELDS (update berkala)
# ──────────────────────────────────────────
FALLBACK = {
    "1Y": {"US":4.82,"EU":2.10,"GB":4.52,"JP":0.60,"AU":3.80,"NZ":3.55,"CA":3.10,"CH":0.25,"CN":1.40},
    "2Y": {"US":3.93,"EU":2.05,"GB":4.10,"JP":0.35,"AU":3.85,"NZ":3.60,"CA":2.90,"CH":-0.25,"CN":1.50},
    "10Y":{"US":4.37,"EU":2.65,"GB":4.65,"JP":1.50,"AU":4.35,"NZ":4.55,"CA":3.40,"CH":0.70,"CN":1.80},
}

# Yield aktif di memori
YIELDS   = {"1Y": dict(FALLBACK["1Y"]), "2Y": dict(FALLBACK["2Y"]), "10Y": dict(FALLBACK["10Y"])}
SOURCES  = {"1Y": {}, "2Y": {}, "10Y": {}}
UPDATED_AT = "hardcode (belum auto-fetch)"

# ──────────────────────────────────────────
# FRED — US (1Y, 2Y, 10Y)
# ──────────────────────────────────────────
FRED_SERIES = {"1Y": "DGS1", "2Y": "DGS2", "10Y": "DGS10"}

def fetch_fred(series_id: str) -> float | None:
    try:
        r = requests.get(
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            lines = [l for l in r.text.strip().splitlines()
                     if not l.startswith("DATE") and "," in l]
            # Ambil baris valid terbaru (skip ".")
            for line in reversed(lines):
                val_str = line.split(",")[1].strip()
                if val_str and val_str != ".":
                    return round(float(val_str), 2)
    except Exception as e:
        log.debug(f"FRED {series_id}: {e}")
    return None

# ──────────────────────────────────────────
# ECB — EU/DE (1Y, 2Y, 10Y)
# ──────────────────────────────────────────
ECB_SERIES = {"1Y": "SR_1Y", "2Y": "SR_2Y", "10Y": "SR_10Y"}

def fetch_ecb(maturity: str) -> float | None:
    try:
        series = ECB_SERIES[maturity]
        url = (f"https://data-api.ecb.europa.eu/service/data/"
               f"YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{series}"
               f"?format=csvdata&lastNObservations=5")
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            # Cari header untuk tahu kolom OBS_VALUE
            header = lines[0].split(",") if lines else []
            obs_idx = next((i for i, h in enumerate(header)
                           if "OBS_VALUE" in h.upper()), -1)
            if obs_idx == -1:
                obs_idx = len(header) - 1
            for line in reversed(lines[1:]):
                parts = line.split(",")
                if len(parts) > obs_idx:
                    val_str = parts[obs_idx].strip()
                    if val_str and val_str not in ("", "NaN", "na"):
                        val = float(val_str)
                        if val != 0.0:
                            return round(val, 2)
    except Exception as e:
        log.debug(f"ECB {maturity}: {e}")
    return None

# ──────────────────────────────────────────
# BANK OF ENGLAND — GB
# ──────────────────────────────────────────
BOE_SERIES = {"1Y": "IUDMNZC1", "2Y": "IUDMNZC2", "10Y": "IUDMNZC10"}

def fetch_boe(series: str) -> float | None:
    try:
        url = (f"https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
               f"?Travel=NIxIRx&FromSeries=1&ToSeries=50&DAT=RNG"
               f"&FD=01/Jan/2025&TD=01/Jan/2027&FNY=&CSVF=TT"
               f"&html.x=66&html.y=26&C={series}&Filter=N")
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200 and "," in r.text:
            lines = [l for l in r.text.strip().splitlines()
                     if l and not l.startswith("Date")]
            for line in reversed(lines):
                parts = line.split(",")
                if len(parts) >= 2:
                    val_str = parts[1].strip()
                    if val_str and val_str != "":
                        return round(float(val_str), 2)
    except Exception as e:
        log.debug(f"BoE {series}: {e}")
    return None

# ──────────────────────────────────────────
# BANK OF CANADA — CA
# ──────────────────────────────────────────
BOC_SERIES = {"1Y": "V39051", "2Y": "V39054", "10Y": "V39063"}

def fetch_boc(series: str) -> float | None:
    try:
        r = requests.get(
            f"https://www.bankofcanada.ca/valet/observations/{series}/json?recent=5",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for obs in reversed(data.get("observations", [])):
                v = obs.get(series, {}).get("v", "")
                if v and v != "":
                    return round(float(v), 2)
    except Exception as e:
        log.debug(f"BoC {series}: {e}")
    return None

# ──────────────────────────────────────────
# RBA — AU
# ──────────────────────────────────────────
RBA_COL = {"1Y": "1 year", "2Y": "2 year", "10Y": "10 year"}

def fetch_rba(maturity: str) -> float | None:
    try:
        r = requests.get(
            "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            col_idx = None
            data_start = 0
            target = RBA_COL[maturity].lower()
            for i, line in enumerate(lines):
                low = line.lower()
                if target in low:
                    parts = line.split(",")
                    for j, p in enumerate(parts):
                        if target in p.lower():
                            col_idx = j
                            data_start = i + 2
                            break
                    if col_idx is not None:
                        break
            if col_idx is not None:
                for line in reversed(lines[data_start:]):
                    parts = line.split(",")
                    if len(parts) > col_idx:
                        val_str = parts[col_idx].strip()
                        if val_str and val_str != "":
                            return round(float(val_str), 2)
    except Exception as e:
        log.debug(f"RBA {maturity}: {e}")
    return None

# ──────────────────────────────────────────
# RBNZ — NZ
# ──────────────────────────────────────────
def fetch_rbnz(maturity: str) -> float | None:
    try:
        r = requests.get(
            "https://www.rbnz.govt.nz/api/indicatorsdata/b2?type=json",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            data = r.json()
            mat_num = maturity.replace("Y", "")
            for s in data.get("series", []):
                name = str(s.get("name", ""))
                if mat_num in name and "year" in name.lower():
                    obs = s.get("observations", [])
                    if obs:
                        val = obs[-1].get("value")
                        if val is not None:
                            return round(float(val), 2)
    except Exception as e:
        log.debug(f"RBNZ {maturity}: {e}")
    return None

# ──────────────────────────────────────────
# JAPAN MOF — JP
# ──────────────────────────────────────────
def fetch_mof(maturity: str) -> float | None:
    try:
        r = requests.get(
            "https://www.mof.go.jp/english/jgbs/reference/interest_rate/jgbcme.csv",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            header = lines[0].split(",") if lines else []
            target = maturity.replace("Y", "Y").lower()
            col_idx = None
            for i, h in enumerate(header):
                if target in h.lower().replace(" ", ""):
                    col_idx = i
                    break
            if col_idx and len(lines) > 1:
                parts = lines[-1].split(",")
                if len(parts) > col_idx:
                    val_str = parts[col_idx].strip()
                    if val_str:
                        return round(float(val_str), 2)
    except Exception as e:
        log.debug(f"MOF {maturity}: {e}")
    return None

# ──────────────────────────────────────────
# SNB — CH
# ──────────────────────────────────────────
SNB_SERIES = {"1Y": "rendoblim/CHF/D1", "2Y": "rendoblim/CHF/D2", "10Y": "rendoblim/CHF/D10"}

def fetch_snb(maturity: str) -> float | None:
    try:
        series = SNB_SERIES.get(maturity)
        if not series:
            return None
        r = requests.get(
            f"https://data.snb.ch/api/serie/{series}/json?lastNObservations=5",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            data = r.json()
            obs = data.get("data", {}).get("observations", [])
            for o in reversed(obs):
                val = o.get("value")
                if val is not None:
                    return round(float(val), 2)
    except Exception as e:
        log.debug(f"SNB {maturity}: {e}")
    return None

# ──────────────────────────────────────────
# CHINABOND — CN
# ──────────────────────────────────────────
CN_TERM = {"1Y": "1", "2Y": "2", "10Y": "10"}

def fetch_cn(maturity: str) -> float | None:
    try:
        today = datetime.now().strftime("%Y%m%d")
        r = requests.get(
            f"https://yield.chinabond.com.cn/cbweb-czb-web/czb/historyQuery"
            f"?workTime={today}&locale=en_US",
            headers={"User-Agent": "Mozilla/5.0",
                     "Referer": "https://yield.chinabond.com.cn/"}, timeout=12)
        if r.status_code == 200:
            data = r.json()
            target = CN_TERM[maturity]
            for item in data:
                if str(item.get("term", "")) == target:
                    return round(float(item.get("yield", 0)), 2)
    except Exception as e:
        log.debug(f"ChinaBond {maturity}: {e}")
    return None

# ──────────────────────────────────────────
# MASTER FETCH — semua negara semua tenor
# ──────────────────────────────────────────
def get_yields_auto():
    global YIELDS, SOURCES, UPDATED_AT
    log.info("Auto-fetch yield dari sumber resmi...")

    FETCH = {
        "US":  {"1Y": lambda: fetch_fred("DGS1"),  "2Y": lambda: fetch_fred("DGS2"),  "10Y": lambda: fetch_fred("DGS10")},
        "EU":  {"1Y": lambda: fetch_ecb("1Y"),      "2Y": lambda: fetch_ecb("2Y"),      "10Y": lambda: fetch_ecb("10Y")},
        "GB":  {"1Y": lambda: fetch_boe("IUDMNZC1"),"2Y": lambda: fetch_boe("IUDMNZC2"),"10Y": lambda: fetch_boe("IUDMNZC10")},
        "CA":  {"1Y": lambda: fetch_boc("V39051"),  "2Y": lambda: fetch_boc("V39054"),  "10Y": lambda: fetch_boc("V39063")},
        "AU":  {"1Y": lambda: fetch_rba("1Y"),      "2Y": lambda: fetch_rba("2Y"),      "10Y": lambda: fetch_rba("10Y")},
        "NZ":  {"1Y": lambda: fetch_rbnz("1Y"),     "2Y": lambda: fetch_rbnz("2Y"),     "10Y": lambda: fetch_rbnz("10Y")},
        "JP":  {"1Y": lambda: fetch_mof("1Y"),      "2Y": lambda: fetch_mof("2Y"),      "10Y": lambda: fetch_mof("10Y")},
        "CH":  {"1Y": lambda: fetch_snb("1Y"),      "2Y": lambda: fetch_snb("2Y"),      "10Y": lambda: fetch_snb("10Y")},
        "CN":  {"1Y": lambda: fetch_cn("1Y"),        "2Y": lambda: fetch_cn("2Y"),        "10Y": lambda: fetch_cn("10Y")},
    }

    for country, tenors in FETCH.items():
        for tenor, func in tenors.items():
            val = func()
            if val is not None and -5 < val < 25:
                YIELDS[tenor][country] = val
                SOURCES[tenor][country] = "auto"
                log.info(f"  {country} {tenor}: {val}% [auto]")
            else:
                YIELDS[tenor][country] = FALLBACK[tenor].get(country, 0.0)
                SOURCES[tenor][country] = "fallback"
                log.warning(f"  {country} {tenor}: gagal — fallback {YIELDS[tenor][country]}%")

    UPDATED_AT = datetime.now().strftime("%d %b %Y %H:%M WIB")
    log.info(f"Yield update selesai: {UPDATED_AT}")

# ──────────────────────────────────────────
# 31 PAIR FX
# ──────────────────────────────────────────
FX_PAIRS = [
    ("EURUSD","EU","US","EUR","USD"), ("GBPUSD","GB","US","GBP","USD"),
    ("AUDUSD","AU","US","AUD","USD"), ("NZDUSD","NZ","US","NZD","USD"),
    ("USDJPY","US","JP","USD","JPY"), ("USDCAD","US","CA","USD","CAD"),
    ("USDCHF","US","CH","USD","CHF"), ("USDCNH","US","CN","USD","CNH"),
    ("EURGBP","EU","GB","EUR","GBP"), ("EURJPY","EU","JP","EUR","JPY"),
    ("EURCAD","EU","CA","EUR","CAD"), ("EURCHF","EU","CH","EUR","CHF"),
    ("EURNZD","EU","NZ","EUR","NZD"), ("EURAUD","EU","AU","EUR","AUD"),
    ("GBPJPY","GB","JP","GBP","JPY"), ("GBPCAD","GB","CA","GBP","CAD"),
    ("GBPCHF","GB","CH","GBP","CHF"), ("GBPNZD","GB","NZ","GBP","NZD"),
    ("GBPAUD","GB","AU","GBP","AUD"), ("AUDJPY","AU","JP","AUD","JPY"),
    ("AUDCAD","AU","CA","AUD","CAD"), ("AUDCHF","AU","CH","AUD","CHF"),
    ("AUDNZD","AU","NZ","AUD","NZD"), ("AUDEUR","AU","EU","AUD","EUR"),
    ("AUDGBP","AU","GB","AUD","GBP"), ("NZDJPY","NZ","JP","NZD","JPY"),
    ("NZDCAD","NZ","CA","NZD","CAD"), ("NZDCHF","NZ","CH","NZD","CHF"),
    ("NZDGBP","NZ","GB","NZD","GBP"), ("CADJPY","CA","JP","CAD","JPY"),
    ("CADCHF","CA","CH","CAD","CHF"),
]

def get_all_fx() -> dict:
    log.info("Mengambil harga FX...")
    rates_usd = {}
    try:
        r = requests.get(
            "https://api.fxratesapi.com/latest?base=USD&currencies=EUR,GBP,AUD,NZD,JPY,CAD,CHF,CNH,CNY",
            timeout=15)
        data = r.json()
        if data.get("rates"):
            rates_usd = data["rates"]
            rates_usd["USD"] = 1.0
    except Exception as e:
        log.error(f"fxratesapi: {e}")
    if not rates_usd:
        try:
            r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
            data2 = r2.json()
            if data2.get("result") == "success":
                rates_usd = data2["rates"]
                rates_usd["USD"] = 1.0
        except Exception as e2:
            log.error(f"er-api: {e2}")
    fx = {}
    for pair, _, _, b, q in FX_PAIRS:
        try:
            bc = "CNY" if b == "CNH" else b
            qc = "CNY" if q == "CNH" else q
            if bc == "USD": price = rates_usd.get(qc)
            elif qc == "USD":
                rate = rates_usd.get(bc)
                price = 1/rate if rate else None
            else:
                rb, rq = rates_usd.get(bc), rates_usd.get(qc)
                price = rq/rb if (rb and rq) else None
            fx[pair] = price
        except:
            fx[pair] = None
    return fx

def calculate(fx_prices: dict, tenor: str = "2Y") -> list:
    results = []
    yields = YIELDS[tenor]
    for pair, base, quote, _, _ in FX_PAIRS:
        yb, yq, fx = yields.get(base), yields.get(quote), fx_prices.get(pair)
        if yb is None or yq is None or fx is None:
            continue
        spread = yb - yq
        fair = fx / (1 + spread/100)
        diff_pct = ((fx - fair) / fair) * 100
        status = "OVERVALUED" if diff_pct > 0.5 else ("UNDERVALUED" if diff_pct < -0.5 else "FAIR VALUE")
        results.append({"pair": pair, "status": status, "diff": diff_pct})
    return results

def format_valuation(results: list, tenor: str = "2Y") -> str:
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    over  = [r for r in results if r["status"] == "OVERVALUED"]
    under = [r for r in results if r["status"] == "UNDERVALUED"]
    fair  = [r for r in results if r["status"] == "FAIR VALUE"]
    auto_count = sum(1 for v in SOURCES[tenor].values() if v == "auto")
    lines = [
        f"📊 *YIELD SPREAD FX VALUATION — {tenor}*",
        f"🕐 _{now}_",
        f"📡 _Yield: {auto_count}/9 auto | {UPDATED_AT}_",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if over:
        lines.append("\n🔴 *OVERVALUED*")
        for r in over:
            lines.append(f"`{r['pair']}` : Overvalued ({r['diff']:+.2f}%)")
    if under:
        lines.append("\n🟢 *UNDERVALUED*")
        for r in under:
            lines.append(f"`{r['pair']}` : Undervalued ({r['diff']:+.2f}%)")
    if fair:
        lines.append("\n⚪ *FAIR VALUE*")
        for r in fair:
            lines.append(f"`{r['pair']}` : Fair Value ({r['diff']:+.2f}%)")
    lines += ["\n━━━━━━━━━━━━━━━━━━━━━━",
              f"Total: {len(results)} pair | ⚠️ Bukan rekomendasi investasi"]
    return "\n".join(lines)

def format_tenor_table() -> str:
    """Tampilkan tabel yield 1Y, 2Y, 10Y semua negara."""
    lines = [
        "📈 *YIELD PER TENOR — SEMUA NEGARA*",
        f"_Update: {UPDATED_AT}_\n",
        "`Negara  | 1Y     | 2Y     | 10Y`",
        "`--------|--------|--------|--------`",
    ]
    countries = ["US","EU","GB","CA","AU","NZ","JP","CH","CN"]
    flags = {"US":"🇺🇸","EU":"🇩🇪","GB":"🇬🇧","CA":"🇨🇦","AU":"🇦🇺","NZ":"🇳🇿","JP":"🇯🇵","CH":"🇨🇭","CN":"🇨🇳"}
    for c in countries:
        y1  = YIELDS["1Y"].get(c, 0)
        y2  = YIELDS["2Y"].get(c, 0)
        y10 = YIELDS["10Y"].get(c, 0)
        s1  = SOURCES["1Y"].get(c, "?")
        s2  = SOURCES["2Y"].get(c, "?")
        s10 = SOURCES["10Y"].get(c, "?")
        icon1  = "📡" if s1=="auto"  else "📌"
        icon2  = "📡" if s2=="auto"  else "📌"
        icon10 = "📡" if s10=="auto" else "📌"
        lines.append(
            f"{flags[c]} `{c}` : {icon1}{y1:+.2f}% | {icon2}{y2:+.2f}% | {icon10}{y10:+.2f}%"
        )
    lines.append("\n📡=auto | 📌=fallback")
    return "\n".join(lines)

# ──────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────
def send_message(text, chat_id=CHAT_ID, thread_id=THREAD_ID):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
            "chat_id": chat_id, "text": text,
            "parse_mode": "Markdown", "message_thread_id": thread_id,
        }, timeout=15)
    except Exception as e:
        log.error(f"send_message: {e}")

def get_updates(offset=0):
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                         params={"offset": offset, "timeout": 30}, timeout=35)
        return r.json().get("result", [])
    except:
        return []

def run_yield(chat_id=CHAT_ID, thread_id=THREAD_ID, tenor="2Y"):
    send_message(f"⏳ Mengambil data yield {tenor} & FX...\nHarap tunggu ~20 detik.", chat_id, thread_id)
    try:
        get_yields_auto()
        fx = get_all_fx()
        results = calculate(fx, tenor)
        if not results:
            send_message("⚠️ Gagal ambil data FX.", chat_id, thread_id)
            return
        send_message(format_valuation(results, tenor), chat_id, thread_id)
    except Exception as e:
        send_message(f"❌ Error: {e}", chat_id, thread_id)

def handle_updateyield(text, chat_id, thread_id):
    global YIELDS, SOURCES, UPDATED_AT
    # Format: /updateyield 2Y US:3.93 EU:2.05 ...
    # atau:   /updateyield US:3.93 EU:2.05 ... (default 2Y)
    parts = text.replace("/updateyield", "").strip().split()
    tenor = "2Y"
    if parts and parts[0] in ("1Y","2Y","10Y"):
        tenor = parts[0]
        parts = parts[1:]
    updated, errors = {}, []
    for part in parts:
        try:
            code, val = part.split(":")
            code = code.upper().strip()
            if code not in YIELDS[tenor]:
                errors.append(f"{code} tidak dikenal")
                continue
            YIELDS[tenor][code] = float(val)
            SOURCES[tenor][code] = "manual"
            updated[code] = float(val)
        except:
            errors.append(f"Format salah: {part}")
    if updated:
        UPDATED_AT = datetime.now().strftime("%d %b %Y %H:%M WIB")
        lines = [f"✅ *Yield {tenor} diupdate manual!*\n"]
        for k, v in YIELDS[tenor].items():
            src = SOURCES[tenor].get(k, "?")
            icon = "🔄" if k in updated else ("📡" if src=="auto" else "📌")
            lines.append(f"{icon} `{k}` : {v:.2f}%")
        if errors:
            lines.append(f"\n⚠️ Error: {', '.join(errors)}")
        send_message("\n".join(lines), chat_id, thread_id)
    else:
        send_message(
            "❌ Format salah.\n\nContoh:\n"
            "`/updateyield US:3.93 EU:2.05`\n"
            "`/updateyield 10Y US:4.37 JP:1.50`", chat_id, thread_id)

# ──────────────────────────────────────────
# SCHEDULER
# ──────────────────────────────────────────
def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(run_yield)
    schedule.every().day.at("00:30").do(get_yields_auto)
    log.info(f"Scheduler: kirim {send_time} UTC | auto-fetch 00:30 UTC")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ──────────────────────────────────────────
# POLLING
# ──────────────────────────────────────────
def polling_loop():
    log.info("Bot berjalan...")
    threading.Thread(target=get_yields_auto, daemon=True).start()
    offset = 0
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            text = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            t_id = msg.get("message_thread_id")
            if not text or not chat_id or t_id != THREAD_ID:
                continue

            if text.startswith("/start"):
                send_message(
                    "👋 *ValuasiFX Bot*\n\n"
                    "📌 *Command:*\n"
                    "/yield — Valuasi 31 pair (tenor 2Y)\n"
                    "/yield1y — Valuasi pakai tenor 1Y\n"
                    "/yield10y — Valuasi pakai tenor 10Y\n"
                    "/yields — Yield 2Y saat ini\n"
                    "/tenor — Tabel yield 1Y, 2Y, 10Y semua negara\n"
                    "/refreshyield — Fetch ulang yield dari bank sentral\n"
                    "/updateyield — Update yield manual\n"
                    "/help — Bantuan\n\n"
                    "⏰ Auto-kirim 08:00 WIB | 📡 Auto-fetch harian",
                    chat_id, THREAD_ID)

            elif text.startswith("/yield1y"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID, "1Y"), daemon=True).start()

            elif text.startswith("/yield10y"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID, "10Y"), daemon=True).start()

            elif text.startswith("/yield") and not text.startswith("/yields") and not text.startswith("/updateyield"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID, "2Y"), daemon=True).start()

            elif text.startswith("/yields"):
                lines = [f"📈 *YIELD 2Y SAAT INI*\n_Update: {UPDATED_AT}_\n"]
                for k, v in YIELDS["2Y"].items():
                    src = SOURCES["2Y"].get(k, "?")
                    icon = "📡" if src=="auto" else ("🔄" if src=="manual" else "📌")
                    lines.append(f"{icon} `{k}` : {v:.2f}%")
                lines.append("\n📡=auto | 🔄=manual | 📌=fallback")
                send_message("\n".join(lines), chat_id, THREAD_ID)

            elif text.startswith("/tenor"):
                send_message(format_tenor_table(), chat_id, THREAD_ID)

            elif text.startswith("/refreshyield"):
                send_message("🔄 Fetching yield dari semua bank sentral...\nHarap tunggu ~30 detik.", chat_id, THREAD_ID)
                def do_refresh(cid, tid):
                    get_yields_auto()
                    auto = sum(1 for t in SOURCES.values() for s in t.values() if s=="auto")
                    total = len(SOURCES) * 9
                    send_message(
                        f"✅ *Yield berhasil di-refresh!*\n"
                        f"📡 Auto: {auto}/{total} | 📌 Fallback: {total-auto}/{total}\n"
                        f"🕐 {UPDATED_AT}\n\n"
                        f"Ketik /tenor untuk lihat semua nilai.", cid, tid)
                threading.Thread(target=do_refresh, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/updateyield"):
                handle_updateyield(text, chat_id, THREAD_ID)

            elif text.startswith("/help"):
                send_message(
                    "📖 *Cara Kerja Bot*\n\n"
                    "*Formula:*\n`Spread = Yield Base - Yield Quote`\n"
                    "`Fair Value = FX ÷ (1 + Spread%)`\n\n"
                    "*Tenor:*\n"
                    "/yield → 2Y (default)\n"
                    "/yield1y → 1Y\n"
                    "/yield10y → 10Y\n\n"
                    "*Update yield manual:*\n"
                    "`/updateyield US:3.93 EU:2.05`\n"
                    "`/updateyield 10Y US:4.37 JP:1.50`\n\n"
                    "*Sumber auto:*\n"
                    "🇺🇸 FRED | 🇩🇪 ECB | 🇬🇧 BoE\n"
                    "🇨🇦 BoC | 🇦🇺 RBA | 🇳🇿 RBNZ\n"
                    "🇯🇵 MOF | 🇨🇭 SNB | 🇨🇳 ChinaBond\n\n"
                    "⚠️ Bukan rekomendasi trading.",
                    chat_id, THREAD_ID)
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
