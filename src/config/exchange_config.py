import asyncio
import ccxt
import ccxt.pro

from .logger_config import log


async def get_exchange_authenticated(API_KEY, SECRET_KEY):
    """
    Create an authenticated ccxt.pro.gate exchange object and test authentication by fetching the balance.
    Returns None if authentication fails.
    """
    exchange_authenticated = ccxt.pro.binance(
        {
            "apiKey": API_KEY,
            "secret": SECRET_KEY,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",  # Use 'spot' for spot trading
            },
        }
    )
    exchange_authenticated.set_sandbox_mode(True)

    try:
        balance = await exchange_authenticated.fetch_balance()
        log.info("[Init] Successfully connected to exchange (authenticated).")
        usdt_balance = balance.get("USDT", {}).get("free", 0.0)
        log.info(f"[Init] USDT Free Balance: {usdt_balance:.2f}")
        return exchange_authenticated

    except ccxt.NetworkError as e:
        log.error(f"[Data Stream Error] Network error: {e}. Retrying in 5 seconds...")
        await asyncio.sleep(5)
    except ccxt.ExchangeError as e:
        log.error(f"[Data Stream Error] Exchange error: {e}. Retrying in 5 seconds...")
        await asyncio.sleep(5)
    except Exception as e:
        log.error(
            f"[Init Error] Failed to connect to exchange (authenticated) or fetch balance. Check API keys and permissions: {e}"
        )
        await exchange_authenticated.close()
        return None


def get_exchange_public():
    """
    Return a ccxt.gate exchange object for public (unauthenticated) use.
    """
    exchange_public = ccxt.binance(
        {
            "enableRateLimit": True,
        }
    )
    return exchange_public
