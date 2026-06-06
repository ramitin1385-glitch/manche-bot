"""
ربات منچ تلگرام
نصب: pip install python-telegram-bot
اجرا: python manche_bot.py
"""

import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== توکن ربات =====
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # توکن خود را اینجا بگذارید

# ===== وضعیت‌های بازی =====
WAITING_PLAYERS = 0
PLAYING = 1

# ===== رنگ‌های بازیکنان =====
COLORS = {
    0: ("🔴", "قرمز"),
    1: ("🔵", "آبی"),
    2: ("🟢", "سبز"),
    3: ("🟡", "زرد"),
}

# ===== خانه‌های امن =====
SAFE_SQUARES = [1, 9, 14, 22, 27, 35, 40, 48]

# ===== خانه‌های شروع هر رنگ =====
START_SQUARES = {0: 1, 1: 14, 2: 27, 3: 40}

# ===== خانه ختم هر رنگ =====
HOME_ENTRY = {0: 51, 1: 12, 2: 25, 3: 38}

# ذخیره اطلاعات بازی‌ها
games = {}


def create_new_game(chat_id: int, player_count: int):
    """ایجاد بازی جدید"""
    return {
        "chat_id": chat_id,
        "player_count": player_count,
        "players": {},       # {user_id: {"name": ..., "color": ..., "pieces": [...]}}
        "current_turn": 0,   # ایندکس بازیکن فعلی
        "turn_order": [],    # ترتیب بازیکنان
        "state": WAITING_PLAYERS,
        "dice_rolled": False,
        "last_dice": 0,
        "winner": None,
    }


def init_pieces(color_index: int):
    """مهره‌های اولیه بازیکن (همه در خانه)"""
    return [-1, -1, -1, -1]  # -1 یعنی هنوز وارد بازی نشده


def roll_dice() -> int:
    return random.randint(1, 6)


def board_display(game: dict) -> str:
    """نمایش وضعیت بازی به صورت متن"""
    lines = ["🎲 **وضعیت بازی منچ** 🎲\n"]
    for uid, pdata in game["players"].items():
        emoji, cname = COLORS[pdata["color"]]
        pieces_str = []
        for i, pos in enumerate(pdata["pieces"]):
            if pos == -1:
                pieces_str.append("🏠")
            elif pos >= 100:
                pieces_str.append("🏆")
            else:
                pieces_str.append(f"[{pos}]")
        lines.append(f"{emoji} {pdata['name']}: {' '.join(pieces_str)}")

    turn_order = game["turn_order"]
    if turn_order and game["state"] == PLAYING:
        current_uid = turn_order[game["current_turn"] % len(turn_order)]
        if current_uid in game["players"]:
            p = game["players"][current_uid]
            emoji, cname = COLORS[p["color"]]
            lines.append(f"\n🎯 نوبت: {emoji} {p['name']}")
    return "\n".join(lines)


def get_movable_pieces(game: dict, uid: int, dice: int):
    """پیدا کردن مهره‌هایی که می‌توانند حرکت کنند"""
    pdata = game["players"][uid]
    color = pdata["color"]
    start = START_SQUARES[color]
    movable = []

    for i, pos in enumerate(pdata["pieces"]):
        if pos == -1:
            # برای ورود به بازی باید ۶ بیاید
            if dice == 6:
                movable.append(i)
        elif pos < 100:
            new_pos = pos + dice
            # بررسی اینکه از خانه ختم رد نشود
            if new_pos <= HOME_ENTRY[color] + 6:
                movable.append(i)
    return movable


def move_piece(game: dict, uid: int, piece_index: int, dice: int) -> str:
    """حرکت مهره و برگرداندن پیام"""
    pdata = game["players"][uid]
    color = pdata["color"]
    start = START_SQUARES[color]
    pos = pdata["pieces"][piece_index]
    emoji, cname = COLORS[color]
    msg = ""

    if pos == -1:
        # ورود به بازی
        pdata["pieces"][piece_index] = start
        msg = f"{emoji} مهره {piece_index+1} وارد بازی شد!"
    else:
        new_pos = (pos + dice - 1) % 52 + 1
        new_pos = pos + dice

        # بررسی رسیدن به خانه
        if new_pos >= HOME_ENTRY[color] + 6:
            pdata["pieces"][piece_index] = 100 + piece_index  # رسیده به خانه
            msg = f"{emoji} مهره {piece_index+1} به خانه رسید! 🏆"
        else:
            # بررسی خوردن مهره حریف
            eaten = False
            if new_pos not in SAFE_SQUARES:
                for other_uid, other_pdata in game["players"].items():
                    if other_uid == uid:
                        continue
                    for j, opos in enumerate(other_pdata["pieces"]):
                        if opos == new_pos:
                            other_pdata["pieces"][j] = -1
                            oe, ocname = COLORS[other_pdata["color"]]
                            msg += f"🍽 مهره {oe} خورده شد!\n"
                            eaten = True

            pdata["pieces"][piece_index] = new_pos
            msg += f"{emoji} مهره {piece_index+1} به خانه {new_pos} رفت."

    return msg


def check_winner(game: dict):
    """بررسی برنده شدن"""
    for uid, pdata in game["players"].items():
        if all(p >= 100 for p in pdata["pieces"]):
            return uid
    return None


# ===== هندلرها =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 بازی ۲ نفره", callback_data="new_2")],
        [InlineKeyboardButton("🎮 بازی ۴ نفره", callback_data="new_4")],
    ]
    await update.message.reply_text(
        "🎲 **به ربات منچ خوش آمدید!**\n\nتعداد بازیکنان را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    user = query.from_user

    # ===== شروع بازی جدید =====
    if data.startswith("new_"):
        count = int(data.split("_")[1])
        games[chat_id] = create_new_game(chat_id, count)
        game = games[chat_id]

        # اضافه کردن سازنده بازی
        color = len(game["players"])
        game["players"][user.id] = {
            "name": user.first_name,
            "color": color,
            "pieces": init_pieces(color),
        }
        game["turn_order"].append(user.id)

        keyboard = [[InlineKeyboardButton("✋ پیوستن به بازی", callback_data="join")]]
        if len(game["players"]) >= count:
            keyboard.append([InlineKeyboardButton("▶️ شروع بازی", callback_data="startgame")])

        await query.edit_message_text(
            f"🎮 بازی {count} نفره ایجاد شد!\n"
            f"بازیکنان: {', '.join(p['name'] for p in game['players'].values())}\n"
            f"({len(game['players'])}/{count} نفر)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== پیوستن =====
    elif data == "join":
        if chat_id not in games:
            await query.answer("بازی‌ای وجود ندارد!", show_alert=True)
            return
        game = games[chat_id]
        if user.id in game["players"]:
            await query.answer("قبلاً وارد شدید!", show_alert=True)
            return
        if len(game["players"]) >= game["player_count"]:
            await query.answer("بازی پر است!", show_alert=True)
            return

        color = len(game["players"])
        game["players"][user.id] = {
            "name": user.first_name,
            "color": color,
            "pieces": init_pieces(color),
        }
        game["turn_order"].append(user.id)

        keyboard = [[InlineKeyboardButton("✋ پیوستن به بازی", callback_data="join")]]
        if len(game["players"]) >= game["player_count"]:
            keyboard.append([InlineKeyboardButton("▶️ شروع بازی", callback_data="startgame")])

        await query.edit_message_text(
            f"بازیکنان: {', '.join(p['name'] for p in game['players'].values())}\n"
            f"({len(game['players'])}/{game['player_count']} نفر)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== شروع بازی =====
    elif data == "startgame":
        if chat_id not in games:
            return
        game = games[chat_id]
        if len(game["players"]) < 2:
            await query.answer("حداقل ۲ بازیکن لازم است!", show_alert=True)
            return
        game["state"] = PLAYING

        keyboard = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
        await query.edit_message_text(
            board_display(game),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # ===== تاس انداختن =====
    elif data == "roll":
        if chat_id not in games:
            return
        game = games[chat_id]
        if game["state"] != PLAYING:
            return

        current_uid = game["turn_order"][game["current_turn"] % len(game["turn_order"])]
        if user.id != current_uid:
            await query.answer("نوبت شما نیست!", show_alert=True)
            return

        dice = roll_dice()
        game["last_dice"] = dice
        game["dice_rolled"] = True

        movable = get_movable_pieces(game, user.id, dice)
        pdata = game["players"][user.id]
        emoji, cname = COLORS[pdata["color"]]

        if not movable:
            # هیچ مهره‌ای نمی‌تواند حرکت کند
            game["current_turn"] += 1
            game["dice_rolled"] = False
            keyboard = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
            next_uid = game["turn_order"][game["current_turn"] % len(game["turn_order"])]
            next_p = game["players"][next_uid]
            ne, nc = COLORS[next_p["color"]]
            await query.edit_message_text(
                f"{board_display(game)}\n\n{emoji} {pdata['name']} تاس {dice} انداخت — حرکتی ممکن نیست!\n🎯 نوبت: {ne} {next_p['name']}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            # نمایش مهره‌های قابل حرکت
            keyboard = []
            for i in movable:
                pos = pdata["pieces"][i]
                label = f"مهره {i+1} ({'خانه' if pos == -1 else f'خانه {pos}'})"
                keyboard.append([InlineKeyboardButton(label, callback_data=f"move_{i}")])

            await query.edit_message_text(
                f"{board_display(game)}\n\n{emoji} {pdata['name']} تاس **{dice}** انداخت!\nکدام مهره را حرکت دهید؟",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    # ===== حرکت مهره =====
    elif data.startswith("move_"):
        if chat_id not in games:
            return
        game = games[chat_id]
        piece_index = int(data.split("_")[1])
        current_uid = game["turn_order"][game["current_turn"] % len(game["turn_order"])]

        if user.id != current_uid:
            await query.answer("نوبت شما نیست!", show_alert=True)
            return

        dice = game["last_dice"]
        move_msg = move_piece(game, user.id, piece_index, dice)

        # بررسی برنده
        winner_uid = check_winner(game)
        if winner_uid:
            wp = game["players"][winner_uid]
            we, wc = COLORS[wp["color"]]
            await query.edit_message_text(
                f"{board_display(game)}\n\n{move_msg}\n\n🏆 {we} **{wp['name']} برنده شد!** 🏆",
                parse_mode="Markdown"
            )
            del games[chat_id]
            return

        # اگر ۶ آمد دوباره تاس بیندازد
        if dice != 6:
            game["current_turn"] += 1

        game["dice_rolled"] = False
        keyboard = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]

        await query.edit_message_text(
            f"{board_display(game)}\n\n{move_msg}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )


async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in games:
        del games[chat_id]
        await update.message.reply_text("بازی پایان یافت. 👋")
    else:
        await update.message.reply_text("بازی‌ای در جریان نیست.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end_game))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
