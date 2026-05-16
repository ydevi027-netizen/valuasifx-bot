import os, time, threading, logging, requests, schedule
from datetime import datetime

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

def get_fx_rates():
    """Ambil harga FX dari fxratesapi, fallback ke open.er-api."""
    rates = {}
    try:
        r = requests.get(
            "https://api.fxratesapi.com/latest?base=USD"
            "&currencies=EUR,GBP,AUD,NZD,JPY,CAD,CHF,CNH,CNY,INR",
            timeout=15)
        data = r.json()
        if data.get("rates"):
            rates = data["rates"]
            rates["USD"] = 1.0
            log.info("FX dari fxratesapi OK")
    except Exception as e:
        log.warning(f"fxratesapi: {e}")

    if not rates:
        try:
            r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
            data2 = r2.json()
            if data2.get("result") == "success":
                rates = data2["rates"]
                rates["USD"] = 1.0
                log.info("FX dari open.er-api OK")
        except Exception as e2:
            log.error(f"open.er-api: {e2}")

    return rates

def calc_price(pair, rates):
    """Hitung harga pair dari rates USD-based."""
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

def calculate(rates):
    """Hitung valuasi: Fair Value berdasarkan yield spread."""
    results = []
    for pair, base, quote in FX_PAIRS:
        yb = YIELDS.get(base)
        yq = YIELDS.get(quote)
        price = calc_price(pair, rates)
        if yb is None or yq is None or price is None:
            continue
        spread = yb - yq
        fair = price / (1 + spread/100)
        diff = ((price - fair) / fair) * 100
        yield_spread = round(spread, 2)
        if diff > 0.5:
            status = "OVERVALUED"
        elif diff < -0.5:
            status = "UNDERVALUED"
        else:
            status = "FAIR VALUE"
        results.append({
            "pair": pair, "status": status,
            "diff": round(diff, 2), "spread": yield_spread,
            "price": price
        })
    return results

def format_valuation(results):
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    over  = [r for r in results if r["status"] == "OVERVALUED"]
    under = [r for r in results if r["status"] == "UNDERVALUED"]
    fair  = [r for r in results if r["status"] == "FAIR VALUE"]
    lines = [
        "*YIELD SPREAD FX VALUATION*",
        f"_{now}_",
        f"_Yield: {UPDATED_AT}_",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if over:
        lines.append("\n*🔴 OVERVALUED* — FX > YIELD")
        lines.append("`Pair      FX%     > Yield%`")
        for r in over:
            fx_str = f"{r['diff']:+.2f}%"
            ys_str = f"{r['spread']:+.2f}%"
            lines.append(f"`{r['pair']:<8}` {fx_str:>7} `>` {ys_str}")
    if under:
        lines.append("\n*🟢 UNDERVALUED* — FX < YIELD")
        lines.append("`Pair      FX%     < Yield%`")
        for r in under:
            fx_str = f"{r['diff']:+.2f}%"
            ys_str = f"{r['spread']:+.2f}%"
            lines.append(f"`{r['pair']:<8}` {fx_str:>7} `<` {ys_str}")
    if fair:
        lines.append("\n*⚪ FAIR VALUE* — FX ≈ YIELD")
        lines.append("`Pair      FX%     ≈ Yield%`")
        for r in fair:
            fx_str = f"{r['diff']:+.2f}%"
            ys_str = f"{r['spread']:+.2f}%"
            lines.append(f"`{r['pair']:<8}` {fx_str:>7} `≈` {ys_str}")
    lines += ["\n━━━━━━━━━━━━━━━━━━━━━━",
              f"Total: {len(results)} pair | Bukan rekomendasi investasi"]
    return "\n".join(lines)

def format_forex(rates):
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    lines = [f"*HARGA FOREX SAAT INI*", f"_{now}_\n"]
    for pair, _, _ in FX_PAIRS:
        price = calc_price(pair, rates)
        if price:
            lines.append(f"`{pair}` : {price}")
    return "\n".join(lines)

def save_to_railway():
    """Simpan yield ke Railway Variables."""
    if not RAILWAY_TOKEN or not RAILWAY_SERVICE or not RAILWAY_ENV:
        log.warning("Railway config tidak lengkap, skip save.")
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
        if r.status_code == 200 and not r.json().get("errors"):
            log.info("Yield tersimpan ke Railway.")
        else:
            log.warning(f"Railway: {r.text[:100]}")
    except Exception as e:
        log.error(f"save_to_railway: {e}")

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
    send_message("Mengambil data FX...", chat_id, thread_id)
    try:
        rates = get_fx_rates()
        if not rates:
            send_message("Gagal ambil data FX. Coba lagi.", chat_id, thread_id)
            return
        results = calculate(rates)
        send_message(format_valuation(results), chat_id, thread_id)
    except Exception as e:
        log.error(f"run_yield: {e}")
        send_message(f"Error: {e}", chat_id, thread_id)

def run_forex(chat_id=CHAT_ID, thread_id=THREAD_ID):
    send_message("Mengambil harga FX...", chat_id, thread_id)
    try:
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

def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(run_yield)
    log.info(f"Scheduler: {send_time} UTC")
    while True:
        schedule.run_pending()
        time.sleep(30)

def polling_loop():
    log.info("Bot berjalan...")
    log.info(f"Yield: {YIELDS}")
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
                    "/yield — Valuasi 32 pair FX\n"
                    "/forex — Harga 32 pair FX saat ini\n"
                    "/yields — Yield 2Y saat ini\n"
                    "/updateyield — Update yield manual\n"
                    "/help — Bantuan\n\n"
                    "⏰ Auto-kirim 08:00 WIB",
                    chat_id, THREAD_ID)

            elif text.startswith("/yield") and not text.startswith("/yields") and not text.startswith("/updateyield"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID), daemon=True).start()

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
                    "*Formula:*\n"
                    "Spread = Yield Base - Yield Quote\n"
                    "Fair Value = Harga FX / (1 + Spread%)\n"
                    "Diff% = (Harga - Fair) / Fair x 100\n\n"
                    "*Update yield (seminggu sekali):*\n"
                    "`/updateyield US:4.00 GB:4.48 CA:2.96`\n\n"
                    "⚠️ Bukan rekomendasi trading.",
                    chat_id, THREAD_ID)
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
