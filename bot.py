"""
╔══════════════════════════════════════════╗
║   FX YIELD SPREAD BOT — TELEGRAM         ║
║   Group  : PETILASAN                     ║
║   Topic  : Valuasi (Thread ID: 7)        ║
║   Data   : Investing.com                 ║
║   Pairs  : 31 pair FX + GBP lengkap     ║
╚══════════════════════════════════════════╝
"""

import os, time, threading, logging, requests, schedule, random
from bs4 import BeautifulSoup
from datetime import datetime

# ──────────────────────────────────────────
#  KONFIGURASI
# ──────────────────────────────────────────
TOKEN     = os.environ.get("BOT_TOKEN", "8752357076:AAHVDQckEFwiRafaUfduHTOLwH5IC6A7fE4")
CHAT_ID   = os.environ.get("CHAT_ID",   "-1003890278221")
THREAD_ID = int(os.environ.get("THREAD_ID", "7"))
HOUR      = int(os.environ.get("SEND_HOUR",   "1"))
MINUTE    = int(os.environ.get("SEND_MINUTE", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ──────────────────────────────────────────
#  ROTASI USER AGENT — kurangi kemungkinan diblok
# ──────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

# ──────────────────────────────────────────
#  YIELD 2Y — URL INVESTING.COM
# ──────────────────────────────────────────
YIELD_URLS = {
    "US": "https://www.investing.com/rates-bonds/u.s.-2-year-bond-yield",
    "EU": "https://www.investing.com/rates-bonds/germany-2-year-bond-yield",
    "GB": "https://www.investing.com/rates-bonds/u.k.-2-year-bond-yield",
    "JP": "https://www.investing.com/rates-bonds/japan-2-year-bond-yield",
    "AU": "https://www.investing.com/rates-bonds/australia-2-year-bond-yield",
    "NZ": "https://www.investing.com/rates-bonds/new-zealand-2-year-bond-yield",
    "CA": "https://www.investing.com/rates-bonds/canada-2-year-bond-yield",
    "CH": "https://www.investing.com/rates-bonds/switzerland-2-year-bond-yield",
    "CN": "https://www.investing.com/rates-bonds/china-2-year-bond-yield",
}

# ──────────────────────────────────────────
#  31 PAIR FX LENGKAP + GBP
# ──────────────────────────────────────────
FX_PAIRS = [
    # Major USD
    ("EURUSD", "EU", "US", "eur-usd"),
    ("GBPUSD", "GB", "US", "gbp-usd"),
    ("AUDUSD", "AU", "US", "aud-usd"),
    ("NZDUSD", "NZ", "US", "nzd-usd"),
    ("USDJPY", "US", "JP", "usd-jpy"),
    ("USDCAD", "US", "CA", "usd-cad"),
    ("USDCHF", "US", "CH", "usd-chf"),
    ("USDCNH", "US", "CN", "usd-cnh"),
    # EUR cross
    ("EURGBP", "EU", "GB", "eur-gbp"),
    ("EURJPY", "EU", "JP", "eur-jpy"),
    ("EURCAD", "EU", "CA", "eur-cad"),
    ("EURCHF", "EU", "CH", "eur-chf"),
    ("EURNZD", "EU", "NZ", "eur-nzd"),
    ("EURAUD", "EU", "AU", "eur-aud"),
    # GBP cross
    ("GBPJPY", "GB", "JP", "gbp-jpy"),
    ("GBPCAD", "GB", "CA", "gbp-cad"),
    ("GBPCHF", "GB", "CH", "gbp-chf"),
    ("GBPNZD", "GB", "NZ", "gbp-nzd"),
    ("GBPAUD", "GB", "AU", "gbp-aud"),
    # AUD cross
    ("AUDJPY", "AU", "JP", "aud-jpy"),
    ("AUDCAD", "AU", "CA", "aud-cad"),
    ("AUDCHF", "AU", "CH", "aud-chf"),
    ("AUDNZD", "AU", "NZ", "aud-nzd"),
    ("AUDEUR", "AU", "EU", "aud-eur"),
    ("AUDGBP", "AU", "GB", "aud-gbp"),
    # NZD cross
    ("NZDJPY", "NZ", "JP", "nzd-jpy"),
    ("NZDCAD", "NZ", "CA", "nzd-cad"),
    ("NZDCHF", "NZ", "CH", "nzd-chf"),
    ("NZDGBP", "NZ", "GB", "nzd-gbp"),
    # CAD cross
    ("CADJPY", "CA", "JP", "cad-jpy"),
    ("CADCHF", "CA", "CH", "cad-chf"),
]

# ──────────────────────────────────────────
#  SCRAPING DENGAN RETRY
# ──────────────────────────────────────────
def _parse_price(soup):
    for sel in ['[data-test="instrument-price-last"]', ".text-5xl", "#last_last"]:
        tag = soup.select_one(sel)
        if tag:
            try:
                return float(tag.get_text(strip=True).replace(",", ""))
            except ValueError:
                continue
    return None

def scrape_url(url, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.5, 3.5))  # jeda acak
            r = requests.get(url, headers=get_headers(), timeout=20)
            if r.status_code == 200:
                return _parse_price(BeautifulSoup(r.text, "lxml"))
            elif r.status_code == 403:
                log.warning(f"  403 blocked, retry {attempt+1}/{retries}...")
                time.sleep(random.uniform(5, 10))
            else:
                log.warning(f"  Status {r.status_code}")
        except Exception as e:
            log.warning(f"  Error: {e}, retry {attempt+1}/{retries}")
            time.sleep(3)
    return None

def get_all_yields():
    log.info("Scraping yield data...")
    yields = {}
    for code, url in YIELD_URLS.items():
        val = scrape_url(url)
        yields[code] = val
        log.info(f"  {code}: {val}")
    return yields

def calculate(yields):
    results = []
    for pair, base, quote, slug in FX_PAIRS:
        yb = yields.get(base)
        yq = yields.get(quote)
        if yb is None or yq is None:
            log.warning(f"  Skip {pair}: yield kosong")
            continue

        url = f"https://www.investing.com/currencies/{slug}"
        fx  = scrape_url(url)
        if fx is None:
            log.warning(f"  Skip {pair}: harga FX tidak ada")
            continue

        spread   = yb - yq
        fair     = fx / (1 + spread / 100)
        diff_pct = ((fx - fair) / fair) * 100

        if diff_pct > 0.5:
            status = "OVERVALUED"
        elif diff_pct < -0.5:
            status = "UNDERVALUED"
        else:
            status = "FAIR VALUE"

        results.append({"pair": pair, "status": status, "diff": diff_pct})
        log.info(f"  {pair}: {status} ({diff_pct:+.2f}%)")

    return results

# ──────────────────────────────────────────
#  FORMAT PESAN
# ──────────────────────────────────────────
def format_msg(results):
    now   = datetime.now().strftime("%d %b %Y %H:%M WIB")
    over  = [r for r in results if r["status"] == "OVERVALUED"]
    under = [r for r in results if r["status"] == "UNDERVALUED"]
    fair  = [r for r in results if r["status"] == "FAIR VALUE"]

    lines = [
        "📊 *YIELD SPREAD FX VALUATION*",
        f"🕐 _{now}_ | Tenor: 2Y",
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

    lines += [
        "\n━━━━━━━━━━━━━━━━━━━━━━",
        f"Total: {len(results)} pair | ⚠️ Bukan rekomendasi investasi",
    ]
    return "\n".join(lines)

# ──────────────────────────────────────────
#  TELEGRAM
# ──────────────────────────────────────────
def send_message(text, chat_id=CHAT_ID, thread_id=THREAD_ID):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "message_thread_id": thread_id,
        }, timeout=15)
        if not r.ok:
            log.error(f"Telegram error: {r.text}")
    except Exception as e:
        log.error(f"send_message error: {e}")

def get_updates(offset=0):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 30}, timeout=35
        )
        return r.json().get("result", [])
    except Exception:
        return []

# ──────────────────────────────────────────
#  PROSES YIELD
# ──────────────────────────────────────────
def run_yield(chat_id=CHAT_ID, thread_id=THREAD_ID):
    send_message("⏳ Mengambil data yield & FX...\nProses ~5-7 menit, harap tunggu.", chat_id, thread_id)
    try:
        yields  = get_all_yields()
        results = calculate(yields)
        if not results:
            send_message("⚠️ Gagal mengambil data. Coba lagi nanti.", chat_id, thread_id)
            return
        send_message(format_msg(results), chat_id, thread_id)
    except Exception as e:
        log.error(f"run_yield error: {e}")
        send_message(f"❌ Error: {e}", chat_id, thread_id)

# ──────────────────────────────────────────
#  SCHEDULER
# ──────────────────────────────────────────
def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(run_yield)
    log.info(f"Scheduler aktif — {send_time} UTC (08:00 WIB)")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ──────────────────────────────────────────
#  POLLING — hanya respon di topic Valuasi
# ──────────────────────────────────────────
def polling_loop():
    log.info("Bot berjalan...")
    offset = 0
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset  = upd["update_id"] + 1
            msg     = upd.get("message", {})
            text    = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            t_id    = msg.get("message_thread_id")

            if not text or not chat_id:
                continue
            if t_id != THREAD_ID:
                continue

            if text.startswith("/start"):
                send_message(
                    "👋 *Selamat datang di ValuasiFX Bot!*\n\n"
                    "Bot ini menganalisis valuasi mata uang berdasarkan "
                    "selisih yield obligasi 2 tahun antar negara.\n\n"
                    "📌 *Command:*\n"
                    "/yield — Cek valuasi 31 pair FX sekarang\n"
                    "/help  — Penjelasan cara kerja\n\n"
                    "⏰ Auto-kirim setiap hari jam 08:00 WIB",
                    chat_id, THREAD_ID,
                )
            elif text.startswith("/yield"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID), daemon=True).start()
            elif text.startswith("/help"):
                send_message(
                    "📖 *Cara Kerja Bot*\n\n"
                    "*Formula:*\n"
                    "`Spread = Yield Base - Yield Quote`\n"
                    "`Fair Value = Harga FX ÷ (1 + Spread%)`\n\n"
                    "*Interpretasi:*\n"
                    "🔴 OVERVALUED  → pair kemungkinan terlalu mahal\n"
                    "🟢 UNDERVALUED → pair kemungkinan terlalu murah\n"
                    "⚪ FAIR VALUE  → harga wajar secara yield\n\n"
                    "⚠️ Ini bukan rekomendasi trading.",
                    chat_id, THREAD_ID,
                )
        time.sleep(2)

# ──────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
