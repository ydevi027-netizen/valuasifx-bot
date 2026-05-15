import os, time, threading, logging, requests, schedule
from datetime import datetime

TOKEN        = os.environ.get("BOT_TOKEN",      "8752357076:AAHVDQckEFwiRafaUfduHTOLwH5IC6A7fE4")
CHAT_ID      = os.environ.get("CHAT_ID",        "-1003890278221")
THREAD_ID    = int(os.environ.get("THREAD_ID",  "7"))
HOUR         = int(os.environ.get("SEND_HOUR",  "1"))
MINUTE       = int(os.environ.get("SEND_MINUTE","0"))
FINNHUB_KEY  = os.environ.get("FINNHUB_API_KEY","d80ll8pr01qt5k5vdr9gd80ll8pr01qt5k5vdra0")
RAILWAY_TOKEN   = os.environ.get("RAILWAY_TOKEN", "")
RAILWAY_PROJECT = "ccc5f65d-7b08-42cd-a3bc-6bd697fc2b09"
RAILWAY_SERVICE = "e217e8c1-80f8-4a72-9c54-83a1e9224f1a"
RAILWAY_ENV     = "813df25d-37dd-4f69-8ba1-dee73c632140"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── YIELD 2Y (load dari env vars saat startup) ──────────────────
def _env(key, fallback):
    try:
        val = os.environ.get(key)
        return float(val) if val else fallback
    except:
        return fallback

YIELDS = {
    "US": _env("YIELD_US", 3.93),
    "EU": _env("YIELD_EU", 2.05),
    "GB": _env("YIELD_GB", 4.10),
    "JP": _env("YIELD_JP", 0.35),
    "AU": _env("YIELD_AU", 3.85),
    "NZ": _env("YIELD_NZ", 3.60),
    "CA": _env("YIELD_CA", 2.90),
    "CH": _env("YIELD_CH", -0.25),
    "CN": _env("YIELD_CN", 1.50),
    "IN": _env("YIELD_IN", 6.50),
}
YIELD_SOURCES = {k: "env" for k in YIELDS}
UPDATED_AT = os.environ.get("YIELD_UPDATED_AT", "belum diupdate")

# ── 32 PAIR FX ───────────────────────────────────────────────────
FX_PAIRS = [
    ("EURUSD","EU","US"), ("GBPUSD","GB","US"),
    ("AUDUSD","AU","US"), ("NZDUSD","NZ","US"),
    ("USDJPY","US","JP"), ("USDCAD","US","CA"),
    ("USDCHF","US","CH"), ("USDCNH","US","CN"),
    ("USDINR","US","IN"),
    ("EURGBP","EU","GB"), ("EURJPY","EU","JP"),
    ("EURCAD","EU","CA"), ("EURCHF","EU","CH"),
    ("EURNZD","EU","NZ"), ("EURAUD","EU","AU"),
    ("GBPJPY","GB","JP"), ("GBPCAD","GB","CA"),
    ("GBPCHF","GB","CH"), ("GBPNZD","GB","NZ"),
    ("GBPAUD","GB","AU"), ("AUDJPY","AU","JP"),
    ("AUDCAD","AU","CA"), ("AUDCHF","AU","CH"),
    ("AUDNZD","AU","NZ"), ("AUDEUR","AU","EU"),
    ("AUDGBP","AU","GB"), ("NZDJPY","NZ","JP"),
    ("NZDCAD","NZ","CA"), ("NZDCHF","NZ","CH"),
    ("NZDGBP","NZ","GB"), ("CADJPY","CA","JP"),
    ("CADCHF","CA","CH"),
]

# ── AUTO FETCH YIELD DARI SUMBER RESMI ───────────────────────────
def fetch_ecb(maturity="SR_2Y"):
    try:
        url = f"https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{maturity}?format=csvdata&lastNObservations=5"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            header = lines[0].split(",") if lines else []
            obs_idx = next((i for i, h in enumerate(header) if "OBS_VALUE" in h.upper()), len(header)-1)
            for line in reversed(lines[1:]):
                parts = line.split(",")
                if len(parts) > obs_idx:
                    val_str = parts[obs_idx].strip()
                    if val_str and val_str not in ("", "NaN"):
                        val = float(val_str)
                        if val != 0.0:
                            return round(val, 2)
    except Exception as e:
        log.debug(f"ECB: {e}")
    return None

def fetch_rba():
    try:
        r = requests.get("https://www.rba.gov.au/statistics/tables/csv/f2-data.csv",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            col_idx, data_start = None, 0
            for i, line in enumerate(lines):
                if "2 year" in line.lower():
                    parts = line.split(",")
                    for j, p in enumerate(parts):
                        if "2 year" in p.lower():
                            col_idx, data_start = j, i+2
                            break
                    break
            if col_idx:
                for line in reversed(lines[data_start:]):
                    parts = line.split(",")
                    if len(parts) > col_idx and parts[col_idx].strip():
                        return round(float(parts[col_idx].strip()), 2)
    except Exception as e:
        log.debug(f"RBA: {e}")
    return None

def fetch_fred(series="DGS2"):
    try:
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            lines = [l for l in r.text.strip().splitlines() if not l.startswith("DATE") and "," in l]
            for line in reversed(lines):
                val_str = line.split(",")[1].strip()
                if val_str and val_str != ".":
                    return round(float(val_str), 2)
    except Exception as e:
        log.debug(f"FRED: {e}")
    return None

def fetch_boe():
    try:
        r = requests.get(
            "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
            "?Travel=NIxIRx&FromSeries=1&ToSeries=50&DAT=RNG"
            "&FD=01/Jan/2025&TD=01/Jan/2027&FNY=&CSVF=TT"
            "&html.x=66&html.y=26&C=IUDMNZC2&Filter=N",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200 and "," in r.text:
            lines = [l for l in r.text.strip().splitlines() if l and not l.startswith("Date")]
            for line in reversed(lines):
                parts = line.split(",")
                if len(parts) >= 2 and parts[1].strip():
                    return round(float(parts[1].strip()), 2)
    except Exception as e:
        log.debug(f"BoE: {e}")
    return None

def fetch_boc():
    try:
        r = requests.get("https://www.bankofcanada.ca/valet/observations/V39054/json?recent=5",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            for obs in reversed(r.json().get("observations", [])):
                v = obs.get("V39054", {}).get("v", "")
                if v:
                    return round(float(v), 2)
    except Exception as e:
        log.debug(f"BoC: {e}")
    return None

def fetch_rbnz():
    try:
        r = requests.get("https://www.rbnz.govt.nz/api/indicatorsdata/b2?type=json",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            for s in r.json().get("series", []):
                if "2" in str(s.get("name","")) and "year" in str(s.get("name","")).lower():
                    obs = s.get("observations", [])
                    if obs:
                        return round(float(obs[-1].get("value", 0)), 2)
    except Exception as e:
        log.debug(f"RBNZ: {e}")
    return None

def fetch_mof():
    try:
        r = requests.get("https://www.mof.go.jp/english/jgbs/reference/interest_rate/jgbcme.csv",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            header = lines[0].split(",") if lines else []
            col_idx = next((i for i, h in enumerate(header) if "2Y" in h.upper() or "2 Y" in h.upper()), None)
            if col_idx and len(lines) > 1:
                parts = lines[-1].split(",")
                if len(parts) > col_idx and parts[col_idx].strip():
                    return round(float(parts[col_idx].strip()), 2)
    except Exception as e:
        log.debug(f"MOF: {e}")
    return None

def fetch_snb():
    try:
        r = requests.get("https://data.snb.ch/api/serie/rendoblim/CHF/D2/json?lastNObservations=5",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            obs = r.json().get("data", {}).get("observations", [])
            for o in reversed(obs):
                if o.get("value") is not None:
                    return round(float(o["value"]), 2)
    except Exception as e:
        log.debug(f"SNB: {e}")
    return None

def fetch_rbi():
    """India 2Y — RBI (Reserve Bank of India)"""
    try:
        r = requests.get(
            "https://api.rbi.org.in/api/GSecYields?YieldDate=&type=json",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for item in data:
                if "2" in str(item.get("MaturityYear", "")):
                    return round(float(item.get("Yield", 0)), 2)
    except Exception as e:
        log.debug(f"RBI: {e}")
    # Fallback: scrape dari investing.com tidak memungkinkan, pakai env var
    return None

FETCH_FUNCS = {
    "US": fetch_fred,
    "EU": fetch_ecb,
    "GB": fetch_boe,
    "CA": fetch_boc,
    "AU": fetch_rba,
    "NZ": fetch_rbnz,
    "JP": fetch_mof,
    "CH": fetch_snb,
    "IN": fetch_rbi,
    "CN": None,  # ChinaBond tidak bisa diakses, manual saja
}

def auto_fetch_yields():
    global YIELDS, YIELD_SOURCES, UPDATED_AT
    log.info("Auto-fetch yield dari sumber resmi...")
    success = []
    failed = []
    for country, func in FETCH_FUNCS.items():
        if func is None:
            failed.append(country)
            continue
        try:
            val = func()
            if val is not None and -5 < val < 25:
                YIELDS[country] = val
                YIELD_SOURCES[country] = "auto"
                success.append(f"{country}:{val}%")
                log.info(f"  {country}: {val}% [auto]")
            else:
                failed.append(country)
                log.warning(f"  {country}: gagal — pakai {YIELDS[country]}%")
        except Exception as e:
            failed.append(country)
            log.warning(f"  {country}: error {e}")
    UPDATED_AT = datetime.now().strftime("%d %b %Y %H:%M WIB")
    log.info(f"Auto: {success} | Fallback: {failed}")

# ── FX REAL-TIME DARI FINNHUB ────────────────────────────────────
def get_fx_quote(symbol):
    """Ambil harga FX dan daily change% dari Finnhub."""
    try:
        # Format Finnhub: OANDA:EUR_USD
        sym = symbol[:3] + "_" + symbol[3:]
        r = requests.get(
            f"https://finnhub.io/api/v1/forex/candle",
            params={
                "symbol": f"OANDA:{sym}",
                "resolution": "D",
                "count": 2,
                "token": FINNHUB_KEY
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            closes = data.get("c", [])
            if len(closes) >= 2:
                prev = closes[-2]
                curr = closes[-1]
                change_pct = ((curr - prev) / prev) * 100
                return round(curr, 5), round(change_pct, 2)
    except Exception as e:
        log.debug(f"Finnhub {symbol}: {e}")
    return None, None

def get_all_fx_finnhub():
    """Ambil semua FX dari Finnhub dengan daily change%."""
    log.info("Mengambil FX dari Finnhub...")
    fx_data = {}
    pairs = list(set([p[0] for p in FX_PAIRS]))
    for pair in pairs:
        price, change = get_fx_quote(pair)
        fx_data[pair] = {"price": price, "change": change}
        time.sleep(0.1)  # rate limit
    return fx_data

def get_all_fx_fallback():
    """Fallback: ambil harga FX dari fxratesapi."""
    rates = {}
    try:
        r = requests.get(
            "https://api.fxratesapi.com/latest?base=USD&currencies=EUR,GBP,AUD,NZD,JPY,CAD,CHF,CNH,CNY,INR",
            timeout=15)
        data = r.json()
        if data.get("rates"):
            rates = data["rates"]
            rates["USD"] = 1.0
    except:
        pass
    return rates

# ── KALKULASI VALUASI ─────────────────────────────────────────────
def calculate_new(fx_data):
    """
    Formula baru:
    Yield Spread% = Yield Base - Yield Quote
    FX Change% = perubahan harga FX harian
    Jika FX Change% > Yield Spread% → Overvalued (FX naik terlalu tinggi)
    Jika FX Change% < Yield Spread% → Undervalued
    """
    results = []
    for pair, base, quote in FX_PAIRS:
        yb = YIELDS.get(base)
        yq = YIELDS.get(quote)
        fx_info = fx_data.get(pair, {})
        fx_change = fx_info.get("change")
        fx_price = fx_info.get("price")

        if yb is None or yq is None:
            continue

        yield_spread = round(yb - yq, 2)

        if fx_change is None:
            # Fallback: pakai formula lama jika Finnhub gagal
            status = "N/A"
            results.append({
                "pair": pair, "status": status,
                "fx_pct": None, "yield_pct": yield_spread,
                "price": fx_price
            })
            continue

        diff = fx_change - yield_spread

        if diff > 0.3:
            status = "OVERVALUED"
        elif diff < -0.3:
            status = "UNDERVALUED"
        else:
            status = "FAIR VALUE"

        results.append({
            "pair": pair, "status": status,
            "fx_pct": fx_change, "yield_pct": yield_spread,
            "price": fx_price
        })
    return results

def format_msg(results):
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    auto_count = sum(1 for v in YIELD_SOURCES.values() if v == "auto")
    over  = [r for r in results if r["status"] == "OVERVALUED"]
    under = [r for r in results if r["status"] == "UNDERVALUED"]
    fair  = [r for r in results if r["status"] == "FAIR VALUE"]

    lines = [
        "*FX YIELD SPREAD VALUATION*",
        f"_{now}_",
        f"_Yield: {auto_count}/10 auto | {UPDATED_AT}_",
        "_Format: FX daily% vs Yield Spread%_",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if over:
        lines.append("\n*OVERVALUED*")
        for r in over:
            fx = f"{r['fx_pct']:+.2f}%" if r['fx_pct'] is not None else "N/A"
            lines.append(f"`{r['pair']}` : {fx} vs {r['yield_pct']:+.2f}%")
    if under:
        lines.append("\n*UNDERVALUED*")
        for r in under:
            fx = f"{r['fx_pct']:+.2f}%" if r['fx_pct'] is not None else "N/A"
            lines.append(f"`{r['pair']}` : {fx} vs {r['yield_pct']:+.2f}%")
    if fair:
        lines.append("\n*FAIR VALUE*")
        for r in fair:
            fx = f"{r['fx_pct']:+.2f}%" if r['fx_pct'] is not None else "N/A"
            lines.append(f"`{r['pair']}` : {fx} vs {r['yield_pct']:+.2f}%")

    lines += ["\n━━━━━━━━━━━━━━━━━━━━━━",
              f"Total: {len(results)} pair | Bukan rekomendasi investasi"]
    return "\n".join(lines)

# ── SIMPAN YIELD KE RAILWAY ──────────────────────────────────────
def save_to_railway():
    if not RAILWAY_TOKEN:
        return
    try:
        vars_to_set = {f"YIELD_{k}": str(v) for k, v in YIELDS.items()}
        vars_to_set["YIELD_UPDATED_AT"] = UPDATED_AT
        query = "mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) { variableCollectionUpsert(input: $input) }"
        r = requests.post(
            "https://backboard.railway.com/graphql/v2",
            json={"query": query, "variables": {"input": {
                "projectId": RAILWAY_PROJECT,
                "serviceId": RAILWAY_SERVICE,
                "environmentId": RAILWAY_ENV,
                "variables": vars_to_set
            }}},
            headers={"Authorization": f"Bearer {RAILWAY_TOKEN}", "Content-Type": "application/json"},
            timeout=15
        )
        if r.status_code == 200:
            log.info("Yield tersimpan ke Railway.")
    except Exception as e:
        log.error(f"save_to_railway: {e}")

# ── TELEGRAM ─────────────────────────────────────────────────────
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

def run_yield(chat_id=CHAT_ID, thread_id=THREAD_ID):
    send_message("Mengambil data FX real-time dari Finnhub...\nHarap tunggu ~30 detik.", chat_id, thread_id)
    try:
        fx_data = get_all_fx_finnhub()
        results = calculate_new(fx_data)
        if not results:
            send_message("Gagal ambil data.", chat_id, thread_id)
            return
        send_message(format_msg(results), chat_id, thread_id)
    except Exception as e:
        send_message(f"Error: {e}", chat_id, thread_id)

def handle_updateyield(text, chat_id, thread_id):
    global UPDATED_AT
    parts = text.replace("/updateyield", "").strip().split()
    updated, errors = {}, []
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
        UPDATED_AT = datetime.now().strftime("%d %b %Y %H:%M WIB")
        threading.Thread(target=save_to_railway, daemon=True).start()
        lines = ["*Yield 2Y diupdate!*\n"]
        for k, v in YIELDS.items():
            src = YIELD_SOURCES.get(k, "?")
            icon = "📡" if src=="auto" else ("🔄" if src=="manual" else "📌")
            mark = ">> " if k in updated else "   "
            lines.append(f"{mark}{icon}`{k}` : {v:.2f}%")
        if errors:
            lines.append(f"\nError: {', '.join(errors)}")
        send_message("\n".join(lines), chat_id, thread_id)
    else:
        send_message(
            "Format salah.\n\nContoh:\n"
            "`/updateyield US:3.99 GB:4.55 CA:2.98 NZ:3.79 JP:1.39 CH:0.15 CN:1.28 IN:6.50`",
            chat_id, thread_id)

# ── SCHEDULER ────────────────────────────────────────────────────
def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(run_yield)
    schedule.every().day.at("00:30").do(auto_fetch_yields)
    log.info(f"Scheduler: kirim {send_time} UTC | auto-fetch yield 00:30 UTC")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ── POLLING ───────────────────────────────────────────────────────
def polling_loop():
    log.info("Bot berjalan...")
    log.info(f"Yield loaded: {YIELDS}")
    threading.Thread(target=auto_fetch_yields, daemon=True).start()
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
                    "*ValuasiFX Bot v2*\n\n"
                    "*Command:*\n"
                    "/yield — Valuasi 32 pair (FX% vs Yield%)\n"
                    "/yields — Yield 2Y saat ini\n"
                    "/refreshyield — Auto-fetch yield dari bank sentral\n"
                    "/updateyield — Update yield manual\n"
                    "/help — Bantuan\n\n"
                    "📡 FX real-time dari Finnhub\n"
                    "⏰ Auto-kirim 08:00 WIB",
                    chat_id, THREAD_ID)

            elif text.startswith("/yield") and not text.startswith("/yields") and not text.startswith("/updateyield"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/yields"):
                lines = [f"*YIELD 2Y SAAT INI*\n_{UPDATED_AT}_\n"]
                for k, v in YIELDS.items():
                    src = YIELD_SOURCES.get(k, "?")
                    icon = "📡" if src=="auto" else ("🔄" if src=="manual" else "📌")
                    lines.append(f"{icon}`{k}` : {v:.2f}%")
                lines.append("\n📡=auto | 🔄=manual | 📌=env")
                send_message("\n".join(lines), chat_id, THREAD_ID)

            elif text.startswith("/refreshyield"):
                send_message("🔄 Fetching yield dari bank sentral...\nHarap tunggu ~30 detik.", chat_id, thread_id)
                def do_refresh(cid, tid):
                    auto_fetch_yields()
                    auto = sum(1 for s in YIELD_SOURCES.values() if s == "auto")
                    save_to_railway()
                    send_message(
                        f"✅ *Yield di-refresh!*\n"
                        f"📡 Auto: {auto}/10\n"
                        f"🕐 {UPDATED_AT}\n\n"
                        f"Ketik /yields untuk lihat nilai.", cid, tid)
                threading.Thread(target=do_refresh, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/updateyield"):
                handle_updateyield(text, chat_id, THREAD_ID)

            elif text.startswith("/help"):
                send_message(
                    "*Cara Kerja Bot v2*\n\n"
                    "*Formula:*\n"
                    "FX Daily Change% vs Yield Spread%\n"
                    "Jika FX% > Yield% → OVERVALUED\n"
                    "Jika FX% < Yield% → UNDERVALUED\n\n"
                    "*Update yield manual:*\n"
                    "`/updateyield US:3.99 GB:4.55 CA:2.98`\n"
                    "`/updateyield IN:6.50 CN:1.28`\n\n"
                    "*Pair tersedia:* 32 pair + USDINR\n"
                    "⚠️ Bukan rekomendasi trading.",
                    chat_id, THREAD_ID)
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
