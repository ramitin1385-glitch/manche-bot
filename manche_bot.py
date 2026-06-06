"""
ربات منچ تلگرام - نسخه سازگار با python-telegram-bot 21.x
"""

import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8945308523:AAFueYNr5nrpTEYj6DPmgF6GvR4JIPOzYs4"

COLORS = {
    0: ("🔴", "قرمز"),
    1: ("🔵", "آبی"),
    2: ("🟢", "سبز"),
    3: ("🟡", "زرد"),
}

SAFE_SQUARES = [1, 9, 14, 22, 27, 35, 40, 48]
START_SQUARES = {0: 1, 1: 14, 2: 27, 3: 40}
HOME_ENTRY = {0: 51, 1: 12, 2: 25, 3: 38}

games = {}


def create_game(chat_id, player_count):
    return {
        "chat_id": chat_id,
        "player_count": player_count,
        "players": {},
        "current_turn": 0,
        "turn_order": [],
        "playing": False,
        "last_dice": 0,
    }


def board_display(game):
    lines = ["🎲 *وضعیت بازی منچ*\n"]
    for uid, p in game["players"].items():
        e, c = COLORS[p["color"]]
        pieces = []
        for pos in p["pieces"]:
            if pos == -1:
                pieces.append("🏠")
            elif pos >= 100:
                pieces.append("🏆")
            else:
                pieces.append(f"[{pos}]")
        lines.append(f"{e} {p['name']}: {' '.join(pieces)}")

    if game["playing"] and game["turn_order"]:
        uid = game["turn_order"][game["current_turn"] % len(game["turn_order"])]
        if uid in game["players"]:
            p = game["players"][uid]
            e, c = COLORS[p["color"]]
            lines.append(f"\n🎯 نوبت: {e} {p['name']}")
    return "\n".join(lines)


def get_movable(game, uid, dice):
    p = game["players"][uid]
    color = p["color"]
    movable = []
    for i, pos in enumerate(p["pieces"]):
        if pos == -1 and dice == 6:
            movable.append(i)
        elif pos != -1 and pos < 100:
            movable.append(i)
    return movable


def move_piece(game, uid, idx, dice):
    p = game["players"][uid]
    color = p["color"]
    pos = p["pieces"][idx]
    e, c = COLORS[color]
    msg = ""

    if pos == -1:
        p["pieces"][idx] = START_SQUARES[color]
        msg = f"{e} مهره {idx+1} وارد بازی شد!"
    else:
        new_pos = pos + dice
        if new_pos >= HOME_ENTRY[color] + 6:
            p["pieces"][idx] = 100 + idx
            msg = f"{e} مهره {idx+1} به خانه رسید! 🏆"
        else:
            if new_pos not in SAFE_SQUARES:
                for ouid, op in game["players"].items():
                    if ouid == uid:
                        continue
                    for j, opos in enumerate(op["pieces"]):
                        if opos == new_pos:
                            op["pieces"][j] = -1
                            oe, oc = COLORS[op["color"]]
                            msg += f"🍽 مهره {oe} خورده شد!\n"
            p["pieces"][idx] = new_pos
            msg += f"{e} مهره {idx+1} به خانه {new_pos} رفت."
    return msg


def check_winner(game):
    for uid, p in game["players"].items():
        if all(pos >= 100 for pos in p["pieces"]):
            return uid
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎮 بازی ۲ نفره", callback_data="new_2")],
        [InlineKeyboardButton("🎮 بازی ۴ نفره", callback_data="new_4")],
    ]
    await update.message.reply_text(
        "🎲 *به ربات منچ خوش آمدید!*\n\nتعداد بازیکنان را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    chat_id = q.message.chat_id
    user = q.from_user

    if data.startswith("new_"):
        count = int(data.split("_")[1])
        games[chat_id] = create_game(chat_id, count)
        game = games[chat_id]
        game["players"][user.id] = {
            "name": user.first_name,
            "color": 0,
            "pieces": [-1, -1, -1, -1],
        }
        game["turn_order"].append(user.id)

        kb = [[InlineKeyboardButton("✋ پیوستن", callback_data="join")]]
        if len(game["players"]) >= count:
            kb.append([InlineKeyboardButton("▶️ شروع", callback_data="startgame")])

        await q.edit_message_text(
            f"بازی {count} نفره ایجاد شد!\nبازیکنان: {', '.join(p['name'] for p in game['players'].values())}\n({len(game['players'])}/{count})",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data == "join":
        if chat_id not in games:
            await q.answer("بازی‌ای نیست!", show_alert=True)
            return
        game = games[chat_id]
        if user.id in game["players"]:
            await q.answer("قبلاً وارد شدید!", show_alert=True)
            return
        if len(game["players"]) >= game["player_count"]:
            await q.answer("بازی پر است!", show_alert=True)
            return

        color = len(game["players"])
        game["players"][user.id] = {
            "name": user.first_name,
            "color": color,
            "pieces": [-1, -1, -1, -1],
        }
        game["turn_order"].append(user.id)

        kb = [[InlineKeyboardButton("✋ پیوستن", callback_data="join")]]
        if len(game["players"]) >= game["player_count"]:
            kb.append([InlineKeyboardButton("▶️ شروع", callback_data="startgame")])

        await q.edit_message_text(
            f"بازیکنان: {', '.join(p['name'] for p in game['players'].values())}\n({len(game['players'])}/{game['player_count']})",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data == "startgame":
        if chat_id not in games:
            return
        game = games[chat_id]
        if len(game["players"]) < 2:
            await q.answer("حداقل ۲ نفر لازم است!", show_alert=True)
            return
        game["playing"] = True
        kb = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
        await q.edit_message_text(
            board_display(game),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )

    elif data == "roll":
        if chat_id not in games:
            return
        game = games[chat_id]
        if not game["playing"]:
            return
        current_uid = game["turn_order"][game["current_turn"] % len(game["turn_order"])]
        if user.id != current_uid:
            await q.answer("نوبت شما نیست!", show_alert=True)
            return

        dice = random.randint(1, 6)
        game["last_dice"] = dice
        movable = get_movable(game, user.id, dice)
        p = game["players"][user.id]
        e, c = COLORS[p["color"]]

        if not movable:
            game["current_turn"] += 1
            kb = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
            await q.edit_message_text(
                f"{board_display(game)}\n\n{e} تاس {dice} — حرکتی ممکن نیست!",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
        else:
            kb = []
            for i in movable:
                pos = p["pieces"][i]
                label = f"مهره {i+1} ({'خانه' if pos == -1 else f'pos {pos}'})"
                kb.append([InlineKeyboardButton(label, callback_data=f"move_{i}")])
            await q.edit_message_text(
                f"{board_display(game)}\n\n{e} تاس *{dice}* انداخت!\nکدام مهره؟",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )

    elif data.startswith("move_"):
        if chat_id not in games:
            return
        game = games[chat_id]
        idx = int(data.split("_")[1])
        current_uid = game["turn_order"][game["current_turn"] % len(game["turn_order"])]
        if user.id != current_uid:
            await q.answer("نوبت شما نیست!", show_alert=True)
            return

        msg = move_piece(game, user.id, idx, game["last_dice"])
        winner = check_winner(game)
        if winner:
            wp = game["players"][winner]
            we, wc = COLORS[wp["color"]]
            await q.edit_message_text(
                f"{board_display(game)}\n\n{msg}\n\n🏆 *{wp['name']} برنده شد!* 🏆",
                parse_mode="Markdown"
            )
            del games[chat_id]
            return

        if game["last_dice"] != 6:
            game["current_turn"] += 1

        kb = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
        await q.edit_message_text(
            f"{board_display(game)}\n\n{msg}",
            reply_markup=InlineKeyboardMarkup(kb),
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
    app.add_handler(CallbackQueryHandler(button))
    print("ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
