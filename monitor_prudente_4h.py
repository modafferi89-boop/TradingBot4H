import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
import logging
import requests
import ccxt
from datetime import datetime


# --- CONFIGURAZIONE TELEGRAM ---
def invia_telegram(messaggio):
    token = "8686714259:AAG7h8PCRRIno2OW7liyvwoY7XTKGUPIkBg"
    chat_id = "256279412"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": messaggio}
    try:
        requests.post(url, data=payload)
    except:
        pass


# --- CONFIGURAZIONE BINANCE TESTNET (PAPER TRADING) ---
API_KEY = 'AMd4SobjuwHNokO6BAkRmFfXYoMRz8NhSpNRy8kzEiyLVTf1fv0TOtK5uyeeEPLo'
SECRET_KEY = 'kgxSeXBsPvU7DCnRwbd9OyqpJQO0C9axAmLxgwalRWMfUMXF2PeICZxJDbpjx7wz'

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)  # Attiva la modalità Paper Trading (Testnet)

# --- CONFIGURAZIONE LOG ---
logging.basicConfig(
    filename='trading_monitor_4h.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

lista_asset = ['BTC-USD', 'GC=F', '^GSPC']


def calcola_esposizione_atr(df):
    atr = ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1]
    prezzo_attuale = df['Close'].iloc[-1]
    if pd.notna(atr) and prezzo_attuale > 0:
        volatilita_perc = atr / prezzo_attuale
        fattore_rischio = 0.05 / volatilita_perc
        return min(1.0, float(fattore_rischio))
    return 1.0


def controlla_mercato(ticker):
    try:
        # Nota: CCXT usa simboli diversi, qui gestiamo il mapping per BTC
        simbolo_ccxt = 'BTC/USDT' if ticker == 'BTC-USD' else None

        df = yf.download(ticker, period="2mo", interval="4h", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df['sma_fast'] = ta.sma(df['Close'], length=20)
        df['sma_slow'] = ta.sma(df['Close'], length=50)
        df['sma200'] = ta.sma(df['Close'], length=200)

        ultimo = df.iloc[-1]
        penultimo = df.iloc[-2]

        if pd.isna(ultimo['sma200']): return "DATI_INSUFFICIENTI"

        # LOGICA BUY
        if ultimo['Close'] > ultimo['sma200'] and penultimo['sma_fast'] <= penultimo['sma_slow'] and ultimo[
            'sma_fast'] > ultimo['sma_slow']:
            esposizione = calcola_esposizione_atr(df)

            # ESECUZIONE ORDINE (Solo per BTC su Testnet)
            if simbolo_ccxt:
                try:
                    balance = exchange.fetch_balance()
                    usdt_disponibile = balance['total']['USDT']
                    quantita_da_comprare = (usdt_disponibile * esposizione) / ultimo['Close']
                    exchange.create_market_buy_order(simbolo_ccxt, quantita_da_comprare)
                except Exception as e:
                    logging.error(f"Errore ordine Binance: {e}")

            return f"BUY (Esposizione: {esposizione:.1%})"

        # LOGICA SELL
        if penultimo['sma_fast'] >= penultimo['sma_slow'] and ultimo['sma_fast'] < ultimo['sma_slow']:
            if simbolo_ccxt:
                try:
                    balance = exchange.fetch_balance()
                    btc_disponibile = balance['total']['BTC']
                    exchange.create_market_sell_order(simbolo_ccxt, btc_disponibile)
                except Exception as e:
                    logging.error(f"Errore vendita Binance: {e}")

            return "SELL (Uscita posizione)"

        return "HOLD"
    except Exception as e:
        logging.error(f"Errore {ticker}: {str(e)}")
        return "ERRORE_TECNICO"


def main():
    print("=== MONITOR TRADING (LIVE PAPER TRADING) AVVIATO ===")
    while True:
        ora_attuale = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for asset in lista_asset:
            esito = controlla_mercato(asset)
            if "BUY" in esito or "SELL" in esito:
                msg = f"🚨 ALERT [{ora_attuale}] {asset}: {esito}"
                print(msg)
                invia_telegram(msg)
        time.sleep(14400)


if __name__ == "__main__":
    main()