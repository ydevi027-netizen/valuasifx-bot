"""
╔══════════════════════════════════════════╗
║   FX YIELD SPREAD BOT — TELEGRAM         ║
║   Group  : PETILASAN                     ║
║   Topic  : Valuasi (Thread ID: 7)        ║
║   Data   : yfinance (Yahoo Finance)      ║
║   Pairs  : 31 pair FX                   ║
╚══════════════════════════════════════════╝
"""

import os
import time
import threading
import logging
import requests
import schedule
import yfinance as yf

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
#  YIELD 2Y — Yahoo Finance symbols
# ──────────────────────────────────────────
YIELD_SYMBOLS = {
    "US": "^IRX",       # Proxy: US 13W, kita pakai TNX sebagai 2Y proxy
    "US": "2YY=F",      # US 2Y futures
    "EU": "DE2YT=RR",   # Germany 2Y
    "GB": "GB2YT=RR",   # UK 2Y
    "JP": "JP2YT=RR",   # Japan 2Y
    "AU": "AU2YT=RR",   # Australia 2Y
    "NZ": "NZ2YT=RR",   # New Zealand 2Y
    "CA": "CA2YT=RR",   # Canada 2Y
    "CH": "CH2YT=RR",   # Switzerland 2Y
    "CN": "CN2YT=RR",   # China 2Y
}

# ──────────────────────────────────────────
#  31 PAIR FX — Yahoo Finance symbols
# pair, base_yield, quote_yield, yahoo_symbol
# ──────────────────────────────────────────
FX_PAIRS = [
    # Major USD
    ("EURUSD", "EU", "US", "EURUSD=X"),
    ("GBPUSD", "GB", "US", "GBPUSD=X"),
    ("AUDUSD", "AU", "US", "AUDUSD=X"),
    ("NZDUSD", "NZ", "US", "NZDUSD=X"),
    ("USDJPY", "US", "JP", "USDJPY=X"),
    ("USDCAD", "US", "CA", "USDCAD=X"),
    ("USDCHF", "US", "CH", "USDCHF=X"),
    ("USDCNH", "US", "CN", "USDCNH=X"),
    # EUR cross
    ("EURGBP", "EU", "GB", "EURGBP=X"),
    ("EURJPY", "EU", "JP", "EURJPY=X"),
    ("EURCAD", "EU", "CA", "EURCAD=X"),
    ("EURCHF", "EU", "CH", "EURCHF=X"),
    ("EURNZD", "EU", "NZ", "EURNZD=X"),
    ("EURAUD", "EU", "AU", "EURAUD=X"),
    # GBP cross
    ("GBPJPY", "GB", "JP", "GBPJPY=X"),
    ("GBPCAD", "GB", "CA", "GBPCAD=X"),
    ("GBPCHF", "GB", "CH", "GBPCHF=X"),
    ("GBPNZD", "GB", "NZ", "GBPNZD=X"),
    ("GBPAUD", "GB", "AU", "GBPAUD=X"),
    # AUD cross
    ("AUDJPY", "AU", "JP", "AUDJPY=X"),
    ("AUDCAD", "AU", "CA", "AUDCAD=X"),
    ("AUDCHF", "AU", "CH", "AUDCHF=X"),
    ("AUDNZD", "AU", "NZ", "AUDNZD=X"),
    ("AUDEUR", "AU", "EU", "AUDEUR=X"),
    ("AUDGBP", "AU", "GB", "AUDGBP=X"),
    # NZD cross
    ("NZDJPY", "NZ", "JP", "NZDJPY=X"),
    ("NZDCAD", "NZ", "CA", "NZDCAD=X"),
    ("NZDCHF", "NZ", "CH", "NZDCHF=X"),
    # CAD cross
    ("CADJPY", "CA", "JP", "CADJPY=X"),
    ("CADCHF", "CA", "CH", "CADCHF=X"),
    # CHF cross
    ("JPYCHF", "JP", "CH", "JPYCHF=X"),
]

# ──────────────────────────────────────────
#  AMBIL DATA YIELD VIA YFINANCE
# ──────────────────────────────────────────
def get_all_yields() -> dict:
    log.info("Mengambil data yield via yfinance...")
    yields = {}

    symbol_map = {
        "US": "2YY=F",
        "EU": "DE2YT=RR",
        "GB": "GB2YT=RR",
        "JP": "JP2YT=RR",
        "AU": "AU2YT=RR",
        "NZ": "NZ2YT=RR",
        "CA": "CA2YT=RR",
        "CH": "CH2YT=RR",
        "CN": "CN2YT=RR",
    }

    for country, symbol in symbol_map.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if not hist.empty:
                val = float(hist["Close"].dropna().iloc[-1])
                yields[country] = val
                log.info(f"  {country} ({symbol}): {val:.4f}%")
            else:
                log.warning(f"  {country}: data kosong")
                yields[country] = None
        except Exception as e:
            log.warning(f"  {country}: ERROR - {e}")
            yields[country] = None
        time.sleep(0.5)

    return yields


# ──────────────────────────────────────────
#  AMBIL HARGA FX VIA YFINANCE (batch)
# ──────────────────────────────────────────
def get_all_fx_prices() -> dict:
    log.info("Mengambil harga FX via yfinance (batch)...")
    symbols = [sym for _, _, _, sym in FX_PAIRS]
    prices  = {}

    try:
        # Download semua sekaligus — lebih cepat
        data = yf.download(
            tickers=symbols,
            period="1d",
            interval="1h",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        for sym in symbols:
            try:
                if len(symbols) == 1:
                    close = data["Close"].dropna()
                else:
                    close = data[sym]["Close"].dropna()

                if not close.empty:
                    prices[sym] = float(close.iloc[-1])
                    log.info(f"  {sym}: {prices[sym]}")
                else:
                    prices[sym] = None
            except Exception as e:
                log.warning(f"  {sym}: ERROR parse - {e}")
                prices[sym] = None

    except Exception as e:
        log.error(f"Batch download error: {e}")
        # Fallback: satu per satu
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                hist = t.history(period="2d", interval="1h")
                if not hist.empty:
                    prices[sym] = float(hist["Close"].dropna().iloc[-1])
                else:
                    prices[sym] = None
            except Exception as e2:
                log.warning(f"  {sym} fallback error: {e2}")
                prices[sym] = None
            time.sleep(0.3)

    return prices


# ──────────────────────────────────────────
#  KALKULASI VALUASI
# ──────────────────────────────────────────
def calculate(yields: dict, fx_prices: dict) -> list:
    results = []
    for pair, base, quote, symbol in FX_PAIRS:
        yb = yields.get(base)
        yq = yields.get(quote)
        fx = fx_prices.get(symbol)

        if yb is None or yq is None or fx is None:
            log.warning(f"Skip {pair}: data tidak lengkap")
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
def format_msg(results: list) -> str:
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
def send_message(text: str, chat_id: str = CHAT_ID, thread_id: int = THREAD_ID):
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

def get_updates(offset: int = 0) -> list:
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
def run_yield(chat_id: str = CHAT_ID, thread_id: int = THREAD_ID):
    send_message("⏳ Mengambil data yield & FX...\nProses ~1-2 menit, harap tunggu.", chat_id, thread_id)
    try:
        yields    = get_all_yields()
        fx_prices = get_all_fx_prices()
        results   = calculate(yields, fx_prices)

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

            # Hanya respon di topic Valuasi
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
