from datetime import datetime
from pip._vendor import requests

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, check_cash


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# define check share price function
def check_price(symbol):

    # symbol input validation
    if (len(symbol) < 1):
        return apology("no symbol searched", 403)

    for a in symbol:
        if (not a.isalpha()):
            return apology("invalid symbol", 403)

    # check symbol share price
    try:
        stock_currentv = lookup(symbol)
        if (stock_currentv == None):
            return ValueError
        price = float(stock_currentv["price"])
    except (ValueError, KeyError, IndexError, TypeError):
        return apology("invalid symbol", 403)
    
    return price


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

    if request.method == "POST":

        return apology("invalid request", 400)

    else:
        
        # get info from db for the current user to display the user's account overvue
        overview = db.execute("SELECT * FROM balance JOIN stocks ON stocks.id = balance.stock_id WHERE balance.user_id = ?;", 
                                session.get("user_id"))
        
        cash_balance = check_cash(session.get("user_id"))
        
        if (len(overview) < 1):

            # return message if user does not yet have any share
            return render_template("/overview.html", 
                                   message = "You don't own any stocks at this moment.", 
                                   cash=cash_balance, 
                                   tot_balance=cash_balance)

        else:

            stock_balance = 0

            # populate overview info to display in overview page feching current share value remotely
            for i in range(len(overview)):

                symb = overview[i]['symbol']
                stock_currentv = check_price(symb)
                
                overview[i]["price"] = stock_currentv
                overview[i]["stock_total"] = stock_currentv * overview[i]['stock_quantity']
                stock_balance += overview[i]["stock_total"]
                overview[i]["price"] = usd(overview[i]["price"])
                overview[i]["stock_total"] = usd(overview[i]["stock_total"])

            return render_template("/overview.html", 
                                   overview=overview, 
                                   cash=cash_balance, 
                                   tot_balance = (cash_balance + stock_balance))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # update users cash amount to display
    cash_balance = check_cash(session.get("user_id"))

    if request.method == "GET":

        # return to quote page if method is GET
        return redirect("/quote")

    if request.method == "POST":

        # declare info from the user input
        action = request.form.get("action")
        symbol = request.form.get("symbol").upper()

        # get quantity of shares to buy
        if (action == "quote"):

            price = check_price(symbol)

            return render_template("/buy.html", cash=cash_balance, price=price, symbol=symbol)
        
        # proceed with purchase after getting amount of shares desired
        if (action == "purchase"):

            """Buy shares of stock"""
            # retrieve the amount of stocks to purchase and set purchase value
            
            # validation of quantity input
            try: 
                quantity = int(request.form.get("quantity"))
            except (ValueError, KeyError, IndexError, TypeError):
                return apology("invalid input", 400)
            
            if quantity < 1:
                return apology("invalid quantity input", 400)
            
            # get share current value
            price = check_price(symbol)

            # calc total purchase value
            purchase_value = quantity * price # type:ignore

            # cancel purchase of the user does not have suficient funds
            if (purchase_value > cash_balance):
                return apology("insuficient funds", 403)

            # proceed with purchase in case funds are suficient
            else:

                # update users available cash 
                cash_balance = cash_balance - purchase_value

                # check if symbol exists in stocks table
                # if yes, retrieve stock id; if not, create and get stock id

                stock_id = db.execute("SELECT id FROM stocks WHERE symbol = ?;", symbol)

                if (len(stock_id) < 1):

                    db.execute("INSERT INTO stocks (symbol) VALUES (?);", symbol)
                    stock_id = db.execute("SELECT id FROM stocks WHERE symbol = ?;", symbol)

                    # return error if stock registration was not successful
                    if (len(stock_id) < 1):

                        return apology("error registering stock", 500)

                stock_id = int(stock_id[0]['id'])

                # check if user has shares of the stock being purchased
                user_stock_quantity = db.execute("SELECT stock_quantity FROM balance WHERE user_id = ? AND stock_id = ?;", 
                                                 session.get("user_id"), 
                                                 stock_id)

                # insert stock data into balance table if it's first time purchasing shares from this stock
                if (len(user_stock_quantity) < 1):

                    db.execute("INSERT INTO balance (user_id, stock_id, stock_quantity) VALUES (?, ?, ?);", 
                               session.get("user_id"), 
                               stock_id, 
                               quantity)

                # Updating shares quantity is user already has shares from this stock
                else:

                    user_stock_quantity = int(user_stock_quantity[0]['stock_quantity'])
                    update_quant = user_stock_quantity + quantity
                    db.execute("UPDATE balance SET stock_quantity = ? WHERE user_id = ? AND stock_id = ?;", 
                               update_quant, 
                               session.get("user_id"), 
                               stock_id)

                # insert purchase into users history

                db.execute("INSERT INTO history (user_id, stock_id, operation, quantity, value, time_stamp, cash_balance) VALUES (?, ?, ?, ?, ?, ?, ?);", 
                           session.get("user_id"), 
                           stock_id, "Purchase", 
                           quantity, 
                           purchase_value, 
                           datetime.now(), 
                           cash_balance)

                db.execute("UPDATE users SET cash = ? WHERE id = ?;", 
                           cash_balance, 
                           session.get("user_id"))

            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # get users history info from the history's DB
    history = db.execute("SELECT time_stamp, operation, symbol, quantity, value, cash_balance FROM history JOIN stocks ON history.stock_id = stocks.id WHERE user_id = ? ORDER BY time_stamp DESC;", 
                         session.get("user_id"))

    # return message if user does not have any history to show
    if (len(history) < 1):
        return render_template("/history.html", 
                               message = "No operations history yet to display")

    # populate table of user's history to be displayed
    else:

        for row in history:
            if (int(row['quantity']) == 0):
                row['value_per_share'] = 0
            else:
                row['value_per_share'] = float(row['value']) / int(row['quantity'])
            row['value'] = row['value']
            row['cash_balance'] = float(row['cash_balance'])

        return render_template("/history.html", history=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", 
                          request.form.get("username"))

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

    # update user's cash amount to be displayed
    cash_balance = check_cash(session.get("user_id"))

    # get info from the nasdaq100 index 
    try:
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"}
        res=requests.get("https://api.nasdaq.com/api/quote/list-type/nasdaq100",headers=headers)
        main_data=res.json()['data']['data']['rows']
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return apology("Service Unavailable", 503)

    # in the GET method, only display the nasdaq100 index info
    if request.method == "GET":
          
        return render_template("/quote.html", 
                               cash=cash_balance, 
                               market_data=main_data, 
                               quote="0")

    # in the POST method display the quote of the share requested by the user
    if request.method == "POST":

        symbol = request.form.get("symbol").upper()

        price = check_price(symbol)

        return render_template("/quote.html", 
                               cash=cash_balance, 
                               price=price, 
                               symbol=symbol, 
                               market_data=main_data, 
                               quote="1")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # if user request registration through the registration form
    if request.method == "POST":

        userName = request.form.get("username").lower()
        passd = request.form.get("password")
        passdConf = request.form.get("confirmation")

        # check if username is valid
        if (len(userName) < 6 or not userName.isalnum()):

            return apology("invalid username")

        count_numb = 0
        for i in passd:
            if i.isnumeric():
                count_numb+=1

        # check if password meets the requirements
        if (len(passd) < 6 or not passd.isalnum() or count_numb < 1 or count_numb == len(passd)):

            return apology("invalid password")

        # check if password and username are not the same
        if (userName == passd):

            return apology("username and password must be different", 403)

        # check if password and password confirmation are the same
        if (passd != passdConf):

            return apology("passwords do not match", 400)

        # check if username is already in use
        userExist = db.execute("SELECT * FROM users WHERE username = ?", 
                               userName)

        if (len(userExist) > 0):

            return apology("Username already in use", 403)


        # after all conditions are met, generate pass hash and input user info in DB

        pass_hash = generate_password_hash(passd)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?);", 
                   userName, 
                   pass_hash)

        return render_template("/login.html", 
                               user_alert = "Registration Successful! Thank you for registering. You may login.")

    # display registration form in case the user gets to the registration page via GET method
    else:

        return render_template("/register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # get the user's shares owned info and chash amount from DB
    stocks = db.execute("SELECT symbol FROM balance JOIN stocks ON balance.stock_id = stocks.id WHERE user_id = ?;", 
                        session.get("user_id"))
    
    cash_balance = check_cash(session.get("user_id"))

    if request.method == "GET":

        # redirect to main page if method is GET
        return redirect("/")

    if request.method == "POST":

        # get info of type of action
        action = request.form.get("action")

        if (action == "quote"):

            # if action is to quote sell, get info from the DB of the amount of shares the user has from the symbol requested
            symbol = request.form.get("symbol").upper()

            # validation of user's input
            if (len(symbol) < 1):
                return apology("no symbol searched", 403)

            for a in symbol:
                if (not a.isalpha()):
                    return apology("invalid symbol", 403)

            balance = db.execute("SELECT stock_quantity, stock_id FROM balance JOIN stocks ON balance.stock_id = stocks.id WHERE user_id = ? AND symbol = ?;", 
                                 session.get("user_id"), 
                                 symbol)

            # message in case user does not have any share from symbol requested
            if (len(balance) < 1):
                return apology("you don't have any shares from this symbol", 403)

            # in case of a valid symbol input check the amount of shares owned and the share symbol ID
            quantity = int(balance[0]['stock_quantity'])
            stock_id = balance[0]['stock_id']

            # check current share value
            price = check_price(symbol)        

            # get the total share value
            value = quantity * price #type: ignore

            return render_template("/sell.html", 
                                   price=price, 
                                   quantity=quantity, 
                                   value=value, 
                                   symbol=symbol,  
                                   symbols=stocks)

        if (action == "sell"):

            # if action is to proceed with sale

            # validate the user input of quantity of shares to sell
            try:
                sell_quantity = int(request.form.get("quantity"))
            except (ValueError, KeyError, IndexError, TypeError):
                return apology("invalid quantity input", 400)            
    
            symbol = request.form.get("symbol").upper() 

            # get the updated price info for the symbol input
            price = check_price(symbol)

            balance = db.execute("SELECT stock_quantity, stock_id FROM balance JOIN stocks ON balance.stock_id = stocks.id WHERE user_id = ? AND symbol = ?;", 
                                 session.get("user_id"), 
                                 symbol)

            # message in case user does not have any share from symbol requested 
            if (len(balance) < 1):
                return apology("you don't have any shares from this symbol", 403)

            quantity = int(balance[0]['stock_quantity'])
            stock_id = balance[0]['stock_id']


            # message in case user is trying to sell more shares than owned or if quantity input is invalid
            if (sell_quantity < 1 or sell_quantity > quantity):
                return apology("share quantity invalid", 403)

            # proceed with sale if all conditions are met
            else:
                # update user's cash amount and shares quantity owned after sale
                sell_value = sell_quantity * price #type:ignore
                cash_balance+= sell_value
                quantity-=sell_quantity
                db.execute("UPDATE users SET cash = ? WHERE id = ?;", 
                           cash_balance, 
                           session.get("user_id"))

                # update db with the new share amount
                if (quantity > 0):
                    db.execute("UPDATE balance SET stock_quantity = ? WHERE stock_id = ? AND user_id = ?;", 
                               quantity, 
                               stock_id, 
                               session.get("user_id"))
                
                # remove the share info from the balance db table in case the amount of shares is 0 (zero) after sale
                else:
                    db.execute("DELETE FROM balance WHERE stock_id = ? AND user_id = ?;", 
                               stock_id, 
                               session.get("user_id"))

                # update history DB with transaction
                db.execute("INSERT INTO history (user_id, stock_id, operation, quantity, value, time_stamp, cash_balance) VALUES (?, ?, ?, ?, ?, ?, ?);", 
                           session.get("user_id"), 
                           stock_id, 
                           "Sell", 
                           sell_quantity, 
                           sell_value, 
                           datetime.now(), 
                           cash_balance)


@app.route("/funds", methods=["GET", "POST"])
@login_required
def funds():
    """to deposit or withdraw cash"""

    # get user's updated chash amount from db
    cash_balance = check_cash(session.get("user_id"))

    # redirect to cash operation form in case of GET method 
    if request.method == "GET":

        return render_template("/funds.html", cash=cash_balance)

    # proceed with cash operation in case of POST method
    if request.method == "POST":

        # fetch the requested operation type
        t_type = request.form.get("t_type")

        # fetch the cash amount for the operation
        t_amount = request.form.get("amount")

        # proceed with operation if option is valid
        if (t_type == "Deposit" or t_type == "Withdrawal"):

            # validation of cash transaction amount
            try:
                t_amount = float(t_amount)
            except ValueError:
                return apology("Input value not valid", 403)
            
            if t_amount <= 0:
                return apology("Input value not valid", 403)
            
            # update the user's cash value if deposit or withdrawal transaction
            if (t_type == "Deposit"):

                cash_balance += t_amount


            if (t_type == "Withdrawal"):

                # return message if user tries to withdraw more cash than possessed
                if (t_amount > cash_balance):
                    return apology("Insuficient Funds", 403)

                cash_balance -= t_amount

            # update DB with updated user's cash owned and update history DB with transaction
            db.execute("UPDATE users SET cash = ? WHERE id = ?;", 
                       cash_balance, 
                       session.get("user_id"))
            
            db.execute("INSERT INTO history (user_id, stock_id, operation, quantity, value, time_stamp, cash_balance) VALUES (?, ?, ?, ?, ?, ?, ?);", 
                       session.get("user_id"), 
                       0, 
                       t_type, 
                       0, 
                       t_amount, 
                       datetime.now(), 
                       cash_balance)
            
            return redirect("/history")

    # return error if there was a bad request
    return apology("Something went wrong", 400)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """lets user's change their passwords"""

    if request.method == "GET":
        
        # render the settings template in case of GET method 
        return render_template("settings.html")

    if request.method == "POST":

        # Ensure password was submitted
        if not request.form.get("cpassword"):
            return apology("must provide password", 403)

        # Ensure new password was submitted
        elif not request.form.get("npassword"):
            return apology("must provide new password", 403)

        # Remember new password for future check and store, confirm both fields match
        npass = request.form.get("npassword")
        confpass = request.form.get("confpassword")

        if (not npass == confpass):

            return render_template("settings.html", message = "New Passwords don't match")

        # Query database for username
        userdata = db.execute("SELECT * FROM users WHERE id = ?", 
                              session.get("user_id"))

        # Ensure password is correct
        if not check_password_hash(userdata[0]["hash"], 
                                   request.form.get("cpassword")):
            
            return apology("wrong password", 403)

        count_numb = 0
        for i in npass:
            if i.isnumeric():
                count_numb+=1

        # check if password meets the requirements
        if (len(npass) < 6 or not npass.isalnum() or count_numb < 1 or count_numb == len(npass)):

            return apology("new password does not meet the requirements", 403)

        # check if password and username are not the same
        if (userdata[0]['username'] == npass):

            return apology("username and password must be different", 403)

        # check if new password is deferent from the old
        if request.form.get("cpassword") == npass:

            return apology("new password must be different", 403)

        # Create hash for new password and store it after all conditions are met

        pass_hash = generate_password_hash(npass)

        db.execute("UPDATE users SET hash = ? WHERE id = ?;", 
                   pass_hash, 
                   session.get("user_id"))


    return render_template("/settings.html", message = "Password Updated")