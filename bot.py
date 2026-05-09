"""
╔══════════════════════════════════════════╗
║   FX YIELD SPREAD BOT — TELEGRAM         ║
║   Group  : PETILASAN                     ║
║   Topic  : Valuasi                       ║
╚══════════════════════════════════════════╝
"""

import os
import time
import threading
import logging
import requests
import schedule

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
#  YIELD 2Y
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

FX_PAIRS = [
    ("EURUSD", "EU", "US", "eur-usd"),
    ("AUDUSD", "AU", "US", "aud-usd"),
    ("NZDUSD", "NZ", "US", "nzd-usd"),
    ("USDJPY", "US", "JP", "usd-jpy"),
    ("GBPUSD", "GB", "US", "gbp-usd"),
    ("USDCAD", "US", "CA", "usd-cad"),
    ("USDCHF", "US", "CH", "usd-chf"),
    ("USDCNH", "US", "CN", "usd-cnh"),
    ("AUDEUR", "AU", "EU", "aud-eur"),
    ("AUDCAD", "AU", "CA", "aud-cad"),
    ("AUDGBP", "AU", "GB", "aud-gbp"),
    ("AUDCHF", "AU", "CH", "aud-chf"),
    ("AUDJPY", "AU", "JP", "aud-jpy"),
    ("EURJPY", "EU", "JP", "eur-jpy"),
    ("GBPJPY", "GB", "JP", "gbp-jpy"),
    ("CADJPY", "CA", "JP", "cad-jpy"),
    ("NZDJPY", "NZ", "JP", "nzd-jpy"),
    ("EURNZD", "EU", "NZ", "eur-nzd"),
    ("EURCHF", "EU", "CH", "eur-chf"),
    ("NZDCHF", "NZ", "CH", "nzd-chf"),
    ("NZDGBP", "NZ", "GB", "nzd-gbp"),
    ("GBPCHF", "GB", "CH", "gbp-chf"),
    ("EURCAD", "EU", "CA", "eur-cad"),
    ("GBPCAD", "GB", "CA", "gbp-cad"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.investing.com/",
}

# ──────────────────────────────────────────
#  SCRAPING
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

def scrape_yield(country):
    try:
        r = requests.get(YIELD_URLS[country], headers=HEADERS, timeout=15)
        return _parse_price(BeautifulSoup(r.text, "lxml"))
    except Exception as e:
        log.warning(f"Yield error [{country}]: {e}")
        return None

def scrape_fx(slug):
    try:
        r = requests.get(f"https://www.investing.com/currencies/{slug}", headers=HEADERS, timeout=15)
        return _parse_price(BeautifulSoup(r.text, "lxml"))
    except Exception as e:
        log.warning(f"FX error [{slug}]: {e}")
        return None

def get_all_yields():
    yields = {}
    for code in YIELD_URLS:
        yields[code] = scrape_yield(code)
        log.info(f"  {code}: {yields[code]}")
        time.sleep(2)
    return yields

def calculate(yields):
    results = []
    for pair, base, quote, slug in FX_PAIRS:
        yb = yields.get(base)
        yq = yields.get(quote)
        if yb is None or yq is None:
            continue
        spread = yb - yq
        fx = scrape_fx(slug)
        time.sleep(1.5)
        if fx is None:
            continue
        fair = fx / (1 + spread / 100)
        diff_pct = ((fx - fair) / fair) * 100
        if diff_pct > 0.5:
            status = "OVERVALUED"
            emoji  = "🔴"
        elif diff_pct < -0.5:
            status = "UNDERVALUED"
            emoji  = "🟢"
        else:
            status = "FAIR VALUE"
            emoji  = "⚪"
        results.append({
            "pair": pair, "status": status,
            "emoji": emoji, "diff": diff_pct,
        })
    return results

# ──────────────────────────────────────────
#  FORMAT PESAN — RINGKAS
# ──────────────────────────────────────────
def format_msg(results):
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")

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
        if r.ok:
            log.info("Pesan terkirim")
        else:
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
    send_message("⏳ Mengambil data yield & FX...\nProses ~2-3 menit, harap tunggu.", chat_id, thread_id)
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
#  SCHEDULER & POLLING
# ──────────────────────────────────────────
def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(run_yield)
    log.info(f"Scheduler aktif — {send_time} UTC (08:00 WIB)")
    while True:
        schedule.run_pending()
        time.sleep(30)

def polling_loop():
    log.info("Bot berjalan...")
    offset = 0
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg     = upd.get("message", {})
            text    = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            t_id    = msg.get("message_thread_id", THREAD_ID)
            if not text or not chat_id:
                continue
            if text.startswith("/start"):
                send_message(
                    "👋 *Selamat datang di ValuasiFX Bot!*\n\n"
                    "Bot ini menganalisis valuasi mata uang berdasarkan "
                    "selisih yield obligasi 2 tahun antar negara.\n\n"
                    "📌 *Command:*\n"
                    "/yield — Cek valuasi 24 pair FX sekarang\n"
                    "/help  — Penjelasan cara kerja\n\n"
                    "⏰ Auto-kirim setiap hari jam 08:00 WIB",
                    chat_id, t_id,
                )
            elif text.startswith("/yield"):
                threading.Thread(target=run_yield, args=(chat_id, t_id), daemon=True).start()
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
                    chat_id, t_id,
                )
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
