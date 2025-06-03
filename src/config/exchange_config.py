import asyncio
import ccxt
import ccxt.pro


async def get_exchange_authenticated(API_KEY, SECRET_KEY, log):
    """
    Create an authenticated ccxt.pro.gate exchange object and test authentication by fetching the balance.
    Returns None if authentication fails.
    """
    exchange_authenticated = ccxt.pro.gate(
        {
            "apiKey": API_KEY,
            "secret": SECRET_KEY,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
            },
        }
    )

    try:
        balance = await exchange_authenticated.fetch_balance()
        log.info("[Init] Successfully connected to exchange (authenticated).")
        # "balance" format may vary by exchange, you can comment the section below or adjust accordingly
        cross_info = balance.get("info", [{}])[0]
        cross_available = float(cross_info.get("cross_available", 0))
        cross_initial_margin = float(cross_info.get("cross_initial_margin", 0))
        equity = cross_available + cross_initial_margin
        log.info(f"[Init] Equity: {equity:.2f}")
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
    exchange_public = ccxt.gate(
        {
            "enableRateLimit": True,
        }
    )
    return exchange_public
