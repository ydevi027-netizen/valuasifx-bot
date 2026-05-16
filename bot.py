import os, time, threading, logging, requests, schedule, json
from datetime import datetime, timedelta

TOKEN        = os.environ.get("BOT_TOKEN",      "8752357076:AAHVDQckEFwiRafaUfduHTOLwH5IC6A7fE4")
CHAT_ID      = os.environ.get("CHAT_ID",        "-1003890278221")
THREAD_ID    = int(os.environ.get("THREAD_ID",  "7"))
HOUR         = int(os.environ.get("SEND_HOUR",  "1"))
MINUTE       = int(os.environ.get("SEND_MINUTE","0"))
RAILWAY_TOKEN   = os.environ.get("RAILWAY_TOKEN", "")
RAILWAY_PROJECT = "ccc5f65d-7b08-42cd-a3bc-6bd697fc2b09"
RAILWAY_SERVICE = os.environ.get("RAILWAY_SERVICE_ID", "")
RAILWAY_ENV     = os.environ.get("RAILWAY_ENV_ID", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

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
UPDATED_AT = os.environ.get("YIELD_UPDATED_AT", "belum diupdate")

# Simpan harga FX kemarin di memori
FX_YESTERDAY = {}

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

# ── AMBIL HARGA FX HARI INI ──────────────────────────────────────
def get_fx_rates(date_str=None):
    """Ambil harga FX. date_str format: YYYY-MM-DD untuk historical."""
    rates = {}
    try:
        if date_str:
            # Historical dari exchangerate.host
            r = requests.get(
                f"https://api.exchangerate.host/{date_str}",
                params={"base": "USD", "symbols": "EUR,GBP,AUD,NZD,JPY,CAD,CHF,CNY,INR"},
                timeout=15)
            data = r.json()
            if data.get("success") and data.get("rates"):
                rates = data["rates"]
                rates["USD"] = 1.0
                log.info(f"FX historical {date_str} dari exchangerate.host OK")
        else:
            # Hari ini dari fxratesapi
            r = requests.get(
                "https://api.fxratesapi.com/latest?base=USD"
                "&currencies=EUR,GBP,AUD,NZD,JPY,CAD,CHF,CNH,CNY,INR",
                timeout=15)
            data = r.json()
            if data.get("rates"):
                rates = data["rates"]
                rates["USD"] = 1.0
                log.info("FX today dari fxratesapi OK")
    except Exception as e:
        log.warning(f"get_fx_rates: {e}")

    # Fallback ke open.er-api
    if not rates:
        try:
            url = f"https://open.er-api.com/v6/{'latest' if not date_str else date_str}/USD"
            r2 = requests.get(url, timeout=15)
            data2 = r2.json()
            if data2.get("result") == "success" or data2.get("rates"):
                rates = data2["rates"]
                rates["USD"] = 1.0
                log.info(f"FX dari open.er-api OK")
        except Exception as e2:
            log.error(f"open.er-api: {e2}")

    return rates

def calc_price(pair, rates):
    b = pair[:3]
    q = pair[3:]
    bc = "CNY" if b == "CNH" else b
    qc = "CNY" if q == "CNH" else q
    try:
        if bc == "USD":
            return rates.get(qc)
        elif qc == "USD":
            rate = rates.get(bc)
            return round(1/rate, 5) if rate else None
        else:
            rb, rq = rates.get(bc), rates.get(qc)
            return round(rq/rb, 5) if (rb and rq) else None
    except:
        return None

# ── FETCH HARGA KEMARIN ──────────────────────────────────────────
def fetch_yesterday_prices():
    """Ambil harga FX kemarin dan simpan ke memori."""
    global FX_YESTERDAY
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    log.info(f"Fetching harga kemarin {yesterday}...")
    rates_yday = get_fx_rates(date_str=yesterday)
    if rates_yday:
        for pair, _, _ in FX_PAIRS:
            price = calc_price(pair, rates_yday)
            if price:
                FX_YESTERDAY[pair] = price
        log.info(f"Harga kemarin tersimpan: {len(FX_YESTERDAY)} pair")
    else:
        log.warning("Gagal fetch harga kemarin")

# ── KALKULASI METODE A: FX Daily Change% vs Yield Spread% ────────
def calculate_method_a(rates_today):
    """
    Metode A: Pakai perubahan harga FX harian.
    FX% = (Harga Hari Ini - Harga Kemarin) / Harga Kemarin × 100
    Yield% = Yield Base - Yield Quote
    Overvalued jika FX% > Yield%
    """
    results = []
    for pair, base, quote in FX_PAIRS:
        yb = YIELDS.get(base)
        yq = YIELDS.get(quote)
        price_today = calc_price(pair, rates_today)
        price_yday = FX_YESTERDAY.get(pair)

        if yb is None or yq is None or price_today is None:
            continue

        yield_spread = round(yb - yq, 2)

        if price_yday and price_yday != 0:
            fx_change = round(((price_today - price_yday) / price_yday) * 100, 2)
        else:
            fx_change = None

        if fx_change is not None:
            diff = fx_change - yield_spread
            if diff > 0.3:
                status = "OVERVALUED"
            elif diff < -0.3:
                status = "UNDERVALUED"
            else:
                status = "FAIR VALUE"
        else:
            # Fallback ke metode B jika tidak ada data kemarin
            status = "N/A"

        results.append({
            "pair": pair, "status": status,
            "fx_pct": fx_change, "yield_pct": yield_spread,
            "price": price_today
        })
    return results

# ── KALKULASI METODE B: Fair Value berdasarkan Yield Spread ──────
def calculate_method_b(rates_today):
    """
    Metode B: Hitung Fair Value dari yield spread.
    Fair Value = Harga FX / (1 + Spread%)
    Diff% = (Harga - Fair) / Fair × 100
    """
    results = []
    for pair, base, quote in FX_PAIRS:
        yb = YIELDS.get(base)
        yq = YIELDS.get(quote)
        price = calc_price(pair, rates_today)

        if yb is None or yq is None or price is None:
            continue

        spread = yb - yq
        fair = price / (1 + spread/100)
        diff = round(((price - fair) / fair) * 100, 2)
        yield_spread = round(spread, 2)

        if diff > 0.5:
            status = "OVERVALUED"
        elif diff < -0.5:
            status = "UNDERVALUED"
        else:
            status = "FAIR VALUE"

        results.append({
            "pair": pair, "status": status,
            "fx_pct": diff, "yield_pct": yield_spread,
            "price": price
        })
    return results

# ── FORMAT PESAN ─────────────────────────────────────────────────
def format_results(results, method="A"):
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    over  = [r for r in results if r["status"] == "OVERVALUED"]
    under = [r for r in results if r["status"] == "UNDERVALUED"]
    fair  = [r for r in results if r["status"] == "FAIR VALUE"]

    if method == "A":
        title = "VALUASI — FX Daily% vs Yield Spread%"
        header = "Pair       FX%      Yield%"
    else:
        title = "VALUASI — Fair Value vs Yield Spread%"
        header = "Pair       Diff%    Yield%"

    lines = [
        f"*{title}*",
        f"_{now}_",
        f"_Yield: {UPDATED_AT}_",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if over:
        lines.append("\n*🔴 OVERVALUED*")
        lines.append(f"`{header}`")
        for r in over:
            fx = f"{r['fx_pct']:+.2f}%" if r['fx_pct'] is not None else "N/A "
            lines.append(f"`{r['pair']:<8}  {fx:>7}  >  {r['yield_pct']:+.2f}%`")

    if under:
        lines.append("\n*🟢 UNDERVALUED*")
        lines.append(f"`{header}`")
        for r in under:
            fx = f"{r['fx_pct']:+.2f}%" if r['fx_pct'] is not None else "N/A "
            lines.append(f"`{r['pair']:<8}  {fx:>7}  <  {r['yield_pct']:+.2f}%`")

    if fair:
        lines.append("\n*⚪ FAIR VALUE*")
        lines.append(f"`{header}`")
        for r in fair:
            fx = f"{r['fx_pct']:+.2f}%" if r['fx_pct'] is not None else "N/A "
            lines.append(f"`{r['pair']:<8}  {fx:>7}  ≈  {r['yield_pct']:+.2f}%`")

    lines += ["\n━━━━━━━━━━━━━━━━━━━━━━",
              f"Total: {len([r for r in results if r['status'] != 'N/A'])} pair | Bukan rekomendasi investasi"]
    return "\n".join(lines)

def format_forex(rates):
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    lines = [f"*HARGA FOREX SAAT INI*", f"_{now}_\n"]
    for pair, _, _ in FX_PAIRS:
        price = calc_price(pair, rates)
        if price:
            yday = FX_YESTERDAY.get(pair)
            if yday:
                chg = round(((price - yday) / yday) * 100, 2)
                arrow = "📈" if chg > 0 else "📉" if chg < 0 else "➡️"
                lines.append(f"`{pair:<8}` {price} {arrow} {chg:+.2f}%")
            else:
                lines.append(f"`{pair:<8}` {price}")
    return "\n".join(lines)

# ── SIMPAN KE RAILWAY ────────────────────────────────────────────
def save_to_railway():
    if not RAILWAY_TOKEN or not RAILWAY_SERVICE or not RAILWAY_ENV:
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

def run_yield_a(chat_id=CHAT_ID, thread_id=THREAD_ID):
    """Metode A: FX Daily Change% vs Yield Spread%"""
    send_message("Mengambil data FX...", chat_id, thread_id)
    try:
        if not FX_YESTERDAY:
            fetch_yesterday_prices()
        rates = get_fx_rates()
        if not rates:
            send_message("Gagal ambil data FX.", chat_id, thread_id)
            return
        results = calculate_method_a(rates)
        send_message(format_results(results, method="A"), chat_id, thread_id)
    except Exception as e:
        send_message(f"Error: {e}", chat_id, thread_id)

def run_yield_b(chat_id=CHAT_ID, thread_id=THREAD_ID):
    """Metode B: Fair Value vs Yield Spread%"""
    send_message("Mengambil data FX...", chat_id, thread_id)
    try:
        rates = get_fx_rates()
        if not rates:
            send_message("Gagal ambil data FX.", chat_id, thread_id)
            return
        results = calculate_method_b(rates)
        send_message(format_results(results, method="B"), chat_id, thread_id)
    except Exception as e:
        send_message(f"Error: {e}", chat_id, thread_id)

def run_forex(chat_id=CHAT_ID, thread_id=THREAD_ID):
    send_message("Mengambil harga FX...", chat_id, thread_id)
    try:
        if not FX_YESTERDAY:
            fetch_yesterday_prices()
        rates = get_fx_rates()
        if not rates:
            send_message("Gagal ambil data FX.", chat_id, thread_id)
            return
        send_message(format_forex(rates), chat_id, thread_id)
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
            updated[code] = float(val)
        except:
            errors.append(f"Format salah: {part}")
    if updated:
        UPDATED_AT = datetime.now().strftime("%d %b %Y %H:%M WIB")
        threading.Thread(target=save_to_railway, daemon=True).start()
        lines = ["*Yield 2Y diupdate!*\n"]
        for k, v in YIELDS.items():
            mark = ">> " if k in updated else "   "
            lines.append(f"{mark}`{k}` : {v:.2f}%")
        lines.append(f"\nUpdate: {UPDATED_AT}")
        if errors:
            lines.append(f"Error: {', '.join(errors)}")
        send_message("\n".join(lines), chat_id, thread_id)
    else:
        send_message(
            "Format salah.\n\nContoh:\n"
            "`/updateyield US:4.00 GB:4.48 CA:2.96 NZ:3.73 JP:1.40 CH:0.14 CN:1.27 IN:8.10`",
            chat_id, thread_id)

# ── SCHEDULER ────────────────────────────────────────────────────
def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(lambda: run_yield_b())
    # Fetch harga kemarin setiap hari jam 00:05 UTC
    schedule.every().day.at("00:05").do(fetch_yesterday_prices)
    log.info(f"Scheduler: kirim {send_time} UTC")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ── POLLING ───────────────────────────────────────────────────────
def polling_loop():
    log.info("Bot berjalan...")
    # Fetch harga kemarin saat startup
    threading.Thread(target=fetch_yesterday_prices, daemon=True).start()
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
                    "*ValuasiFX Bot*\n\n"
                    "*Command:*\n"
                    "/yield — Valuasi metode B (Fair Value)\n"
                    "/yieldA — Valuasi metode A (FX Daily%)\n"
                    "/forex — Harga 32 pair + daily change\n"
                    "/yields — Yield 2Y saat ini\n"
                    "/updateyield — Update yield manual\n"
                    "/help — Bantuan\n\n"
                    "⏰ Auto-kirim 08:00 WIB",
                    chat_id, THREAD_ID)

            elif text.startswith("/yieldA") or text.startswith("/yielda"):
                threading.Thread(target=run_yield_a, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/yield") and not text.startswith("/yields") and not text.startswith("/updateyield"):
                threading.Thread(target=run_yield_b, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/forex"):
                threading.Thread(target=run_forex, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/yields"):
                lines = [f"*YIELD 2Y SAAT INI*\n_{UPDATED_AT}_\n"]
                for k, v in YIELDS.items():
                    lines.append(f"`{k}` : {v:.2f}%")
                send_message("\n".join(lines), chat_id, THREAD_ID)

            elif text.startswith("/updateyield"):
                handle_updateyield(text, chat_id, THREAD_ID)

            elif text.startswith("/help"):
                send_message(
                    "*Cara Kerja Bot*\n\n"
                    "*Metode B (/yield):*\n"
                    "Fair Value = Harga / (1 + Yield Spread%)\n"
                    "Diff% = (Harga - Fair) / Fair × 100\n\n"
                    "*Metode A (/yieldA):*\n"
                    "FX Daily% = (Hari ini - Kemarin) / Kemarin × 100\n"
                    "Bandingkan dengan Yield Spread%\n\n"
                    "*Update yield:*\n"
                    "`/updateyield US:4.00 GB:4.48`\n\n"
                    "⚠️ Bukan rekomendasi trading.",
                    chat_id, THREAD_ID)
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
