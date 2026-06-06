import random
import logging
import io
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8945308523:AAFueYNr5nrpTEYj6DPmgF6GvR4JIPOzYs4"

COLORS = {0: ("🔴", "قرمز", (200,50,50)), 1: ("🔵", "آبی", (50,80,200)), 2: ("🟢", "سبز", (50,180,50)), 3: ("🟡", "زرد", (200,180,50))}
HOME_COLORS = [(220,80,80), (80,120,220), (80,200,80), (220,200,80)]
START_SQUARES = {0: 1, 1: 14, 2: 27, 3: 40}
HOME_ENTRY = {0: 52, 1: 13, 2: 26, 3: 39}
SAFE_SQUARES = {1, 9, 14, 22, 27, 35, 40, 48}

PATH = [
    (6,0),(7,0),(8,0),(9,0),(10,0),(10,1),(10,2),(10,3),(10,4),
    (10,5),(10,6),(9,6),(8,6),(7,6),(6,6),(5,6),(5,5),(5,4),
    (5,3),(5,2),(5,1),(5,0),(4,0),(3,0),(2,0),(1,0),(0,0),
    (0,1),(0,2),(0,3),(0,4),(0,5),(0,6),(1,6),(2,6),(3,6),
    (4,6),(5,6),(5,7),(5,8),(5,9),(5,10),(6,10),(7,10),(8,10),
    (9,10),(10,10),(10,9),(10,8),(10,7),(10,6),(9,6),
]

CELL = 58
COLS = 11
ROWS = 11

games = {}


def draw_board(players=None, last_dice=0, message=""):
    W = COLS * CELL
    H = ROWS * CELL + 50
    img = Image.new("RGB", (W, H), (240, 220, 180))
    draw = ImageDraw.Draw(img)

    corners = [
        ((0, 0, 5*CELL, 5*CELL), HOME_COLORS[0]),
        ((6*CELL, 0, W, 5*CELL), HOME_COLORS[1]),
        ((0, 6*CELL, 5*CELL, W), HOME_COLORS[2]),
        ((6*CELL, 6*CELL, W, 11*CELL), HOME_COLORS[3]),
    ]
    for rect, color in corners:
        draw.rectangle(rect, fill=color)

    for i, (c, r) in enumerate(PATH[:52]):
        x, y = c*CELL, r*CELL
        color = (150, 230, 150) if (i+1) in SAFE_SQUARES else (255, 255, 255)
        draw.rectangle([x+2, y+2, x+CELL-2, y+CELL-2], fill=color, outline=(80,60,40), width=2)
        draw.text((x+4, y+4), str(i+1), fill=(60,60,60))

    draw.rectangle([5*CELL+3, 5*CELL+3, 6*CELL-3, 6*CELL-3], fill=(255,255,200), outline=(100,80,0), width=2)
    draw.text((5*CELL+10, 5*CELL+15), "WIN", fill=(150,100,0))

    if players:
        pos_count = {}
        for uid, p in players.items():
            color_rgb = COLORS[p["color"]][2]
            for i, pos in enumerate(p["pieces"]):
                if pos == -1 or pos >= 100:
                    continue
                idx = pos - 1
                if idx < len(PATH):
                    c, r = PATH[idx]
                    key = (c, r)
                    offset = pos_count.get(key, 0)
                    pos_count[key] = offset + 1
                    ox = (offset % 2) * 20
                    oy = (offset // 2) * 20
                    cx = c*CELL + 10 + ox
                    cy = r*CELL + 10 + oy
                    draw.ellipse([cx, cy, cx+18, cy+18], fill=color_rgb, outline=(0,0,0), width=2)

    if last_dice > 0:
        dice_faces = {1:"⚀",2:"⚁",3:"⚂",4:"⚃",5:"⚄",6:"⚅"}
        draw.text((10, ROWS*CELL+10), f"تاس: {last_dice}  {message}", fill=(50,50,50))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def new_game(chat_id, count):
    return {"chat_id": chat_id, "count": count, "players": {}, "order": [], "turn": 0, "playing": False, "dice": 0}


def movable(game, uid, dice):
    p = game["players"][uid]
    result = []
    for i, pos in enumerate(p["pieces"]):
        if pos == -1 and dice == 6:
            result.append(i)
        elif pos != -1 and pos < 100:
            result.append(i)
    return result


def do_move(game, uid, idx):
    p = game["players"][uid]
    color = p["color"]
    pos = p["pieces"][idx]
    dice = game["dice"]
    e = COLORS[color][0]
    msg = ""
    if pos == -1:
        p["pieces"][idx] = START_SQUARES[color]
        msg = f"{e} مهره {idx+1} وارد بازی شد!"
    else:
        new = pos + dice
        if new >= HOME_ENTRY[color] + 6:
            p["pieces"][idx] = 100 + idx
            msg = f"{e} مهره {idx+1} به خانه رسید! 🏆"
        else:
            if new not in SAFE_SQUARES:
                for ouid, op in game["players"].items():
                    if ouid == uid:
                        continue
                    for j, opos in enumerate(op["pieces"]):
                        if opos == new:
                            op["pieces"][j] = -1
                            msg += f"🍽 مهره {COLORS[op['color']][0]} خورده شد!\n"
            p["pieces"][idx] = new
            msg += f"{e} مهره {idx+1} به خانه {new} رفت."
    return msg


def check_winner(game):
    for uid, p in game["players"].items():
        if all(x >= 100 for x in p["pieces"]):
            return uid
    return None


def status_text(game):
    lines = []
    for uid, p in game["players"].items():
        e = COLORS[p["color"]][0]
        home = sum(1 for x in p["pieces"] if x >= 100)
        lines.append(f"{e} {p['name']}: {home}/4 خانه")
    if game["playing"] and game["order"]:
        uid = game["order"][game["turn"] % len(game["order"])]
        if uid in game["players"]:
            p = game["players"][uid]
            lines.append(f"\n🎯 نوبت: {COLORS[p['color']][0]} {p['name']}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🎮 ۲ نفره", callback_data="new_2")],
          [InlineKeyboardButton("🎮 ۴ نفره", callback_data="new_4")]]
    await update.message.reply_text("🎲 *ربات منچ*\nتعداد بازیکنان را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    cid = q.message.chat_id
    user = q.from_user

    if d.startswith("new_"):
        count = int(d[4:])
        games[cid] = new_game(cid, count)
        g = games[cid]
        g["players"][user.id] = {"name": user.first_name, "color": 0, "pieces": [-1,-1,-1,-1]}
        g["order"].append(user.id)
        kb = [[InlineKeyboardButton("✋ پیوستن", callback_data="join")]]
        if len(g["players"]) >= count:
            kb.append([InlineKeyboardButton("▶️ شروع", callback_data="go")])
        await q.edit_message_text(f"بازی {count} نفره ایجاد شد!\nبازیکنان: {', '.join(p['name'] for p in g['players'].values())} ({len(g['players'])}/{count})", reply_markup=InlineKeyboardMarkup(kb))

    elif d == "join":
        if cid not in games:
            await q.answer("بازی نیست!", show_alert=True); return
        g = games[cid]
        if user.id in g["players"]:
            await q.answer("قبلاً وارد شدید!", show_alert=True); return
        if len(g["players"]) >= g["count"]:
            await q.answer("بازی پر است!", show_alert=True); return
        color = len(g["players"])
        g["players"][user.id] = {"name": user.first_name, "color": color, "pieces": [-1,-1,-1,-1]}
        g["order"].append(user.id)
        kb = [[InlineKeyboardButton("✋ پیوستن", callback_data="join")]]
        if len(g["players"]) >= g["count"]:
            kb.append([InlineKeyboardButton("▶️ شروع", callback_data="go")])
        await q.edit_message_text(f"بازیکنان: {', '.join(p['name'] for p in g['players'].values())} ({len(g['players'])}/{g['count']})", reply_markup=InlineKeyboardMarkup(kb))

    elif d == "go":
        if cid not in games: return
        g = games[cid]
        if len(g["players"]) < 2:
            await q.answer("حداقل ۲ نفر!", show_alert=True); return
        g["playing"] = True
        uid = g["order"][0]
        p = g["players"][uid]
        e = COLORS[p["color"]][0]
        kb = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
        img = draw_board(g["players"], 0, "")
        await q.message.reply_photo(photo=img, caption=f"{status_text(g)}", reply_markup=InlineKeyboardMarkup(kb))
        await q.delete_message()

    elif d == "roll":
        if cid not in games: return
        g = games[cid]
        cur = g["order"][g["turn"] % len(g["order"])]
        if user.id != cur:
            await q.answer("نوبت شما نیست!", show_alert=True); return
        dice = random.randint(1, 6)
        g["dice"] = dice
        mv = movable(g, user.id, dice)
        p = g["players"][user.id]
        e = COLORS[p["color"]][0]

        if not mv:
            g["turn"] += 1
            kb = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
            img = draw_board(g["players"], dice, f"{e} حرکتی نیست!")
            await q.message.reply_photo(photo=img, caption=f"{e} تاس {dice} انداخت — حرکتی ممکن نیست!\n\n{status_text(g)}", reply_markup=InlineKeyboardMarkup(kb))
            await q.delete_message()
        else:
            kb = [[InlineKeyboardButton(f"مهره {i+1} (خانه {p['pieces'][i] if p['pieces'][i]!=-1 else 'شروع'})", callback_data=f"mv_{i}")] for i in mv]
            img = draw_board(g["players"], dice, f"{e} تاس {dice}")
            await q.message.reply_photo(photo=img, caption=f"{e} تاس *{dice}* انداخت!\nکدام مهره را حرکت دهید؟", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            await q.delete_message()

    elif d.startswith("mv_"):
        if cid not in games: return
        g = games[cid]
        cur = g["order"][g["turn"] % len(g["order"])]
        if user.id != cur:
            await q.answer("نوبت شما نیست!", show_alert=True); return
        idx = int(d[3:])
        msg = do_move(g, user.id, idx)
        w = check_winner(g)
        if w:
            wp = g["players"][w]
            we = COLORS[wp["color"]][0]
            img = draw_board(g["players"], g["dice"], "برنده!")
            await q.message.reply_photo(photo=img, caption=f"{msg}\n\n🏆 *{wp['name']} برنده شد!* 🏆", parse_mode="Markdown")
            await q.delete_message()
            del games[cid]; return

        if g["dice"] != 6:
            g["turn"] += 1
        kb = [[InlineKeyboardButton("🎲 تاس بینداز", callback_data="roll")]]
        img = draw_board(g["players"], g["dice"], msg)
        await q.message.reply_photo(photo=img, caption=f"{msg}\n\n{status_text(g)}", reply_markup=InlineKeyboardMarkup(kb))
        await q.delete_message()


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.message.chat_id
    if cid in games:
        del games[cid]
        await update.message.reply_text("بازی پایان یافت 👋")
    else:
        await update.message.reply_text("بازی‌ای در جریان نیست.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end))
    app.add_handler(CallbackQueryHandler(btn))
    print("ربات روشنه...")
    app.run_polling()


if __name__ == "__main__":
    main()
