import os, time, threading, logging, requests, schedule, json
from datetime import datetime

TOKEN        = os.environ.get("BOT_TOKEN",      "8752357076:AAHVDQckEFwiRafaUfduHTOLwH5IC6A7fE4")
CHAT_ID      = os.environ.get("CHAT_ID",        "-1003890278221")
THREAD_ID    = int(os.environ.get("THREAD_ID",  "7"))
HOUR         = int(os.environ.get("SEND_HOUR",  "1"))
MINUTE       = int(os.environ.get("SEND_MINUTE","0"))
RAILWAY_TOKEN   = os.environ.get("RAILWAY_TOKEN", "")
RAILWAY_PROJECT = "ccc5f65d-7b08-42cd-a3bc-6bd697fc2b09"
RAILWAY_SERVICE = "e217e8c1-80f8-4a72-9c54-83a1e9224f1a"
RAILWAY_ENV     = "813df25d-37dd-4f69-8ba1-dee73c632140"

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
}
UPDATED_AT = os.environ.get("YIELD_UPDATED_AT", "belum diupdate")

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

def save_to_railway():
    if not RAILWAY_TOKEN:
        return
    try:
        vars_to_set = {
            "YIELD_US": str(YIELDS.get("US","")),
            "YIELD_EU": str(YIELDS.get("EU","")),
            "YIELD_GB": str(YIELDS.get("GB","")),
            "YIELD_JP": str(YIELDS.get("JP","")),
            "YIELD_AU": str(YIELDS.get("AU","")),
            "YIELD_NZ": str(YIELDS.get("NZ","")),
            "YIELD_CA": str(YIELDS.get("CA","")),
            "YIELD_CH": str(YIELDS.get("CH","")),
            "YIELD_CN": str(YIELDS.get("CN","")),
            "YIELD_UPDATED_AT": UPDATED_AT,
        }
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
        else:
            log.warning(f"Railway API: {r.status_code}")
    except Exception as e:
        log.error(f"save_to_railway: {e}")

def get_all_fx():
    rates = {}
    try:
        r = requests.get(
            "https://api.fxratesapi.com/latest?base=USD&currencies=EUR,GBP,AUD,NZD,JPY,CAD,CHF,CNH,CNY",
            timeout=15)
        data = r.json()
        if data.get("rates"):
            rates = data["rates"]
            rates["USD"] = 1.0
    except:
        pass
    if not rates:
        try:
            r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
            data2 = r2.json()
            if data2.get("result") == "success":
                rates = data2["rates"]
                rates["USD"] = 1.0
        except:
            pass
    fx = {}
    for pair, _, _, b, q in FX_PAIRS:
        try:
            bc = "CNY" if b == "CNH" else b
            qc = "CNY" if q == "CNH" else q
            if bc == "USD": price = rates.get(qc)
            elif qc == "USD":
                rate = rates.get(bc)
                price = 1/rate if rate else None
            else:
                rb, rq = rates.get(bc), rates.get(qc)
                price = rq/rb if (rb and rq) else None
            fx[pair] = price
        except:
            fx[pair] = None
    return fx

def calculate(fx_prices):
    results = []
    for pair, base, quote, _, _ in FX_PAIRS:
        yb = YIELDS.get(base)
        yq = YIELDS.get(quote)
        fx = fx_prices.get(pair)
        if yb is None or yq is None or fx is None:
            continue
        spread = yb - yq
        fair = fx / (1 + spread/100)
        diff = ((fx - fair) / fair) * 100
        status = "OVERVALUED" if diff > 0.5 else ("UNDERVALUED" if diff < -0.5 else "FAIR VALUE")
        results.append({"pair": pair, "status": status, "diff": diff})
    return results

def format_msg(results):
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
        lines.append("\n*OVERVALUED*")
        for r in over: lines.append(f"`{r['pair']}` : Overvalued ({r['diff']:+.2f}%)")
    if under:
        lines.append("\n*UNDERVALUED*")
        for r in under: lines.append(f"`{r['pair']}` : Undervalued ({r['diff']:+.2f}%)")
    if fair:
        lines.append("\n*FAIR VALUE*")
        for r in fair: lines.append(f"`{r['pair']}` : Fair Value ({r['diff']:+.2f}%)")
    lines += ["\n━━━━━━━━━━━━━━━━━━━━━━",
              f"Total: {len(results)} pair | Bukan rekomendasi investasi"]
    return "\n".join(lines)

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
        fx = get_all_fx()
        results = calculate(fx)
        if not results:
            send_message("Gagal ambil data FX.", chat_id, thread_id)
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
            "`/updateyield US:3.99 GB:4.55 CA:2.98 NZ:3.79 JP:1.39 CH:0.15 CN:1.28`",
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
                    "/yield - Valuasi 31 pair\n"
                    "/yields - Yield 2Y saat ini\n"
                    "/updateyield - Update yield\n"
                    "/help - Bantuan",
                    chat_id, THREAD_ID)
            elif text.startswith("/yield") and not text.startswith("/yields") and not text.startswith("/updateyield"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID), daemon=True).start()
            elif text.startswith("/yields"):
                lines = [f"*YIELD 2Y*\n_{UPDATED_AT}_\n"]
                for k, v in YIELDS.items():
                    lines.append(f"`{k}` : {v:.2f}%")
                send_message("\n".join(lines), chat_id, THREAD_ID)
            elif text.startswith("/updateyield"):
                handle_updateyield(text, chat_id, THREAD_ID)
            elif text.startswith("/help"):
                send_message(
                    "*Cara pakai:*\n"
                    "`/updateyield US:3.99 GB:4.55 CA:2.98 NZ:3.79 JP:1.39 CH:0.15 CN:1.28`\n\n"
                    "Yield tidak hilang saat restart.",
                    chat_id, THREAD_ID)
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
