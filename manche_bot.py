import random, logging, io
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8945308523:AAFueYNr5nrpTEYj6DPmgF6GvR4JIPOzYs4"

SIZE = 660
CELL = SIZE // 11
BG = (205, 170, 120)

COLORS = {0: ("🔴","قرمز"), 1: ("🔵","آبی"), 2: ("🟢","سبز"), 3: ("🟡","زرد")}
P_COLORS = {0:(220,50,50), 1:(50,80,200), 2:(50,180,50), 3:(180,160,50)}
P_DARK   = {0:(140,30,30), 1:(30,50,140), 2:(30,120,30), 3:(120,100,30)}

PATH = [
    (4,10),(4,9),(4,8),(4,7),(4,6),
    (3,6),(2,6),(1,6),(0,6),
    (0,5),(0,4),(0,3),(0,2),(0,1),(0,0),
    (1,0),(2,0),(3,0),(4,0),
    (5,0),(5,1),(5,2),(5,3),(5,4),
    (6,4),(7,4),(8,4),(9,4),(10,4),
    (10,5),(10,6),(10,7),(10,8),(10,9),(10,10),
    (9,10),(8,10),(7,10),(6,10),
    (6,9),(6,8),(6,7),(6,6),
    (6,5),(7,5),(8,5),(9,5),(10,5),
]

START_IDX = {0:0, 1:13, 2:26, 3:39}
PARKING = {
    0: [(1,8),(2,8),(1,9),(2,9)],
    1: [(1,1),(2,1),(1,2),(2,2)],
    2: [(8,1),(9,1),(8,2),(9,2)],
    3: [(8,8),(9,8),(8,9),(9,9)],
}
SAFE = {0,8,13,21,26,34,39,47}
games = {}


def draw_circle(draw, cx, cy, r, fill, outline, width=2):
    draw.ellipse([cx-r,cy-r,cx+r,cy+r], fill=fill, outline=outline, width=width)


def draw_board(players=None, dice=0, msg=""):
    img = Image.new("RGB", (SIZE, SIZE+50), BG)
    draw = ImageDraw.Draw(img)

    for i in range(len(PATH)-1):
        c1,r1=PATH[i]; c2,r2=PATH[i+1]
        draw.line([c1*CELL+CELL//2, r1*CELL+CELL//2, c2*CELL+CELL//2, r2*CELL+CELL//2], fill=(80,60,40), width=3)

    for i,(c,r) in enumerate(PATH):
        cx,cy = c*CELL+CELL//2, r*CELL+CELL//2
        if i in SAFE:
            ci = i//13 % 4
            draw_circle(draw, cx, cy, CELL//2-4, P_COLORS[ci], (0,0,0), 3)
        else:
            draw_circle(draw, cx, cy, CELL//2-4, (255,255,255), (0,0,0), 2)

    for color, positions in PARKING.items():
        for c,r in positions:
            draw_circle(draw, c*CELL+CELL//2, r*CELL+CELL//2, CELL//2-6, P_COLORS[color], P_DARK[color], 3)

    draw_circle(draw, 5*CELL+CELL//2, 5*CELL+CELL//2, CELL//2-2, (255,255,200), (100,80,0), 3)

    if players:
        slot = {}
        for uid,p in players.items():
            for i,pos in enumerate(p["pieces"]):
                if pos==-1 or pos>=100: continue
                idx=pos-1
                if 0<=idx<len(PATH):
                    slot.setdefault(idx,[]).append(p["color"])
        offsets=[(-8,-8),(8,-8),(-8,8),(8,8)]
        for idx,cols in slot.items():
            c,r=PATH[idx]
            cx,cy=c*CELL+CELL//2, r*CELL+CELL//2
            for k,col in enumerate(cols[:4]):
                ox,oy=offsets[k] if len(cols)>1 else (0,0)
                draw_circle(draw, cx+ox, cy+oy, 10 if len(cols)>1 else 14, P_COLORS[col], P_DARK[col], 3)

    if dice>0 or msg:
        draw.rectangle([0, SIZE, SIZE, SIZE+50], fill=(180,145,100))
        draw.text((10, SIZE+10), f"🎲 تاس: {dice}   {msg}", fill=(40,30,20))

    buf=io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def new_game(cid, count):
    return {"cid":cid,"count":count,"players":{},"order":[],"turn":0,"playing":False,"dice":0}


def movable(game, uid, dice):
    p=game["players"][uid]; res=[]
    for i,pos in enumerate(p["pieces"]):
        if pos==-1 and dice==6: res.append(i)
        elif pos!=-1 and pos<100: res.append(i)
    return res


def do_move(game, uid, idx):
    p=game["players"][uid]; color=p["color"]; pos=p["pieces"][idx]; dice=game["dice"]
    e=COLORS[color][0]; msg=""
    if pos==-1:
        p["pieces"][idx]=START_IDX[color]+1
        msg=f"{e} مهره {idx+1} وارد بازی شد!"
    else:
        new=pos+dice
        if new>=52:
            p["pieces"][idx]=100+idx
            msg=f"{e} مهره {idx+1} به خانه رسید! 🏆"
        else:
            if (new-1) not in SAFE:
                for ouid,op in game["players"].items():
                    if ouid==uid: continue
                    for j,opos in enumerate(op["pieces"]):
                        if opos==new:
                            op["pieces"][j]=-1
                            msg+=f"🍽 مهره {COLORS[op['color']][0]} خورده شد!\n"
            p["pieces"][idx]=new
            msg+=f"{e} مهره {idx+1} به خانه {new} رفت."
    return msg


def check_winner(game):
    for uid,p in game["players"].items():
        if all(x>=100 for x in p["pieces"]): return uid
    return None


def status(game):
    lines=[]
    for uid,p in game["players"].items():
        e=COLORS[p["color"]][0]
        home=sum(1 for x in p["pieces"] if x>=100)
        lines.append(f"{e} {p['name']}: {home}/4 🏆")
    if game["playing"] and game["order"]:
        uid=game["order"][game["turn"]%len(game["order"])]
        if uid in game["players"]:
            p=game["players"][uid]
            lines.append(f"\n🎯 نوبت: {COLORS[p['color']][0]} {p['name']}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb=[[InlineKeyboardButton("🎮 ۲ نفره",callback_data="new_2")],
        [InlineKeyboardButton("🎮 ۴ نفره",callback_data="new_4")]]
    await update.message.reply_text("🎲 *ربات منچ*\nتعداد بازیکنان:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    d=q.data; cid=q.message.chat_id; user=q.from_user

    if d.startswith("new_"):
        count=int(d[4:])
        games[cid]=new_game(cid,count); g=games[cid]
        g["players"][user.id]={"name":user.first_name,"color":0,"pieces":[-1,-1,-1,-1]}
        g["order"].append(user.id)
        kb=[[InlineKeyboardButton("✋ پیوستن",callback_data="join")]]
        if len(g["players"])>=count: kb.append([InlineKeyboardButton("▶️ شروع",callback_data="go")])
        await q.edit_message_text(f"بازی {count} نفره\nبازیکنان: {', '.join(p['name'] for p in g['players'].values())} ({len(g['players'])}/{count})", reply_markup=InlineKeyboardMarkup(kb))

    elif d=="join":
        if cid not in games: await q.answer("بازی نیست!",show_alert=True); return
        g=games[cid]
        if user.id in g["players"]: await q.answer("قبلاً وارد شدید!",show_alert=True); return
        if len(g["players"])>=g["count"]: await q.answer("بازی پر است!",show_alert=True); return
        color=len(g["players"])
        g["players"][user.id]={"name":user.first_name,"color":color,"pieces":[-1,-1,-1,-1]}
        g["order"].append(user.id)
        kb=[[InlineKeyboardButton("✋ پیوستن",callback_data="join")]]
        if len(g["players"])>=g["count"]: kb.append([InlineKeyboardButton("▶️ شروع",callback_data="go")])
        await q.edit_message_text(f"بازیکنان: {', '.join(p['name'] for p in g['players'].values())} ({len(g['players'])}/{g['count']})", reply_markup=InlineKeyboardMarkup(kb))

    elif d=="go":
        if cid not in games: return
        g=games[cid]
        if len(g["players"])<2: await q.answer("حداقل ۲ نفر!",show_alert=True); return
        g["playing"]=True
        kb=[[InlineKeyboardButton("🎲 تاس بینداز",callback_data="roll")]]
        img=draw_board(g["players"])
        await q.message.reply_photo(photo=img, caption=status(g), reply_markup=InlineKeyboardMarkup(kb))
        await q.delete_message()

    elif d=="roll":
        if cid not in games: return
        g=games[cid]
        cur=g["order"][g["turn"]%len(g["order"])]
        if user.id!=cur: await q.answer("نوبت شما نیست!",show_alert=True); return
        dice=random.randint(1,6); g["dice"]=dice
        mv=movable(g,user.id,dice)
        e=COLORS[g["players"][user.id]["color"]][0]
        if not mv:
            g["turn"]+=1
            kb=[[InlineKeyboardButton("🎲 تاس بینداز",callback_data="roll")]]
            img=draw_board(g["players"],dice,f"{e} حرکتی نیست")
            await q.message.reply_photo(photo=img, caption=f"{e} تاس {dice} — حرکتی ممکن نیست!\n\n{status(g)}", reply_markup=InlineKeyboardMarkup(kb))
            await q.delete_message()
        else:
            p=g["players"][user.id]
            kb=[[InlineKeyboardButton(f"مهره {i+1} (خانه {'شروع' if p['pieces'][i]==-1 else p['pieces'][i]})",callback_data=f"mv_{i}")] for i in mv]
            img=draw_board(g["players"],dice,f"{e} تاس {dice}")
            await q.message.reply_photo(photo=img, caption=f"{e} تاس *{dice}* انداخت!\nکدام مهره؟", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            await q.delete_message()

    elif d.startswith("mv_"):
        if cid not in games: return
        g=games[cid]
        cur=g["order"][g["turn"]%len(g["order"])]
        if user.id!=cur: await q.answer("نوبت شما نیست!",show_alert=True); return
        idx=int(d[3:]); msg=do_move(g,user.id,idx)
        w=check_winner(g)
        if w:
            wp=g["players"][w]; we=COLORS[wp["color"]][0]
            img=draw_board(g["players"],g["dice"],"برنده!")
            await q.message.reply_photo(photo=img, caption=f"{msg}\n\n🏆 *{wp['name']} برنده شد!* 🏆", parse_mode="Markdown")
            await q.delete_message(); del games[cid]; return
        if g["dice"]!=6: g["turn"]+=1
        kb=[[InlineKeyboardButton("🎲 تاس بینداز",callback_data="roll")]]
        img=draw_board(g["players"],g["dice"],msg)
        await q.message.reply_photo(photo=img, caption=f"{msg}\n\n{status(g)}", reply_markup=InlineKeyboardMarkup(kb))
        await q.delete_message()


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid=update.message.chat_id
    if cid in games: del games[cid]; await update.message.reply_text("بازی پایان یافت 👋")
    else: await update.message.reply_text("بازی‌ای نیست.")


def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("end",end))
    app.add_handler(CallbackQueryHandler(btn))
    print("ربات روشنه...")
    app.run_polling()

if __name__=="__main__":
    main()
