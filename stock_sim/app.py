import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd, get_shares, get_stocks, get_portfolio
import re

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    portfolio = sorted(get_portfolio(db, session["user_id"]), key=lambda d: d['symbol'])
    cash = float(db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]['cash'])
    total = cash
    cash="{:.2f}".format(cash)

    if not portfolio:
        return render_template("index.html", message="Nothing to see here!", cash=cash, total=total)

    for stock in portfolio:
        total += stock['price'] * stock['shares']

    return render_template("index.html", portfolio=portfolio, cash=cash, total="{:.2f}".format(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        query = request.form.get("symbol")
        quote = lookup(query)
        try:
            shares = int(request.form.get("shares"))
        except:
            return render_template("buy.html", message="Invalid shares.")

        if not quote:
            return render_template("buy.html", message="Invalid symbol.")

        elif not shares or shares <= 0:
            return render_template("buy.html", message="Invalid shares.")

        else:
            symbol = quote['symbol']
            price = quote['price']
            total = price * shares
            timestamp = str(datetime.now())[:-7]

            balance = float(db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]['cash'])

            if balance < total:
                return render_template("buy.html", message="Insufficient funds.")

            db.execute("UPDATE users SET cash=cash-? WHERE id=?",total,session["user_id"])
            db.execute("INSERT INTO transactions (user_id,symbol,shares,price,time) VALUES (?,?,?,?,?)", session["user_id"],symbol,shares,price,timestamp)

            # message = "current balance: " + str(db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]['cash'])
            # return render_template("buy.html", message=message)
            return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    buffer = db.execute("SELECT * FROM transactions WHERE user_id=?", session["user_id"])
    len_buffer = len(buffer)
    history = []

    for i in range(len_buffer):
        history.append(buffer[len_buffer - i - 1])

    if history:
        return render_template("history.html", history=history)
    else:
        return render_template("history.html", message="Nothing to see here!")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":

        query = request.form.get("symbol")
        quote = lookup(query)

        if quote:
            name = quote['name']
            symbol = quote['symbol']
            price = str(quote['price'])
            message = "A share of " + name + " (" + symbol + ") costs $" + price + "."
            return render_template("quote.html", message=message)
        else:
            return render_template("quote.html", message="Stock does not exist.")
        
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must provide password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        elif db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username")):
            return apology("username already exists", 400)

        hash = generate_password_hash(request.form.get("password"))

        rows = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",request.form.get("username"), hash)

        session["user_id"] = int(db.execute("SELECT id FROM users where username=?", request.form.get("username"))[0]['id'])

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    portfolio = get_portfolio(db, session["user_id"])

    if request.method == "POST":

        query = re.sub(r"[^A-Za-z]+", '', request.form.get("symbol"))
        shares = request.form.get("shares")

        print("shares:" + shares)
        print("query:" + query)

        try:
            shares = int(shares)
        except:
            return render_template("sell.html", message="Invalid shares.", portfolio=portfolio)

        if shares <=0 or not query:
            return render_template("sell.html", message="Invalid request.", portfolio=portfolio)

        if shares > get_shares(db,query,session["user_id"]):
            return render_template("sell.html", message="Not enough shares!", portfolio=portfolio)


        price = lookup(query)['price']
        timestamp = str(datetime.now())[:-7]

        db.execute("INSERT INTO transactions (user_id,symbol,shares,price,time) VALUES (?,?,?,?,?)",session["user_id"],query,shares* -1,price,timestamp)

        total = price * shares

        db.execute("UPDATE users SET cash=cash+? WHERE id=?",total,session["user_id"])

        return redirect("/")

    else:
        return render_template("sell.html", portfolio=portfolio)


@app.route("/refill", methods=["GET", "POST"])
@login_required
def refill():

    if request.method == "POST":

        try:
            amount = float(request.form.get("amount"))
        except:
            return redirect("/")

        if (amount * -1) <=  abs(float(db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]['cash'])):
            db.execute("UPDATE users SET cash=cash+? WHERE id=?",amount,session["user_id"])
        else:
            pass

        return redirect("/")


    else:
        return render_template("refill.html")
