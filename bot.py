"""
╔══════════════════════════════════════════╗
║  FX YIELD SPREAD BOT — TELEGRAM          ║
║  Group  : PETILASAN                      ║
║  Topic  : Valuasi (Thread ID: 7)         ║
║  Yield  : Official Central Bank APIs     ║
║  FX     : fxratesapi / open.er-api       ║
╚══════════════════════════════════════════╝

Sumber yield 2Y resmi per negara:
  US  → FRED (St. Louis Fed)
  EU  → ECB Data API
  GB  → Bank of England
  CA  → Bank of Canada Valet API
  AU  → RBA Statistical Tables
  NZ  → RBNZ Data API
  JP  → Japan MOF
  CH  → SNB Data Portal
  CN  → investing.com scrape (fallback hardcode)
"""

import os, time, threading, logging, requests, schedule
from datetime import datetime, timedelta

# ──────────────────────────────────────────
# KONFIGURASI
# ──────────────────────────────────────────
TOKEN     = os.environ.get("BOT_TOKEN",     "8752357076:AAHVDQckEFwiRafaUfduHTOLwH5IC6A7fE4")
CHAT_ID   = os.environ.get("CHAT_ID",      "-1003890278221")
THREAD_ID = int(os.environ.get("THREAD_ID",  "7"))
HOUR      = int(os.environ.get("SEND_HOUR",  "1"))
MINUTE    = int(os.environ.get("SEND_MINUTE","0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ──────────────────────────────────────────
# FALLBACK YIELD (update manual berkala)
# Terakhir update: 12 Mei 2026
# ──────────────────────────────────────────
YIELDS_FALLBACK = {
    "US": 3.93,
    "EU": 2.05,
    "GB": 4.10,
    "JP": 0.35,
    "AU": 3.85,
    "NZ": 3.60,
    "CA": 2.90,
    "CH": -0.25,
    "CN": 1.50,
}

# Simpan yield aktif di memori (bisa diupdate via /updateyield)
YIELDS = dict(YIELDS_FALLBACK)
YIELD_UPDATED_AT = "hardcode (belum auto-fetch)"
YIELD_SOURCES = {}  # catat sumber tiap negara

# ──────────────────────────────────────────
# FETCH YIELD — SUMBER RESMI PER NEGARA
# ──────────────────────────────────────────

def fetch_us() -> float | None:
    """US 2Y — FRED (St. Louis Fed) — tidak perlu API key"""
    try:
        r = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if r.status_code == 200:
            lines = [l for l in r.text.strip().splitlines() if not l.startswith("DATE") and "." in l]
            if lines:
                val = float(lines[-1].split(",")[1])
                return round(val, 2)
    except Exception as e:
        log.debug(f"FRED US error: {e}")
    return None

def fetch_eu() -> float | None:
    """EU 2Y — ECB Data API"""
    try:
        url = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?format=csvdata&lastNObservations=1"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            lines = [l for l in r.text.strip().splitlines() if l and not l.startswith("KEY")]
            if lines:
                val = float(lines[-1].split(",")[-1])
                return round(val, 2)
    except Exception as e:
        log.debug(f"ECB EU error: {e}")
    return None

def fetch_gb() -> float | None:
    """GB 2Y — Bank of England IADB"""
    try:
        today = datetime.now().strftime("%d/%b/%Y")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%d/%b/%Y")
        url = (
            "https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp"
            f"?Travel=NIxIRx&FromSeries=1&ToSeries=50&DAT=RNG"
            f"&FD={month_ago}&TD={today}&FNY=&CSVF=TT&html.x=66&html.y=26&C=BLC&Filter=N"
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200 and "," in r.text:
            lines = [l for l in r.text.strip().splitlines() if l and not l.startswith("Date")]
            if lines:
                parts = lines[-1].split(",")
                val = float(parts[1]) if len(parts) > 1 else None
                return round(val, 2) if val else None
    except Exception as e:
        log.debug(f"BoE GB error: {e}")
    return None

def fetch_ca() -> float | None:
    """CA 2Y — Bank of Canada Valet API"""
    try:
        # V39054 = Canada 2Y Government Bond Yield
        r = requests.get(
            "https://www.bankofcanada.ca/valet/observations/V39054/json?recent=5",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            obs = data.get("observations", [])
            for o in reversed(obs):
                v = o.get("V39054", {}).get("v")
                if v and v != "":
                    return round(float(v), 2)
    except Exception as e:
        log.debug(f"BoC CA error: {e}")
    return None

def fetch_au() -> float | None:
    """AU 2Y — RBA Statistical Tables F2"""
    try:
        r = requests.get(
            "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            # Cari kolom "2 year" atau "2-year"
            header = None
            col_idx = None
            for i, line in enumerate(lines):
                if "2 year" in line.lower() or "2-year" in line.lower():
                    parts = line.split(",")
                    for j, p in enumerate(parts):
                        if "2" in p and "year" in p.lower():
                            col_idx = j
                            header = i
                            break
                    break
            if col_idx is not None:
                data_lines = [l for l in lines[header+2:] if l.strip() and l.split(",")[0].strip()]
                if data_lines:
                    val = data_lines[-1].split(",")[col_idx].strip()
                    return round(float(val), 2)
    except Exception as e:
        log.debug(f"RBA AU error: {e}")
    return None

def fetch_nz() -> float | None:
    """NZ 2Y — RBNZ Data API"""
    try:
        r = requests.get(
            "https://www.rbnz.govt.nz/api/indicatorsdata/b2?type=json",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            series = data.get("series", [])
            for s in series:
                if "2" in str(s.get("name", "")):
                    obs = s.get("observations", [])
                    if obs:
                        val = obs[-1].get("value")
                        if val is not None:
                            return round(float(val), 2)
    except Exception as e:
        log.debug(f"RBNZ NZ error: {e}")
    return None

def fetch_jp() -> float | None:
    """JP 2Y — Japan MOF (Ministry of Finance)"""
    try:
        r = requests.get(
            "https://www.mof.go.jp/english/jgbs/reference/interest_rate/index.htm",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if r.status_code == 200:
            # Parse tabel dari HTML
            import re
            # Cari angka yield 2Y dari tabel MOF
            matches = re.findall(r'2-year.*?(\d+\.\d+)', r.text[:5000], re.DOTALL)
            if matches:
                return round(float(matches[0]), 2)
    except Exception as e:
        log.debug(f"MOF JP error: {e}")
    return None

def fetch_ch() -> float | None:
    """CH 2Y — SNB Data Portal"""
    try:
        r = requests.get(
            "https://data.snb.ch/api/serie/rendoblim/CHF/D2/json?lastNObservations=5",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            obs = data.get("data", {}).get("observations", [])
            if obs:
                val = obs[-1].get("value")
                return round(float(val), 2) if val is not None else None
    except Exception as e:
        log.debug(f"SNB CH error: {e}")
    return None

def fetch_cn() -> float | None:
    """CN 2Y — China Bond (chinabond.com.cn)"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        r = requests.get(
            f"https://yield.chinabond.com.cn/cbweb-czb-web/czb/historyQuery?workTime={today}&locale=en_US",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://yield.chinabond.com.cn/"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            for item in data:
                if str(item.get("term", "")) == "2":
                    return round(float(item.get("yield", 0)), 2)
    except Exception as e:
        log.debug(f"ChinaBond CN error: {e}")
    return None

# Map negara ke fungsi fetch
FETCH_FUNCS = {
    "US": fetch_us,
    "EU": fetch_eu,
    "GB": fetch_gb,
    "CA": fetch_ca,
    "AU": fetch_au,
    "NZ": fetch_nz,
    "JP": fetch_jp,
    "CH": fetch_ch,
    "CN": fetch_cn,
}

def get_yields_auto() -> dict:
    """Fetch yield dari sumber resmi. Fallback ke hardcode jika gagal."""
    global YIELDS, YIELD_UPDATED_AT, YIELD_SOURCES
    log.info("Mengambil yield 2Y dari sumber resmi bank sentral...")
    new_yields = {}
    new_sources = {}
    used_fallback = []

    for country, func in FETCH_FUNCS.items():
        val = func()
        if val is not None and -5 < val < 25:  # sanity check
            new_yields[country] = val
            new_sources[country] = "auto"
            log.info(f"  {country}: {val}% [auto]")
        else:
            new_yields[country] = YIELDS_FALLBACK.get(country, 0.0)
            new_sources[country] = "fallback"
            used_fallback.append(country)
            log.warning(f"  {country}: gagal — pakai fallback {new_yields[country]}%")

    YIELDS = new_yields
    YIELD_SOURCES = new_sources
    YIELD_UPDATED_AT = datetime.now().strftime("%d %b %Y %H:%M WIB")
    if used_fallback:
        log.info(f"Fallback dipakai: {used_fallback}")
    return YIELDS

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
        log.error(f"fxratesapi error: {e}")
    if not rates_usd:
        try:
            r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
            data2 = r2.json()
            if data2.get("result") == "success":
                rates_usd = data2["rates"]
                rates_usd["USD"] = 1.0
        except Exception as e2:
            log.error(f"er-api error: {e2}")

    fx_prices = {}
    for pair, _, _, base_cur, quote_cur in FX_PAIRS:
        try:
            b = "CNY" if base_cur == "CNH" else base_cur
            q = "CNY" if quote_cur == "CNH" else quote_cur
            if b == "USD":
                price = rates_usd.get(q)
            elif q == "USD":
                rate = rates_usd.get(b)
                price = 1/rate if rate else None
            else:
                rb, rq = rates_usd.get(b), rates_usd.get(q)
                price = rq/rb if (rb and rq) else None
            fx_prices[pair] = price
        except:
            fx_prices[pair] = None
    return fx_prices

def calculate(fx_prices: dict) -> list:
    results = []
    for pair, base, quote, _, _ in FX_PAIRS:
        yb, yq, fx = YIELDS.get(base), YIELDS.get(quote), fx_prices.get(pair)
        if yb is None or yq is None or fx is None:
            continue
        spread = yb - yq
        fair = fx / (1 + spread/100)
        diff_pct = ((fx - fair) / fair) * 100
        status = "OVERVALUED" if diff_pct > 0.5 else ("UNDERVALUED" if diff_pct < -0.5 else "FAIR VALUE")
        results.append({"pair": pair, "status": status, "diff": diff_pct})
    return results

def format_msg(results: list) -> str:
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    over  = [r for r in results if r["status"] == "OVERVALUED"]
    under = [r for r in results if r["status"] == "UNDERVALUED"]
    fair  = [r for r in results if r["status"] == "FAIR VALUE"]
    auto_count = sum(1 for v in YIELD_SOURCES.values() if v == "auto")
    lines = [
        "📊 *YIELD SPREAD FX VALUATION*",
        f"🕐 _{now}_ | Tenor: 2Y",
        f"📡 _Yield: {auto_count}/9 auto | Update: {YIELD_UPDATED_AT}_",
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

def send_message(text, chat_id=CHAT_ID, thread_id=THREAD_ID):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
            "chat_id": chat_id, "text": text,
            "parse_mode": "Markdown", "message_thread_id": thread_id,
        }, timeout=15)
    except Exception as e:
        log.error(f"send_message error: {e}")

def get_updates(offset=0):
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                         params={"offset": offset, "timeout": 30}, timeout=35)
        return r.json().get("result", [])
    except:
        return []

def run_yield(chat_id=CHAT_ID, thread_id=THREAD_ID):
    send_message("⏳ Mengambil data yield & FX dari sumber resmi...\nHarap tunggu ~20 detik.", chat_id, thread_id)
    try:
        get_yields_auto()
        fx_prices = get_all_fx()
        results = calculate(fx_prices)
        if not results:
            send_message("⚠️ Gagal ambil data FX. Coba lagi.", chat_id, thread_id)
            return
        send_message(format_msg(results), chat_id, thread_id)
    except Exception as e:
        log.error(f"run_yield error: {e}")
        send_message(f"❌ Error: {e}", chat_id, thread_id)

def handle_updateyield(text, chat_id, thread_id):
    global YIELDS, YIELD_UPDATED_AT, YIELD_SOURCES
    parts = text.replace("/updateyield", "").strip().split()
    updated = {}
    errors = []
    for part in parts:
        try:
            code, val = part.split(":")
            code = code.upper().strip()
            if code not in YIELDS:
                errors.append(f"{code} tidak dikenal")
                continue
            YIELDS[code] = float(val)
            YIELD_SOURCES[code] = "manual"
            updated[code] = float(val)
        except:
            errors.append(f"Format salah: {part}")
    if updated:
        YIELD_UPDATED_AT = datetime.now().strftime("%d %b %Y %H:%M WIB")
        lines = ["✅ *Yield diupdate manual!*\n"]
        for k, v in YIELDS.items():
            src = YIELD_SOURCES.get(k, "?")
            icon = "🔄" if k in updated else ("📡" if src == "auto" else "📌")
            lines.append(f"{icon} `{k}` : {v:.2f}%")
        lines.append(f"\n🕐 {YIELD_UPDATED_AT}")
        if errors:
            lines.append(f"⚠️ Error: {', '.join(errors)}")
        send_message("\n".join(lines), chat_id, thread_id)
    else:
        send_message(
            "❌ Format salah.\n\nContoh:\n"
            "`/updateyield US:3.93 EU:2.05 GB:4.10 JP:0.35 AU:3.85 NZ:3.60 CA:2.90 CH:-0.25 CN:1.50`",
            chat_id, thread_id)

def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(run_yield)
    # Auto-fetch yield tiap hari jam 00:30 UTC
    schedule.every().day.at("00:30").do(get_yields_auto)
    log.info(f"Scheduler: kirim {send_time} UTC | auto-fetch yield 00:30 UTC")
    while True:
        schedule.run_pending()
        time.sleep(30)

def polling_loop():
    log.info("Bot berjalan...")
    # Auto-fetch yield saat startup
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
                    "/yield — Cek valuasi 31 pair FX\n"
                    "/yields — Lihat yield 2Y saat ini\n"
                    "/updateyield — Update yield manual\n"
                    "/help — Bantuan\n\n"
                    "📡 Yield auto-fetch dari bank sentral resmi\n"
                    "⏰ Auto-kirim 08:00 WIB", chat_id, THREAD_ID)

            elif text.startswith("/yield") and not text.startswith("/yields") and not text.startswith("/updateyield"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/yields"):
                lines = [f"📈 *YIELD 2Y SAAT INI*\n_Update: {YIELD_UPDATED_AT}_\n"]
                for k, v in YIELDS.items():
                    src = YIELD_SOURCES.get(k, "?")
                    icon = "📡" if src == "auto" else ("🔄" if src == "manual" else "📌")
                    lines.append(f"{icon} `{k}` : {v:.2f}%")
                lines.append("\n📡=auto | 🔄=manual | 📌=fallback")
                send_message("\n".join(lines), chat_id, THREAD_ID)

            elif text.startswith("/updateyield"):
                handle_updateyield(text, chat_id, THREAD_ID)

            elif text.startswith("/help"):
                send_message(
                    "📖 *Cara Kerja Bot*\n\n"
                    "*Formula:*\n`Spread = Yield Base - Yield Quote`\n"
                    "`Fair Value = Harga FX ÷ (1 + Spread%)`\n\n"
                    "*Yield auto-fetch dari:*\n"
                    "🇺🇸 US → FRED (St Louis Fed)\n"
                    "🇪🇺 EU → ECB Data API\n"
                    "🇬🇧 GB → Bank of England\n"
                    "🇨🇦 CA → Bank of Canada\n"
                    "🇦🇺 AU → RBA\n"
                    "🇳🇿 NZ → RBNZ\n"
                    "🇯🇵 JP → Japan MOF\n"
                    "🇨🇭 CH → SNB\n"
                    "🇨🇳 CN → ChinaBond\n\n"
                    "⚠️ Bukan rekomendasi trading.", chat_id, THREAD_ID)
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
