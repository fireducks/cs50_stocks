import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def get_shares(db, symbol, user_id):

    shares_list = db.execute("SELECT shares FROM transactions WHERE user_id=? and symbol=?", user_id,symbol)
    total = 0

    for transaction in shares_list:
        total += int(transaction['shares'])

    return total


def get_stocks(db, user_id):

    stocks = set()

    buffer = db.execute("SELECT symbol FROM transactions WHERE user_id=?", user_id)
    for row in buffer:
        stocks.add(row['symbol'])

    return stocks


def get_portfolio(db, user_id):

    stocks = get_stocks(db, user_id)
    portfolio = []

    for stock in stocks:
        buffer = {}

        buffer['shares'] = get_shares(db, stock, user_id)

        if buffer['shares'] > 0:
            buffer['symbol'] = stock
            buffer['name'] = lookup(stock)['name']
            buffer['price'] = lookup(stock)['price']
            buffer['total'] = "{:.2f}".format(buffer['shares'] * buffer['price'])
            portfolio.append(buffer)
        else:
            pass

    return portfolio
