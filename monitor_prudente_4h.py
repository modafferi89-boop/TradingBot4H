import yfinance as yf
import pandas as pd
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

# --- CONFIGURAZIONE BINANCE ---
API_KEY = 'AMd4SobjuwHNokO6BAkRmFfXYoMRz8NhSpNRy8kzEiyLVTf1fv0TOtK5uyeeEPLo'
SECRET_KEY = 'kgxSeXBsPvU7DCnRwbd9OyqpJQO0C9axAmLxgwalRWMfUMXF2PeICZxJDbpjx7wz'

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)

# --- CONFIGURAZIONE LOG ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

lista_asset = ['BTC-USD', 'GC=F', '^GSPC']

def calcola_esposizione_atr(df):
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[-1]
    
    prezzo_attuale = df['Close'].iloc[-1]
    if pd.notna(atr) and prezzo_attuale > 0:
        volatilita_perc = atr / prezzo_attuale
        fattore_rischio = 0.05 / volatilita_perc
        return min(1.0, float(fattore_rischio))
    return 1.0

def controlla_mercato(ticker):
    try:
        simbolo_ccxt = 'BTC/USDT' if ticker == 'BTC-USD' else None
        df = yf.download(ticker, period="2mo", interval="4h", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df['sma_fast'] = df['Close'].rolling(window=20).mean()
        df['sma_slow'] = df['Close'].rolling(window=50).mean()
        df['sma200'] = df['Close'].rolling(window=200).mean()

        ultimo = df.iloc[-1]
        penultimo = df.iloc[-2]

        if pd.isna(ultimo['sma200']): return "DATI_INSUFFICIENTI"

        if ultimo['Close'] > ultimo['sma200'] and penultimo['sma_fast'] <= penultimo['sma_slow'] and ultimo['sma_fast'] > ultimo['sma_slow']:
            esposizione = calcola_esposizione_atr(df)
            if simbolo_ccxt:
                try:
                    balance = exchange.fetch_balance()
                    usdt_disponibile = balance['total']['USDT']
                    quantita_da_comprare = (usdt_disponibile * esposizione) / ultimo['Close']
                    exchange.create_market_buy_order(simbolo_ccxt, quantita_da_comprare)
                except Exception as e:
                    logging.error(f"Errore ordine Binance: {e}")
            return f"BUY (Esposizione: {esposizione:.1%})"

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
    for asset in lista_asset:
        esito = controlla_mercato(asset)
        if "BUY" in esito or "SELL" in esito:
            invia_telegram(f"🚨 ALERT: {asset}: {esito}")

if __name__ == "__main__":
    main()
