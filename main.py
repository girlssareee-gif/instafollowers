import os
import sqlite3
import qrcode
import random
import string
import asyncio
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== CONFIG =====
TOKEN = os.getenv("8601591233:AAFM2JTNK6P5AZixY3PvQ3CeWX9DNVUWB-I")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
UPI_ID = os.getenv("niteshextema@fam")
BOT_USERNAME = "instapaidfollowbot"

REFERRAL_REWARD = 1

# ===== DATABASE =====
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    promo_used INTEGER DEFAULT 0,
    referred_by INTEGER,
    last_claim TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    user_id INTEGER,
    amount INTEGER,
    status TEXT
)
""")

conn.commit()

PROMO = {"NEW10": 10}

# ===== UTIL =====
def generate_order_id():
    return "ORD-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_user(user_id):
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cur.fetchone()
    if not user:
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return {"balance": 0, "promo_used": 0}
    return {"balance": user[1], "promo_used": user[2]}

def update_balance(user_id, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def generate_qr(amount, user_id):
    link = f"upi://pay?pa={UPI_ID}&pn=PROBOT&am={amount}&cu=INR&tn=Order{user_id}"
    file = f"qr_{user_id}.png"
    qrcode.make(link).save(file)
    return file

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # referral
    ref = None
    if context.args:
        try:
            ref = int(context.args[0])
        except:
            pass

    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, referred_by) VALUES (?,?)", (user_id, ref))
        conn.commit()

        if ref and ref != user_id:
            update_balance(ref, REFERRAL_REWARD)
            await context.bot.send_message(ref, f"🎉 Referral Joined! ₹{REFERRAL_REWARD} added")

    keyboard = [
        [InlineKeyboardButton("💰 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("📦 Order", callback_data="order")],
        [InlineKeyboardButton("🎁 Referral", callback_data="ref")],
        [InlineKeyboardButton("🎯 Promo", callback_data="promo")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily")],
        [InlineKeyboardButton("🛠 Support", callback_data="support")]
    ]

    await update.message.reply_text(
        """🔥 *WELCOME TO INSTA FOLLOW BOT* 🔥

🚀 Fast • Secure • Trusted

💰 Earn • Order • Grow

👇 Select option""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ===== BUTTON =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "wallet":
        user = get_user(user_id)
        await query.message.reply_text(f"💰 Balance: ₹{user['balance']}")

    elif query.data == "order":
        count = random.randint(100,300)
        await query.message.reply_text(f"🔥 {count}+ users ordering now!")

        keyboard = [
            [InlineKeyboardButton("1K - ₹20", callback_data="buy_20")],
            [InlineKeyboardButton("2K - ₹40", callback_data="buy_40")],
            [InlineKeyboardButton("5K - ₹100", callback_data="buy_100")],
            [InlineKeyboardButton("10K - ₹200", callback_data="buy_200")],
            [InlineKeyboardButton("50K - ₹500", callback_data="buy_500")]
        ]
        await query.message.reply_text("📦 Select Plan", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("buy_"):
        amt = int(query.data.split("_")[1])
        context.user_data["amount"] = amt
        context.user_data["step"] = "username"
        await query.message.reply_text("📌 Send username")

    elif query.data == "ref":
        link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await query.message.reply_text(f"🎁 Earn ₹1 per referral\n{link}")

    elif query.data == "promo":
        context.user_data["step"] = "promo"
        await query.message.reply_text("Send promo code")

    elif query.data == "support":
        context.user_data["step"] = "support"
        await query.message.reply_text("Send your issue")

    elif query.data == "daily":
        today = str(datetime.date.today())
        cur.execute("SELECT last_claim FROM users WHERE user_id=?", (user_id,))
        data = cur.fetchone()

        if data and data[0] == today:
            await query.message.reply_text("❌ Already claimed")
        else:
            update_balance(user_id, 1)
            cur.execute("UPDATE users SET last_claim=? WHERE user_id=?", (today, user_id))
            conn.commit()
            await query.message.reply_text("🎁 ₹1 Daily Bonus Added!")

# ===== MESSAGE =====
async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if context.user_data.get("step") == "username":
        amt = context.user_data["amount"]
        oid = generate_order_id()

        cur.execute("INSERT INTO orders (order_id,user_id,amount,status) VALUES (?,?,?,?)",
                    (oid,user_id,amt,"pending"))
        conn.commit()

        context.user_data["order_id"] = oid

        qr = generate_qr(amt,user_id)
        with open(qr,"rb") as f:
            await update.message.reply_photo(f,
                caption=f"""🧾 Order ID: {oid}

💰 Pay ₹{amt}

📸 Send screenshot

⏳ Wait for approval"""
            )
        os.remove(qr)

    elif context.user_data.get("step") == "promo":
        await update.message.reply_text("Promo applied (demo)")
        context.user_data["step"] = None

    elif context.user_data.get("step") == "support":
        await context.bot.send_message(ADMIN_ID,f"Support from {user_id}:\n{text}")
        await update.message.reply_text("✅ Sent to support")
        context.user_data["step"] = None

# ===== PHOTO =====
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    file = await update.message.photo[-1].get_file()
    path = f"{user.id}.jpg"
    await file.download_to_drive(path)

    keyboard = [[
        InlineKeyboardButton("Approve", callback_data=f"ok_{user.id}"),
        InlineKeyboardButton("Reject", callback_data=f"no_{user.id}")
    ]]

    with open(path,"rb") as f:
        await context.bot.send_photo(ADMIN_ID,f,caption=f"User {user.id}",reply_markup=InlineKeyboardMarkup(keyboard))

    os.remove(path)

    await update.message.reply_text("⏳ Wait for admin approval")

# ===== ADMIN =====
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, uid = query.data.split("_")
    uid = int(uid)

    if action == "ok":
        cur.execute("SELECT order_id,amount FROM orders WHERE user_id=? AND status='pending' LIMIT 1",(uid,))
        order = cur.fetchone()

        if order:
            oid, amt = order
            update_balance(uid, amt)
            cur.execute("UPDATE orders SET status='done' WHERE order_id=?", (oid,))
            conn.commit()

            await context.bot.send_message(uid,f"✅ Payment Approved\n🧾 {oid}")

            # progress animation
            await context.bot.send_message(uid,"🚀 Order Started...")
            await asyncio.sleep(2)
            await context.bot.send_message(uid,"⚡ Processing...")
            await asyncio.sleep(2)
            await context.bot.send_message(uid,"✅ Completed!")

    else:
        await context.bot.send_message(uid,"❌ Rejected")

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CallbackQueryHandler(admin, pattern="^(ok|no)_"))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    print("🔥 BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
