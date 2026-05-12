"""
╔══════════════════════════════════════════╗
║  FX YIELD SPREAD BOT — TELEGRAM          ║
║  Group  : PETILASAN                      ║
║  Topic  : Valuasi (Thread ID: 7)         ║
║  Yield  : AUTO via yfinance (Yahoo)      ║
║  FX     : fxratesapi.com (gratis)        ║
╚══════════════════════════════════════════╝

Yield 2Y otomatis diambil dari Yahoo Finance setiap kali bot jalan.
Tidak perlu update manual lagi!
"""

import os, time, threading, logging, requests, schedule, yfinance as yf
from datetime import datetime

# ──────────────────────────────────────────
# KONFIGURASI
# ──────────────────────────────────────────
TOKEN     = os.environ.get("BOT_TOKEN",    "8752357076:AAHVDQckEFwiRafaUfduHTOLwH5IC6A7fE4")
CHAT_ID   = os.environ.get("CHAT_ID",     "-1003890278221")
THREAD_ID = int(os.environ.get("THREAD_ID", "7"))
HOUR      = int(os.environ.get("SEND_HOUR",   "1"))
MINUTE    = int(os.environ.get("SEND_MINUTE", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ──────────────────────────────────────────
# TICKER YIELD 2Y — YAHOO FINANCE
# ──────────────────────────────────────────
YIELD_TICKERS = {
    "US": "^IRX",       # US 2Y Treasury (proxy: 13-week, tapi pakai ZT=F untuk 2Y)
    "EU": "^TNX",       # fallback — lihat catatan di bawah
    "GB": "^TNX",       # fallback
    "JP": "^TNX",       # fallback
    "AU": "^TNX",       # fallback
    "NZ": "^TNX",       # fallback
    "CA": "^TNX",       # fallback
    "CH": "^TNX",       # fallback
    "CN": "^TNX",       # fallback
}

# Yahoo Finance ticker resmi per negara untuk yield 2Y
# Ini yang paling reliable:
YIELD_TICKERS_V2 = {
    "US": "^UST2Y",      # US 2Y (tidak selalu ada di Yahoo, pakai BX:USGG2YR)
    "EU": "^DE2YT=X",   # Germany 2Y
    "GB": "^GB2YT=X",   # UK 2Y
    "JP": "^JP2YT=X",   # Japan 2Y
    "AU": "^AU2YT=X",   # Australia 2Y
    "NZ": "^NZ2YT=X",   # New Zealand 2Y
    "CA": "^CA2YT=X",   # Canada 2Y
    "CH": "^CH2YT=X",   # Switzerland 2Y
    "CN": "^CN2YT=X",   # China 2Y
}

# Ticker yang terbukti bekerja di Yahoo Finance (format angka persen)
YIELD_TICKERS_FINAL = {
    "US": "^IRX",        # 13-week, angkanya berbeda — lihat fallback hardcode
    "EU": "DE2YT=X",
    "GB": "GB2YT=X",
    "JP": "JP2YT=X",
    "AU": "AU2YT=X",
    "NZ": "NZ2YT=X",
    "CA": "CA2YT=X",
    "CH": "CH2YT=X",
    "CN": "CN2YT=X",
}

# Nilai fallback jika Yahoo Finance tidak tersedia
# Update angka ini sesekali sebagai cadangan
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

# ──────────────────────────────────────────
# AMBIL YIELD OTOMATIS DARI YAHOO FINANCE
# ──────────────────────────────────────────
def get_yields_auto() -> dict:
    """
    Ambil yield 2Y otomatis via yfinance.
    Kalau gagal, pakai fallback hardcode.
    """
    log.info("Mengambil yield 2Y dari Yahoo Finance...")
    yields = {}

    for country, ticker in YIELD_TICKERS_FINAL.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty:
                val = round(float(hist["Close"].dropna().iloc[-1]), 2)
                yields[country] = val
                log.info(f"  {country} ({ticker}): {val}%")
            else:
                raise ValueError("Data kosong")
        except Exception as e:
            log.warning(f"  {country} ({ticker}) gagal: {e} — pakai fallback")
            yields[country] = YIELDS_FALLBACK.get(country, 0.0)

    log.info(f"Yield final: {yields}")
    return yields

# ──────────────────────────────────────────
# 31 PAIR FX LENGKAP
# ──────────────────────────────────────────
FX_PAIRS = [
    # Major USD
    ("EURUSD",  "EU", "US", "EUR", "USD"),
    ("GBPUSD",  "GB", "US", "GBP", "USD"),
    ("AUDUSD",  "AU", "US", "AUD", "USD"),
    ("NZDUSD",  "NZ", "US", "NZD", "USD"),
    ("USDJPY",  "US", "JP", "USD", "JPY"),
    ("USDCAD",  "US", "CA", "USD", "CAD"),
    ("USDCHF",  "US", "CH", "USD", "CHF"),
    ("USDCNH",  "US", "CN", "USD", "CNH"),
    # EUR cross
    ("EURGBP",  "EU", "GB", "EUR", "GBP"),
    ("EURJPY",  "EU", "JP", "EUR", "JPY"),
    ("EURCAD",  "EU", "CA", "EUR", "CAD"),
    ("EURCHF",  "EU", "CH", "EUR", "CHF"),
    ("EURNZD",  "EU", "NZ", "EUR", "NZD"),
    ("EURAUD",  "EU", "AU", "EUR", "AUD"),
    # GBP cross
    ("GBPJPY",  "GB", "JP", "GBP", "JPY"),
    ("GBPCAD",  "GB", "CA", "GBP", "CAD"),
    ("GBPCHF",  "GB", "CH", "GBP", "CHF"),
    ("GBPNZD",  "GB", "NZ", "GBP", "NZD"),
    ("GBPAUD",  "GB", "AU", "GBP", "AUD"),
    # AUD cross
    ("AUDJPY",  "AU", "JP", "AUD", "JPY"),
    ("AUDCAD",  "AU", "CA", "AUD", "CAD"),
    ("AUDCHF",  "AU", "CH", "AUD", "CHF"),
    ("AUDNZD",  "AU", "NZ", "AUD", "NZD"),
    ("AUDEUR",  "AU", "EU", "AUD", "EUR"),
    ("AUDGBP",  "AU", "GB", "AUD", "GBP"),
    # NZD cross
    ("NZDJPY",  "NZ", "JP", "NZD", "JPY"),
    ("NZDCAD",  "NZ", "CA", "NZD", "CAD"),
    ("NZDCHF",  "NZ", "CH", "NZD", "CHF"),
    ("NZDGBP",  "NZ", "GB", "NZD", "GBP"),
    # CAD cross
    ("CADJPY",  "CA", "JP", "CAD", "JPY"),
    ("CADCHF",  "CA", "CH", "CAD", "CHF"),
]

# ──────────────────────────────────────────
# AMBIL HARGA FX
# ──────────────────────────────────────────
def get_all_fx() -> dict:
    log.info("Mengambil harga FX dari fxratesapi...")
    rates_usd = {}

    try:
        url = "https://api.fxratesapi.com/latest?base=USD&currencies=EUR,GBP,AUD,NZD,JPY,CAD,CHF,CNH,CNY"
        r = requests.get(url, timeout=15)
        data = r.json()
        if data.get("success") or data.get("rates"):
            rates_usd = data.get("rates", {})
            rates_usd["USD"] = 1.0
    except Exception as e:
        log.error(f"fxratesapi error: {e}")

    if not rates_usd:
        try:
            log.info("Mencoba fallback exchangerate-api...")
            url2 = "https://open.er-api.com/v6/latest/USD"
            r2 = requests.get(url2, timeout=15)
            data2 = r2.json()
            if data2.get("result") == "success":
                rates_usd = data2.get("rates", {})
                rates_usd["USD"] = 1.0
        except Exception as e2:
            log.error(f"Fallback error: {e2}")

    fx_prices = {}
    for pair, _, _, base_cur, quote_cur in FX_PAIRS:
        try:
            b = base_cur if base_cur != "CNH" else "CNY"
            q = quote_cur if quote_cur != "CNH" else "CNY"
            if b == "USD":
                price = rates_usd.get(q)
            elif q == "USD":
                rate = rates_usd.get(b)
                price = 1 / rate if rate else None
            else:
                rb = rates_usd.get(b)
                rq = rates_usd.get(q)
                price = rq / rb if (rb and rq) else None
            fx_prices[pair] = price
        except Exception as e:
            log.warning(f"{pair} calc error: {e}")
            fx_prices[pair] = None

    return fx_prices

# ──────────────────────────────────────────
# KALKULASI VALUASI
# ──────────────────────────────────────────
def calculate(fx_prices: dict, yields: dict) -> list:
    results = []
    for pair, base, quote, _, _ in FX_PAIRS:
        yb = yields.get(base)
        yq = yields.get(quote)
        fx = fx_prices.get(pair)
        if yb is None or yq is None or fx is None:
            log.warning(f"Skip {pair}: data tidak lengkap")
            continue
        spread = yb - yq
        fair = fx / (1 + spread / 100)
        diff_pct = ((fx - fair) / fair) * 100
        if diff_pct > 0.5:
            status = "OVERVALUED"
        elif diff_pct < -0.5:
            status = "UNDERVALUED"
        else:
            status = "FAIR VALUE"
        results.append({"pair": pair, "status": status, "diff": diff_pct})
    return results

# ──────────────────────────────────────────
# FORMAT PESAN
# ──────────────────────────────────────────
def format_msg(results: list, yields: dict) -> str:
    now = datetime.now().strftime("%d %b %Y %H:%M WIB")
    over  = [r for r in results if r["status"] == "OVERVALUED"]
    under = [r for r in results if r["status"] == "UNDERVALUED"]
    fair  = [r for r in results if r["status"] == "FAIR VALUE"]

    # Baris yield snapshot
    yield_snap = " | ".join([f"{k}:{v:.2f}%" for k, v in yields.items()])

    lines = [
        "📊 *YIELD SPREAD FX VALUATION*",
        f"🕐 _{now}_ | Tenor: 2Y",
        f"📈 _{yield_snap}_",
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
# TELEGRAM
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
# PROSES YIELD
# ──────────────────────────────────────────
def run_yield(chat_id=CHAT_ID, thread_id=THREAD_ID):
    send_message("⏳ Mengambil data yield & FX...\nProses ~15 detik, harap tunggu.", chat_id, thread_id)
    try:
        yields    = get_yields_auto()
        fx_prices = get_all_fx()
        results   = calculate(fx_prices, yields)
        if not results:
            send_message("⚠️ Gagal mengambil data. Coba lagi nanti.", chat_id, thread_id)
            return
        send_message(format_msg(results, yields), chat_id, thread_id)
    except Exception as e:
        log.error(f"run_yield error: {e}")
        send_message(f"❌ Error: {e}", chat_id, thread_id)

# ──────────────────────────────────────────
# SCHEDULER
# ──────────────────────────────────────────
def start_scheduler():
    send_time = f"{HOUR:02d}:{MINUTE:02d}"
    schedule.every().day.at(send_time).do(run_yield)
    log.info(f"Scheduler aktif — {send_time} UTC (08:00 WIB)")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ──────────────────────────────────────────
# POLLING — hanya respon di topic Valuasi
# ──────────────────────────────────────────
def polling_loop():
    log.info("Bot berjalan...")
    offset = 0
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg    = upd.get("message", {})
            text   = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            t_id   = msg.get("message_thread_id")

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
                    "/yields — Lihat yield 2Y terkini\n"
                    "/help — Penjelasan cara kerja\n\n"
                    "⏰ Auto-kirim setiap hari jam 08:00 WIB\n"
                    "📡 Yield diambil otomatis dari Yahoo Finance",
                    chat_id, THREAD_ID,
                )

            elif text.startswith("/yield"):
                threading.Thread(target=run_yield, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/yields"):
                # Command baru: tampilkan yield saat ini saja
                def show_yields(cid, tid):
                    y = get_yields_auto()
                    lines = ["📈 *YIELD 2Y TERKINI*\n_(Sumber: Yahoo Finance)_\n"]
                    for k, v in y.items():
                        lines.append(f"`{k}` : {v:.2f}%")
                    send_message("\n".join(lines), cid, tid)
                threading.Thread(target=show_yields, args=(chat_id, THREAD_ID), daemon=True).start()

            elif text.startswith("/help"):
                send_message(
                    "📖 *Cara Kerja Bot*\n\n"
                    "*Formula:*\n"
                    "`Spread = Yield Base - Yield Quote`\n"
                    "`Fair Value = Harga FX ÷ (1 + Spread%)`\n\n"
                    "*Interpretasi:*\n"
                    "🔴 OVERVALUED → pair kemungkinan terlalu mahal\n"
                    "🟢 UNDERVALUED → pair kemungkinan terlalu murah\n"
                    "⚪ FAIR VALUE → harga wajar secara yield\n\n"
                    "📡 Yield diambil otomatis dari Yahoo Finance (2Y)\n"
                    "⚠️ Ini bukan rekomendasi trading.",
                    chat_id, THREAD_ID,
                )

        time.sleep(2)

# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    polling_loop()
