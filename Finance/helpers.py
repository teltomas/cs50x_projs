import csv
import datetime
import pytz
import requests
import subprocess
import urllib
import uuid
import pandas as pd

from cs50 import SQL
from flask import redirect, render_template, session
from functools import wraps

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Yahoo Finance API
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"  # type: ignore
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query API
    try:
        response = requests.get(url, cookies={"session": str(uuid.uuid4())}, headers={"User-Agent": "python-requests", "Accept": "*/*"})
        response.raise_for_status()

        # CSV header: Date,Open,High,Low,Close,Adj Close,Volume
        quotes = list(csv.DictReader(response.content.decode("utf-8").splitlines()))
        quotes.reverse()
        price = round(float(quotes[0]["Adj Close"]), 2)
    
        return {
            "name": symbol,
            "price": price,
            "symbol": symbol
        }
    
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def check_cash(id):
    """chack user's cash amount"""
    cash_balance = db.execute("SELECT cash FROM users WHERE id = ?;",  id)
    cash_balance = float(cash_balance[0]['cash'])
    return cash_balance

def get_index():

    # pretty printing of pandas dataframe
    pd.set_option('expand_frame_repr', False)
    pd.set_option("display.max_rows", None, "display.max_columns", None) # type: ignore

    # There are 5 tables on the Wikipedia page
    # we want the last table

    payload=pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100')

    data = payload[4][["Ticker", "Company"]]

    data = list(data.itertuples(index=False))

    return data
