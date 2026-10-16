import os
import sys
import requests
import pandas as pd
import yfinance as yf

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SYMBOLS = {"XAUUSD": "GC=F", "EURUSD": "EURUSD=X"}
NOTE = "⚠️ Tajriba signali. Foyda kafolati yo'q. Faqat demo hisobda sinang."


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )
    if not r.ok:
        print("Telegram xato:", r.status_code, r.text)
        sys.exit(1)


def analyze(name, ticker):
    df = yf.download(ticker, period="60d", interval="1h",
                     progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None, f"{name}: ma'lumot olinmadi"
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    now = pd.Timestamp.now(tz="UTC")
    if df.index[-1] + pd.Timedelta(hours=1) > now:
        df = df.iloc[:-1]  # hali yopilmagan shamni olib tashlaymiz
    if len(df) < 210:
        return None, f"{name}: ma'lumot yetarli emas"

    close = df["Close"]
    fast = close.ewm(span=20, adjust=False).mean()
    slow = close.ewm(span=50, adjust=False).mean()
    trend = close.ewm(span=200, adjust=False).mean()
    pc = close.shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - pc).abs(),
                    (df["Low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    d = 5 if name == "EURUSD" else 2
    price = float(close.iloc[-1])
    a = float(atr.iloc[-1])
    side = "yuqorida" if price > trend.iloc[-1] else "pastda"
    status = f"{name}: narx {price:.{d}f}, EMA200 dan {side}"

    if now - df.index[-1] > pd.Timedelta(hours=2):
        return None, status + " (bozor yopiq)"

    buy = (fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
           and price > trend.iloc[-1])
    sell = (fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]
            and price < trend.iloc[-1])

    if buy:
        sl, tp = price - 1.5 * a, price + 3 * a
        text = (f"🟢 {name} BUY (H1)\nNarx: {price:.{d}f}\n"
                f"SL: {sl:.{d}f}\nTP: {tp:.{d}f}\n\n{NOTE}")
        return text, status
    if sell:
        sl, tp = price + 1.5 * a, price - 3 * a
        text = (f"🔴 {name} SELL (H1)\nNarx: {price:.{d}f}\n"
                f"SL: {sl:.{d}f}\nTP: {tp:.{d}f}\n\n{NOTE}")
        return text, status
    return None, status


def main():
    test = len(sys.argv) > 1 and sys.argv[1] == "test"
    lines = []
    for name, ticker in SYMBOLS.items():
        try:
            signal, status = analyze(name, ticker)
        except Exception as e:
            print(name, "xato:", e)
            lines.append(f"{name}: xato")
            continue
        lines.append(status)
        if signal:
            send(signal)
    if test:
        send("✅ Aurum ishlayapti\n" + "\n".join(lines))


main()
