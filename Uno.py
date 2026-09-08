# -*- coding: utf-8 -*-
import asyncio, random, time, sqlite3, hashlib, os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types.bot_command import BotCommand
from aiogram.types import (
    ContentTypes, InlineKeyboardMarkup, InlineKeyboardButton,
    Message, CallbackQuery, ContentType, InlineQuery,
    InlineQueryResultArticle, InputTextMessageContent,
    InlineQueryResultCachedSticker, ChosenInlineResult
)
from aiogram.utils import executor

BOT_TOKEN = "8183582932:AAH0pE5E4evzEeQzyJG6ykG1NyusqNqvXbk"
DEV_ID = 1170970828
# Путь к папке data
DATA_DIR = Path(os.environ.get("UNO_DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Путь к базе данных
DB_PATH = DATA_DIR / "uno_game.db"

# Создаем базу, если её нет
if not DB_PATH.exists():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stickers (
            key TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            file_unique_id TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f"База данных создана: {DB_PATH}")
else:
    print(f"База данных уже существует: {DB_PATH}")
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
IGROK = "\u0438\u0433\u0440\u043e\u043a"
IGROK_CAP = "\u0418\u0433\u0440\u043e\u043a"

class AdminStates(StatesGroup):
    waiting_sticker = State()
    auto_setup = State()

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS stickers (key TEXT PRIMARY KEY, file_id TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS leaderboard (user_id INTEGER PRIMARY KEY, wins INTEGER DEFAULT 0, games INTEGER DEFAULT 0)")
    try:
        cols=[r[1] for r in c.execute("PRAGMA table_info(leaderboard)").fetchall()]
        if "chat_id" not in cols:
            c.execute("CREATE TABLE lb2 (chat_id INTEGER, user_id INTEGER, wins INTEGER DEFAULT 0, games INTEGER DEFAULT 0, PRIMARY KEY(chat_id,user_id))")
            c.execute("INSERT OR IGNORE INTO lb2(chat_id,user_id,wins,games) SELECT 0,user_id,wins,games FROM leaderboard")
            c.execute("DROP TABLE leaderboard")
            c.execute("ALTER TABLE lb2 RENAME TO leaderboard")
    except Exception: pass
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.commit(); conn.close()

def get_sticker(key):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT file_id FROM stickers WHERE key=?", (key,))
        row = c.fetchone(); conn.close()
        return row[0] if row else None
    except: return None

def set_sticker_db(key, file_id, fuid=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO stickers(key,file_id,file_unique_id) VALUES(?,?,?)", (key, file_id, fuid))
    conn.commit(); conn.close()

try:
    _c=sqlite3.connect(DB_PATH); _c.execute("ALTER TABLE stickers ADD COLUMN file_unique_id TEXT"); _c.commit(); _c.close()
except Exception: pass

def update_leaderboard(winner, players, chat_id=0):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    for p in players:
        c.execute("INSERT OR IGNORE INTO leaderboard(chat_id,user_id,wins,games) VALUES(?,?,0,0)", (chat_id,p))
        c.execute("UPDATE leaderboard SET games=games+1 WHERE chat_id=? AND user_id=?", (chat_id,p))
    c.execute("UPDATE leaderboard SET wins=wins+1 WHERE chat_id=? AND user_id=?", (chat_id,winner))
    conn.commit(); conn.close()

def get_top(chat_id=0):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id, CAST(user_id AS TEXT), wins, games FROM leaderboard WHERE chat_id=? ORDER BY wins DESC, games ASC LIMIT 25", (chat_id,))
    rows=c.fetchall(); conn.close()
    return rows

def get_all_stickers():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT key, file_id FROM stickers ORDER BY key")
    rows = c.fetchall(); conn.close(); return rows

def register_user(uid, username, fullname=None):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        try: c.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        except Exception: pass
        c.execute("INSERT OR IGNORE INTO users(id,username,created_at) VALUES(?,?,datetime('now'))", (uid, username))
        c.execute("UPDATE users SET username=? WHERE id=?", (username, uid))
        if fullname:
            c.execute("UPDATE users SET full_name=? WHERE id=?", (fullname, uid))
        conn.commit(); conn.close()
    except: pass

def get_all_card_keys():
    keys = []
    colors = ["red","green","yellow","blue"]
    cn = {"red":"\U0001f534 \u043a\u0440\u0430\u0441\u043d\u0443\u044e","green":"\U0001f7e2 \u0437\u0435\u043b\u0451\u043d\u0443\u044e","yellow":"\U0001f7e1 \u0436\u0451\u043b\u0442\u0443\u044e","blue":"\U0001f535 \u0441\u0438\u043d\u044e\u044e"}
    for col in colors:
        for i in range(10):
            keys.append((col+"_"+str(i), cn[col]+" "+str(i)))
        for sp,sn in [("skip","\u043f\u0440\u043e\u043f\u0443\u0441\u043a"),("reverse","\u0440\u0435\u0432\u0435\u0440\u0441"),("draw_two","+2")]:
            keys.append((col+"_"+sp, cn[col]+" "+sn))
    keys.append(("black_wild","\u26ab Wild"))
    keys.append(("black_wild_draw_four","\u26ab Wild+4"))
    for col in colors:
        for i in range(10):
            keys.append(("dark_"+col+"_"+str(i), "\U0001f512 "+cn[col]+" "+str(i)))
        for sp,sn in [("skip","\u043f\u0440\u043e\u043f\u0443\u0441\u043a"),("reverse","\u0440\u0435\u0432\u0435\u0440\u0441"),("draw_two","+2")]:
            keys.append(("dark_"+col+"_"+sp, "\U0001f512 "+cn[col]+" "+sn))
    keys.append(("dark_black_wild","\U0001f512 \u26ab Wild"))
    keys.append(("dark_black_wild_draw_four","\U0001f512 \u26ab Wild+4"))
    keys.append(("action_draw","\U0001f0cf \u0412\u0437\u044f\u0442\u044c"))
    keys.append(("action_pass","\u23ed \u041f\u0440\u043e\u043f\u0443\u0441\u0442\u0438\u0442\u044c"))
    keys.append(("action_bluff","\U0001f3ad \u0411\u043b\u0435\u0444"))
    return keys

COLORS = ["red","green","yellow","blue"]
SPECIALS = ["skip","reverse","draw_two"]
COLOR_RU = {"red":"\U0001f534","green":"\U0001f7e2","yellow":"\U0001f7e1","blue":"\U0001f535","black":"\u26ab"}
TYPE_RU = {"skip":"\u26d4 \u041f\u0440\u043e\u043f\u0443\u0441\u043a","reverse":"\U0001f504 \u0420\u0435\u0432\u0435\u0440\u0441","draw_two":"\u27952","wild":"\U0001f308 Wild","wild_draw_four":"\U0001f480 Wild+4"}
COLOR_ORDER = {"red":0,"green":1,"yellow":2,"blue":3,"black":4}

class Card:
    def __init__(self, color, ctype, value=None):
        self.color=color; self.ctype=ctype; self.value=value
    def get_key(self, dark=False):
        p="dark_" if dark else ""
        return f"{p}{self.color}_{self.value}" if self.ctype=="number" else f"{p}{self.color}_{self.ctype}"
    def display(self):
        icon=COLOR_RU.get(self.color,"")
        return f"{icon} {self.value}" if self.ctype=="number" else f"{icon} {TYPE_RU.get(self.ctype,self.ctype)}"
    def can_play_on(self, top):
        if top is None: return True
        if self.ctype in ("wild","wild_draw_four"): return True
        if self.color==top.color: return True
        if self.ctype!="number" and self.ctype==top.ctype: return True
        if self.ctype=="number" and top.ctype=="number" and self.value==top.value: return True
        return False
    def to_inline_id(self, uid, idx):
        raw=f"{uid}:{idx}:{self.color}:{self.ctype}:{self.value}:{random.randint(0,999999)}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]
    def sort_key(self, can_play):
        po=0 if can_play else 1
        co=COLOR_ORDER.get(self.color,9)
        if self.ctype=="number": v=self.value if self.value is not None else 0
        else: v={"skip":10,"reverse":11,"draw_two":12,"wild":13,"wild_draw_four":14}.get(self.ctype,15)
        return (po,co,v)

def create_deck():
    deck=[]
    for col in COLORS:
        deck.append(Card(col,"number",0))
        for i in range(1,10): deck+=[Card(col,"number",i)]*2
        for sp in SPECIALS: deck+=[Card(col,sp)]*2
    for _ in range(4): deck+=[Card("black","wild"),Card("black","wild_draw_four")]
    return deck

class UnoGame:
    def __init__(self, chat_id, settings, message_id=0):
        self.chat_id=chat_id; self.settings=settings; self.msg_id=message_id
        self.players={}; self.player_names={}
        self.deck=[]; self.discard=[]; self.turn_order=[]
        self.current_idx=0; self.direction=1; self.start_time=0.0
        self.is_active=False; self.winner=None; self.waiting_color_for=None
        self.inline_map={}; self.turn_timer_task=None; self.afk_count={}
        # Bluff tracking: who played wild/wild+4 and did they have alternative
        self.last_wild_player=None
        self.last_wild_had_alternative=False
        self.pending_draw={}
        self.intervened_this_turn=set()
        self.uno_pending={}  # uid: time when player reached 1 card
        self.notif=[]
        self.finish_order=[]; self.scores={}
        self.left_players=set()
        self.uno_task={}  # uid: asyncio task for checking timeout

    def add_player(self, uid, name):
        if uid in self.players: return False
        if uid in getattr(self,"left_players",()): return False
        self.players[uid]=[]; self.player_names[uid]=name; self.afk_count[uid]=0
        if self.is_active: self._deal(uid,8); self.turn_order.append(uid)
        return True

    def players_list_text(self):
        if not self.player_names: return "_\u043f\u043e\u043a\u0430 \u043d\u0438\u043a\u043e\u0433\u043e_"
        lines=[]
        for uid,nm in [(u,self.player_names.get(u,"?")) for u in self.players.keys()]:
            c=len(self.players.get(uid,[])); e=f" ({c})" if self.is_active else ""
            lines.append(f"\u2022 <a href='tg://user?id={uid}'>{nm}</a>{e}")
        return "\n".join(lines)

    def start(self):
        self.deck=create_deck(); random.shuffle(self.deck)
        idxs=[k for k,c in enumerate(self.deck) if c.ctype=="number"]
        first=self.deck.pop(random.choice(idxs)) if idxs else self.deck.pop()
        self.discard=[first]; self.turn_order=list(self.players.keys()); random.shuffle(self.turn_order)
        for uid in self.turn_order: self._deal(uid,8)
        for uid in self.turn_order: self.afk_count[uid]=0
        self.start_time=time.time(); self.is_active=True

    def _deal(self, uid, count):
        limit=8 if self.settings.get("limit_8") else 999
        for _ in range(count):
            if len(self.players.get(uid,[]))>=limit: break
            if not self.deck:
                if len(self.discard)<=1: break
                top=self.discard.pop(); self.deck=self.discard[:]; self.discard=[top]; random.shuffle(self.deck)
            self.players.setdefault(uid,[]).append(self.deck.pop())

    def has_playable(self, uid):
        h=self.players.get(uid,[]); top=self.discard[-1] if self.discard else None
        if not top: return False
        for c in h:
            if c.can_play_on(top): return True
        return False

    def can_play(self, uid, idx):
        h=self.players.get(uid,[])
        return idx<len(h) and h[idx].can_play_on(self.discard[-1])

    def had_alternative_to_wild(self, uid):
        """Check if player had any non-wild playable card BEFORE playing wild"""
        h=self.players.get(uid,[])
        # The wild card is already removed from hand and added to discard
        # So we check discard[-2] as the previous top
        top=self.discard[-2] if len(self.discard)>=2 else None
        if not top: return False
        for c in h:
            if c.ctype not in ("wild","wild_draw_four") and c.can_play_on(top): return True
        return False

    def play_card(self, uid, idx):
        if self.pending_draw.get(uid,0)>0:
            return False,"\u26a0\ufe0f \u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0432\u043e\u0437\u044c\u043c\u0438\u0442\u0435 \u043a\u0430\u0440\u0442\u044b!",None,False
        if not self.can_play(uid,idx): return False,"\U0001f6ab \u041d\u0435\u043b\u044c\u0437\u044f!",None,False
        if self.current_player()==uid: self.check_uno_penalty(uid)
        card=self.players[uid].pop(idx)
        if self.pending_draw.get(uid)==-1: self.pending_draw.pop(uid,None)
        self.clear_skip_marker(uid)
        if card.ctype not in ("wild","wild_draw_four"):
            self.last_wild_player=None
        self.discard.append(card)
        action=None; turn_advanced=False

        if card.ctype=="skip":
            ni=(self.current_idx+self.direction)%len(self.turn_order)
            self.skip_target=self.turn_order[ni]
            action="skip"
            if len(self.turn_order)==2:
                pass
            else:
                self.current_idx=(self.current_idx+self.direction*2)%len(self.turn_order)
            turn_advanced=True
        elif card.ctype=="reverse":
            self.direction*=-1
            if len(self.turn_order)==2:
                # 2-player: reverse = skip opponent, current player goes again
                turn_advanced=True  # Don't call next_turn, stay on same player
            # 3+ players: direction changed, next_turn will go to correct player
        elif card.ctype=="draw_two":
            ni=(self.current_idx+self.direction)%len(self.turn_order)
            nu=self.turn_order[ni]
            # Stacking: carry over the CURRENT player's pending (who was supposed to take cards)
            cur_player=self.turn_order[self.current_idx]
            my_pending=self.pending_draw.pop(cur_player,0)
            # Also clear any pending on the card player if different
            if uid!=cur_player: self.pending_draw.pop(uid,None)
            self.pending_draw[nu]=self.pending_draw.get(nu,0)+my_pending+2
            self.current_idx=ni
            turn_advanced=True
        elif card.ctype=="wild":
            # Track for bluff
            self.last_wild_player=uid
            self.last_wild_had_alternative=self.had_alternative_to_wild(uid)
            action="choose_color"; self.waiting_color_for=uid
        elif card.ctype=="wild_draw_four":
            # Track for bluff
            self.last_wild_player=uid
            self.last_wild_had_alternative=self.had_alternative_to_wild(uid)
            ni=(self.current_idx+self.direction)%len(self.turn_order)
            nu=self.turn_order[ni]
            cur_player=self.turn_order[self.current_idx]
            my_pending=self.pending_draw.pop(cur_player,0)
            if uid!=cur_player: self.pending_draw.pop(uid,None)
            self.pending_draw[nu]=self.pending_draw.get(nu,0)+my_pending+4
            action="choose_color"; self.waiting_color_for=uid; turn_advanced=False

        if self.settings.get("mode_07") and card.ctype=="number":
            if card.value==7: action="swap_7"
            elif card.value==0: action="rotate_0"
        self.afk_count[uid]=0
        # UNO: check if player has exactly 1 card left
        if len(self.players[uid])==1 and uid not in self.uno_pending:
            if self.settings.get("auto_uno",False):
                self.notif.append("\u2705 "+self.player_names.get(uid,IGROK_CAP)+" \u0423\u043d\u043e! (\u0430\u0432\u0442\u043e)")
            else:
                self.uno_pending[uid]=time.time()
        if not self.players[uid]: self._place(uid)
        return True,"",action,turn_advanced

    def draw_exact(self, uid, count):
        """Draw exactly count cards (for pending draw)"""
        self._deal(uid, count)

    def draw_until_playable(self, uid):
        drawn=0
        while True:
            if not self.deck:
                if len(self.discard)<=1: break
                top=self.discard.pop(); self.deck=self.discard[:]; self.discard=[top]; random.shuffle(self.deck)
            if not self.deck: break
            card=self.deck.pop(); self.players.setdefault(uid,[]).append(card); drawn+=1
            if card.can_play_on(self.discard[-1]): break
            if len(self.players.get(uid,[]))>=(8 if self.settings.get("limit_8") else 999): break
        return drawn

    def process_pending_draw(self, uid):
        p=self.pending_draw.pop(uid,0)
        if p<=0: return 0
        self._deal(uid,p); return p

    def clear_skip_marker(self, uid):
        if self.pending_draw.get(uid)==-1:
            self.pending_draw.pop(uid,None)

    def check_uno_penalty(self, actor):
        if self.settings.get("auto_uno",False):
            self.uno_pending.clear(); return
        for uid in list(self.uno_pending.keys()):
            if uid!=actor:
                self._deal(uid,2)
                self.notif.append("\u26a0\ufe0f "+self.player_names.get(uid,IGROK_CAP)+" \u043d\u0435 \u0441\u043a\u0430\u0437\u0430\u043b \u0423\u043d\u043e! +2 \u043a\u0430\u0440\u0442\u044b")
                del self.uno_pending[uid]
    
    def _place(self, uid):
        n=len(self.players)
        place=len(self.finish_order)+1
        pts=n-place
        pw="очко" if pts%10==1 and pts%100!=11 else ("очка" if pts%10 in (2,3,4) and not 11<=pts%100<=14 else "очков")
        self.finish_order.append(uid); self.scores[uid]=pts
        self.notif.append("\U0001f3c6 "+self.player_names.get(uid,IGROK_CAP)+" занял "+str(place)+" место! +"+str(pts)+" "+pw)
        self.pending_draw.pop(uid,None)
        if uid in self.turn_order:
            ci=self.turn_order.index(uid)
            self.turn_order.remove(uid)
            if self.turn_order:
                if self.direction==1: self.current_idx=(ci-1)%len(self.turn_order)
                else: self.current_idx=ci%len(self.turn_order)
        if len(self.turn_order)<=1:
            if self.turn_order:
                last=self.turn_order[0]
                self.finish_order.append(last); self.scores[last]=0
                self.notif.append("\U0001f3c6 "+self.player_names.get(last,IGROK_CAP)+" занял "+str(len(self.finish_order))+" место! +0 очков")
            self.winner=self.finish_order[0]; self.is_active=False

    def next_turn(self):
        self.pending_draw={k:v for k,v in self.pending_draw.items() if v>0}
        # Check UNO penalty: any player with uno_pending who hasn't said UNO
        self.current_idx=(self.current_idx+self.direction)%len(self.turn_order)
        self.intervened_this_turn=set()
    def current_player(self): return self.turn_order[self.current_idx]
    def rotate_hands(self):
        u=[x for x in self.players.keys() if x not in self.finish_order]; h=[self.players[x][:] for x in u]
        random.shuffle(h)
        for i,x in enumerate(u): self.players[x]=h[i]
    def swap_hands(self,a,b): self.players[a],self.players[b]=self.players[b],self.players[a]
    def set_color(self,c):
        if self.discard:
            self.discard[-1].color=c
            if self.discard[-1].ctype=="wild":
                self.discard[-1].ctype="number"
                self.discard[-1].value=""
    def get_stats(self):
        l=["\U0001f465 "+str(len(self.players))]
        for u,h in self.players.items(): l.append("\u2022 "+self.player_names.get(u,str(u))+": "+str(len(h))+" карт")
        return "\n".join(l)
    def duration_str(self):
        s=int(time.time()-self.start_time); m,sc=divmod(s,60); return str(m)+"\u043c "+str(sc)+"\u0441"
    def remove_player(self, uid):
        if uid in self.players:
            del self.players[uid]
            self.left_players.add(uid)
            self.afk_count.pop(uid,None); self.pending_draw.pop(uid,None)
            if uid in self.turn_order:
                self.turn_order.remove(uid)
                if self.current_idx>=len(self.turn_order) and self.turn_order: self.current_idx=0

    def get_inline_results(self, uid):
        results=[]; hand=self.players.get(uid,[])
        is_turn=self.is_active and self.current_player()==uid
        top=self.discard[-1] if self.discard else None
        pending=self.pending_draw.get(uid,0)
        intervention=self.settings.get("intervention",True)

        # Determine what actions are available
        has_any=self.has_playable(uid) if top else False
        waiting_color = self.waiting_color_for is not None
        if waiting_color:
            can_draw = False
            can_pass = False
            can_bluff = False
        elif pending > 0:
            can_draw = is_turn
            can_pass = False
            can_bluff = is_turn and self.last_wild_player is not None and self.last_wild_player!=uid
        else:
            can_draw = is_turn and not has_any
            can_pass = is_turn and pending==-1
            can_bluff = is_turn and self.last_wild_player is not None and self.last_wild_player!=uid

        # Action buttons FIRST (if available)
        if can_draw:
            asid=get_sticker("action_draw")
            aid="action_draw_"+str(uid)+"_"+str(random.randint(0,999999))
            if asid: results.append(InlineQueryResultCachedSticker(id=aid,sticker_file_id=asid))
            else:
                lab="\U0001f0cf \u0412\u0437\u044f\u0442\u044c"
                if pending>0: lab+=" (+"+str(pending)+")"
                results.append(InlineQueryResultArticle(id=aid,title=lab,input_message_content=InputTextMessageContent("UNO_ACTION:draw:"+str(uid))))
        if can_pass:
            psid=get_sticker("action_pass")
            aid2="action_pass_"+str(uid)+"_"+str(random.randint(0,999999))
            if psid: results.append(InlineQueryResultCachedSticker(id=aid2,sticker_file_id=psid))
            else: results.append(InlineQueryResultArticle(id=aid2,title="\u23ed \u041f\u0440\u043e\u043f\u0443\u0441\u0442\u0438\u0442\u044c",input_message_content=InputTextMessageContent("UNO_ACTION:pass:"+str(uid))))
        if can_bluff:
            bsid=get_sticker("action_bluff")
            aid3="action_bluff_"+str(uid)+"_"+str(random.randint(0,999999))
            if bsid: results.append(InlineQueryResultCachedSticker(id=aid3,sticker_file_id=bsid))
            else: results.append(InlineQueryResultArticle(id=aid3,title="\U0001f3ad \u0411\u043b\u0435\u0444!",input_message_content=InputTextMessageContent("UNO_ACTION:bluff:"+str(uid))))

        # Cards sorted: playable first, then by color
        items=[]
        for idx,card in enumerate(hand):
            cp=False
            if top:
                if is_turn and pending<=0 and not waiting_color: cp=card.can_play_on(top)
                elif intervention and pending<=0 and not waiting_color: cp=(card.color==top.color and card.ctype==top.ctype and card.value==top.value)
            items.append((idx,card,cp))
        items.sort(key=lambda x: x[1].sort_key(x[2]))

        for idx,card,cp in items:
            iid=card.to_inline_id(uid,idx)
            self.inline_map[iid]=(uid,idx,cp)
            if cp:
                # Playable: show bright sticker
                sid=get_sticker(card.get_key(dark=False))
                if not sid: sid=get_sticker(card.get_key())
                if sid:
                    results.append(InlineQueryResultCachedSticker(id=iid,sticker_file_id=sid))
                else:
                    t=card.display()+" \u2705"
                    results.append(InlineQueryResultArticle(id=iid,title=t,input_message_content=InputTextMessageContent("UNO_PLAY:"+iid)))
            else:
                # Not playable: show dark sticker with stats as input_message_content
                # When user taps dark sticker, Telegram sends the input_message_content
                dark_sid=get_sticker(card.get_key(dark=True))
                stx="UNO_STATS:"+self.get_stats()+"\n\u23f1 "+self.duration_str()
                if dark_sid:
                    results.append(InlineQueryResultCachedSticker(id=iid,sticker_file_id=dark_sid,input_message_content=InputTextMessageContent(stats_text(self))))
                else:
                    t=card.display()+" \U0001f512"
                    results.append(InlineQueryResultArticle(id=iid,title=t,input_message_content=InputTextMessageContent(stx)))

        return results

games={}; wait_tasks={}; game_settings_cache={}; waiting_swap_target={}

def kb_cards():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("\U0001f440 \u041a\u0430\u0440\u0442\u044b",switch_inline_query_current_chat=""))

def stats_text(game):
    top=game.discard[-1]
    t="\U0001f0cf \u0422\u0435\u043a\u0443\u0449\u0430\u044f \u043a\u0430\u0440\u0442\u0430: "+top.display()+"\n"
    t+="\U0001f3af \u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0438\u0433\u0440\u043e\u043a: "+game.player_names.get(game.current_player(),"?")+"\n"
    t+="\u27a1\ufe0f \u041d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435: "+("\u0432\u043f\u0435\u0440\u0435\u0434" if game.direction==1 else "\u043d\u0430\u0437\u0430\u0434")+"\n"
    for u,h in game.players.items():
        t+="\U0001f920 "+game.player_names.get(u,str(u))+" ("+str(len(h))+" \u043a\u0430\u0440\u0442)\n"
    return t

def kb_wait():
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("\u23f1 30\u0441",callback_data="wt:30"),
        InlineKeyboardButton("\u23f1 1\u043c",callback_data="wt:60"),
        InlineKeyboardButton("\u23f1 2\u043c",callback_data="wt:120"),
        InlineKeyboardButton("\u23f1 3\u043c",callback_data="wt:180"))

def kb_settings(sec,cfg):
    lim="8\ufe0f\u20e3 \u041c\u0430\u043a\u0441 8" if cfg.get("limit_8") else "\u267e \u0411\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430"
    m07="\U0001f504 07:\u0412\u043a\u043b" if cfg.get("mode_07") else "\U0001f504 07:\u0412\u044b\u043a\u043b"
    tt=str(cfg.get("turn_time",30))
    iv="\U0001f91d \u0412\u043c\u0435\u0448.:\u0412\u043a\u043b" if cfg.get("intervention",True) else "\U0001f91d \u0412\u043c\u0435\u0448.:\u0412\u044b\u043a\u043b"
    au="\U0001f916 \u0410\u0432\u0442\u043e\u0423\u043d\u043e:\u0412\u043a\u043b" if cfg.get("auto_uno",False) else "\U0001f916 \u0410\u0432\u0442\u043e\u0423\u043d\u043e:\u0412\u044b\u043a\u043b"
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("\U0001f0cf "+lim,callback_data="cfg:limit:"+str(sec)),
        InlineKeyboardButton(m07,callback_data="cfg:07:"+str(sec)),
        InlineKeyboardButton("\u23f1 \u0425\u043e\u0434:"+tt+"\u0441",callback_data="cfg:turn:"+str(sec)),
        InlineKeyboardButton(iv,callback_data="cfg:interv:"+str(sec)),
        InlineKeyboardButton(au,callback_data="cfg:autouno:"+str(sec)),
        InlineKeyboardButton("\u2705 \u041d\u0430\u0447\u0430\u0442\u044c",callback_data="go:"+str(sec)))

def kb_join():
    return InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton("\U0001f3ae \u041f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u044c\u0441\u044f",callback_data="join"))

def kb_colors(uid):
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("\U0001f534",callback_data="color:red:"+str(uid)),
        InlineKeyboardButton("\U0001f7e2",callback_data="color:green:"+str(uid)),
        InlineKeyboardButton("\U0001f7e1",callback_data="color:yellow:"+str(uid)),
        InlineKeyboardButton("\U0001f535",callback_data="color:blue:"+str(uid)))

def kb_swap(game,uid):
    kb=InlineKeyboardMarkup(row_width=1)
    for ouid,nm in game.player_names.items():
        if ouid!=uid: kb.add(InlineKeyboardButton("\U0001f504 "+nm,callback_data="swap7:"+str(ouid)))
    kb.add(InlineKeyboardButton("\u274c",callback_data="swap7:skip"))
    return kb

async def update_lobby_msg(game, extra=""):
    if not game.msg_id: return
    t="\U0001f0cf <b>UNO</b>\n\U0001f465 ("+str(len(game.players))+"):\n"+game.players_list_text()
    if extra: t+="\n"+extra
    try: await bot.edit_message_text(t,chat_id=game.chat_id,message_id=game.msg_id,reply_markup=kb_join(),parse_mode="HTML")
    except: pass

async def send_state(chat_id, game, extra="", skip_sticker=False):
    top=game.discard[-1]; cur=game.current_player()
    while game.notif:
        ntxt=game.notif.pop(0)
        try: await bot.send_message(chat_id,ntxt)
        except Exception: pass
    cn=game.player_names.get(cur,"?")
    if not skip_sticker:
        sid=get_sticker(top.get_key())
        if sid:
            try: await bot.send_sticker(chat_id,sid)
            except: pass
    t=COLOR_RU.get(top.color,"")+" → ход игрока <a href='tg://user?id="+str(cur)+"'>"+cn+"</a>"
    kb=InlineKeyboardMarkup().add(InlineKeyboardButton("\U0001f440 \u041a\u0430\u0440\u0442\u044b",switch_inline_query_current_chat=""))
    await bot.send_message(chat_id,t,reply_markup=kb,parse_mode="HTML")
    if game.turn_timer_task: game.turn_timer_task.cancel()
    tt=game.settings.get("turn_time",30)
    async def turn_timeout():
        try:
            await asyncio.sleep(tt)
        except asyncio.CancelledError:
            return
        g=games.get(chat_id)
        if not g or not g.is_active or g.current_player()!=cur: return
        uid=cur; nm=g.player_names.get(uid,IGROK_CAP)
        g.check_uno_penalty(uid)
        drawn=g.process_pending_draw(uid)
        if drawn>0 and g.discard and g.discard[-1].ctype=="draw_two":
            g.discard[-1].value="resolved"
        elif g.discard and g.discard[-1].ctype=="wild_draw_four":
            g.discard[-1].ctype="number"
            g.discard[-1].value=""
            g.pending_draw.pop(uid,None)
        g.afk_count[uid]=g.afk_count.get(uid,0)+1
        if g.afk_count[uid]>=3:
            g.remove_player(uid)
            try: await bot.send_message(chat_id,"\U0001f6ab "+nm+" \u043a\u0438\u043a\u043d\u0443\u0442!")
            except: pass
            if len(g.players)<2: await bot.send_message(chat_id,"\u274c"); games.pop(chat_id,None); return
        else:
            if drawn>0:
                try: await bot.send_message(chat_id,"\u23f1 "+nm+" взял "+str(drawn)+" карт"+" \u043f\u0440\u043e\u043f\u0443\u0441\u043a")
                except: pass
            else:
                try: await bot.send_message(chat_id,"\u23f1 "+nm+" \u043f\u0440\u043e\u043f\u0443\u0441\u043a")
                except: pass
        g.next_turn(); await send_state(chat_id,g,skip_sticker=True)
    game.turn_timer_task=asyncio.ensure_future(turn_timeout())

@dp.inline_handler()
async def inline_handler(q):
    uid=q.from_user.id; game=None
    for g in games.values():
        if uid in g.players: game=g; break
    if not game:
        await bot.answer_inline_query(q.id,results=[InlineQueryResultArticle(id="ng",title="\u041d\u0435 \u0432 \u0438\u0433\u0440\u0435",input_message_content=InputTextMessageContent("/startuno"))],cache_time=0,is_personal=True); return
    r=game.get_inline_results(uid)
    if not r: r=[InlineQueryResultArticle(id="em",title="\u041d\u0435\u0442 \u043a\u0430\u0440\u0442",input_message_content=InputTextMessageContent(""))]
    await bot.answer_inline_query(q.id,results=r,cache_time=0,is_personal=True)

# ================= STICKER LISTENER =================
@dp.message_handler(content_types=ContentTypes.STICKER)
async def sticker_listener(msg):
    cid=msg.chat.id; uid=msg.from_user.id
    game=games.get(cid)
    if not game or not game.is_active or uid not in game.players: return
    fid=msg.sticker.file_id
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT key FROM stickers WHERE file_id=?",(fid,))
    rowsx=c.fetchall()
    if not rowsx and getattr(msg.sticker,"file_unique_id",None):
        c.execute("SELECT key FROM stickers WHERE file_unique_id=?",(msg.sticker.file_unique_id,))
        rowsx=c.fetchall()
    conn.close()
    if not rowsx:
        await bot.send_message(cid,"\u26a0\ufe0f \u0421\u0442\u0438\u043a\u0435\u0440 \u043d\u0435 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0435")
        return
    keysx=[r[0] for r in rowsx]
    if any(k.startswith("action_") for k in keysx):
        card_key=[k for k in keysx if k.startswith("action_")][0]
    else:
        handx=game.players.get(uid,[])
        mx=[k for k in keysx if any(cc.get_key()==k for cc in handx)]
        if mx: card_key=mx[0]
        else:
            dx=[k for k in keysx if k.startswith("dark_")]
            if not dx: return
            card_key=dx[0]

    if card_key.startswith("dark_"):
        top=game.discard[-1]
        t="\U0001f0cf \u0422\u0435\u043a\u0443\u0449\u0430\u044f \u043a\u0430\u0440\u0442\u0430: "+top.display()+"\n"
        t+="\U0001f3af \u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0438\u0433\u0440\u043e\u043a: "+game.player_names.get(game.current_player(),"?")+"\n"
        t+="\u27a1\ufe0f \u041d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435: "+("\u0432\u043f\u0435\u0440\u0435\u0434" if game.direction==1 else "\u043d\u0430\u0437\u0430\u0434")+"\n"
        for u,h in game.players.items():
            t+="\U0001f920 "+game.player_names.get(u,str(u))+" ("+str(len(h))+" \u043a\u0430\u0440\u0442)\n"
        await bot.send_message(cid,t)
        return
        game.check_uno_penalty(uid)
    # Action stickers
    if card_key.startswith("action_"):
        act=card_key.replace("action_","")
        if act=="draw":
            if game.current_player()!=uid: return
            # Draw EXACTLY pending amount, or draw until playable if no pending
            pending=game.pending_draw.get(uid,0)
            if pending>0:
                game.process_pending_draw(uid)
                nm=game.player_names.get(uid,IGROK_CAP)
                await bot.send_message(cid,"\U0001f0cf "+nm+" взял "+str(pending)+" карт")
                if game.discard and game.discard[-1].ctype=="draw_two":
                    game.discard[-1].value="resolved"
                elif game.discard and game.discard[-1].ctype=="wild_draw_four":
                    game.discard[-1].ctype="number"
                    game.discard[-1].value=""
                    game.pending_draw.pop(uid,None)
                # After taking penalty cards, turn passes
                game.next_turn()
                await send_state(cid,game,skip_sticker=True)
            else:
                drawn=game.draw_until_playable(uid)
                nm=game.player_names.get(uid,IGROK_CAP)
                if drawn>0: await bot.send_message(cid,"\U0001f0cf "+nm+" взял "+str(drawn)+" карт")
                if game.has_playable(uid):
                    game.pending_draw[uid]=-1
                    await bot.send_message(cid,"\u2705 "+nm+", \u0445\u043e\u0434\u0438\u0442\u0435!",reply_markup=kb_cards())
                else:
                    game.next_turn()
                    await send_state(cid,game,skip_sticker=True)
        elif act=="pass":
            if game.current_player()!=uid: return
            game.pending_draw.pop(uid,None)
            game.pending_draw.pop(uid,None)
            game.next_turn(); await send_state(cid,game,skip_sticker=True)
        elif act=="bluff":
            if game.current_player()!=uid: return
            if game.last_wild_player is None:
                await bot.send_message(cid,"\u26a0\ufe0f \u041d\u0435\u043a\u043e\u0433\u043e \u043e\u0431\u0432\u0438\u043d\u044f\u0442\u044c!"); return
            buid=game.last_wild_player
            bnm=game.player_names.get(buid,"?")
            anm=game.player_names.get(uid,IGROK_CAP)
            if game.last_wild_had_alternative:
                # Bluff detected! Wild player gets +4
                game._deal(buid,4)
                await bot.send_message(cid,"\U0001f3ad "+anm+" \u043f\u043e\u0439\u043c\u0430\u043b "+bnm+" \u043d\u0430 \u0431\u043b\u0435\u0444\u0435! +4 карты для "+bnm+"!")
            else:
                # Wrong bluff! Accuser gets +6
                game._deal(uid,6)
                await bot.send_message(cid,"\U0001f3ad "+anm+" \u043e\u0448\u0438\u0431\u0441\u044f! +6 карты для "+anm+"!")
            game.last_wild_player=None
            if game.discard and game.discard[-1].ctype=="wild_draw_four":
                game.discard[-1].ctype="number"
                game.discard[-1].value=""
                game.pending_draw.pop(uid,None)
            game.next_turn()
            await send_state(cid,game,skip_sticker=True)
        return

    # Dark sticker from chat = show stats
    if card_key.startswith("dark_"):
        st=game.get_stats()+"\n\u23f1 "+game.duration_str()
        nm=game.player_names.get(uid,IGROK_CAP)
        await bot.send_message(cid,"\U0001f512 "+nm+":\n"+st)
        return

    # Parse card from key
    k=card_key; pk=k.split("_",1); color=pk[0]; rest=pk[1] if len(pk)>1 else "0"
    if rest in ("skip","reverse","draw_two","wild","wild_draw_four"): fc=Card(color,rest)
    else:
        try: fc=Card(color,"number",int(rest))
        except: return

    # Find matching card in hand
    hand=game.players.get(uid,[]); mi=None
    for i,c in enumerate(hand):
        if c.color==fc.color and c.ctype==fc.ctype and c.value==fc.value: mi=i; break
    if mi is None: return

    top=game.discard[-1]
    if not fc.can_play_on(top):
        st=game.get_stats()+"\n\u23f1 "+game.duration_str()
        await bot.send_message(cid,"\U0001f512 \u041d\u0435\u043b\u044c\u0437\u044f!\n"+st)
        return

    is_turn=game.current_player()==uid
    interv=game.settings.get("intervention",True)

    if not is_turn and not interv:
        await bot.send_message(cid,"\u23f3 \u041d\u0435 \u0432\u0430\u0448 \u0445\u043e\u0434!"); return

    if not is_turn and interv:
        # Intervention: exact same card required
        if not (fc.color==top.color and fc.ctype==top.ctype and fc.value==top.value):
            return
        if uid in game.intervened_this_turn:
            await bot.send_message(cid,"\u26a0\ufe0f \u0423\u0436\u0435 \u0432\u043c\u0435\u0448\u0430\u043b\u0438\u0441\u044c!"); return
        ok,mt,act,adv=game.play_card(uid,mi)
        if act=="skip": await bot.send_message(cid,"\U0001f6ab "+game.player_names.get(game.skip_target,IGROK_CAP)+" \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430\u0435\u0442 \u0445\u043e\u0434")
        if not ok: return
        game.intervened_this_turn.add(uid)
        if game.winner is not None:
            if game.turn_timer_task: game.turn_timer_task.cancel()
            while game.notif:
                await bot.send_message(cid,game.notif.pop(0))
            update_leaderboard(game.winner,list(game.players.keys()),cid)
            try: await bot.unpin_chat_message(cid)
            except Exception: pass
            t="\U0001f3c6 \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0438\u0433\u0440\u044b!\n"
            for pi,pu in enumerate(game.finish_order):
                pv=game.scores.get(pu,0)
                pw="\u043e\u0447\u043a\u043e" if pv%10==1 and pv%100!=11 else ("\u043e\u0447\u043a\u0430" if pv%10 in (2,3,4) and not 11<=pv%100<=14 else "\u043e\u0447\u043a\u043e\u0432")
                t+=str(pi+1)+". "+game.player_names.get(pu,str(pu))+" \u2014 "+str(pv)+" "+pw+"\n"
            t+="\u23f1 "+game.duration_str()
            await bot.send_message(cid,t); games.pop(cid,None); return
        if act=="choose_color":
            await bot.send_message(cid,"\U0001f308",reply_markup=kb_colors(uid)); return
        if act=="swap_7":
            await bot.send_message(cid,"\U0001f504",reply_markup=kb_swap(game,uid)); waiting_swap_target[cid]=uid; return
        if act=="rotate_0":
            game.rotate_hands()
            await bot.send_message(cid,"\U0001f504 \u0412\u0441\u0435 \u0438\u0433\u0440\u043e\u043a\u0438 \u043f\u043e\u043c\u0435\u043d\u044f\u043b\u0438\u0441\u044c \u043a\u0430\u0440\u0442\u0430\u043c\u0438 \u0441\u043b\u0443\u0447\u0430\u0439\u043d\u044b\u043c \u043e\u0431\u0440\u0430\u0437\u043e\u043c!")
        if not adv and act!="choose_color": game.next_turn()
        await send_state(cid,game,skip_sticker=True); return

    # Normal turn
    if game.current_player()!=uid:
        print("UNO IGNORE sticker: uid",uid,"current",game.current_player(),"key",card_key)
        return
    ok,mt,act,adv=game.play_card(uid,mi)
    if act=="skip": await bot.send_message(cid,"\U0001f6ab "+game.player_names.get(game.skip_target,IGROK_CAP)+" \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430\u0435\u0442 \u0445\u043e\u0434")
    if not ok: await bot.send_message(cid,"\U0001f6ab"); return
    if game.winner is not None:
        if game.turn_timer_task: game.turn_timer_task.cancel()
        while game.notif:
            await bot.send_message(cid,game.notif.pop(0))
        update_leaderboard(game.winner,list(game.players.keys()),cid)
        try: await bot.unpin_chat_message(cid)
        except Exception: pass
        t="\U0001f3c6 \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0438\u0433\u0440\u044b!\n"
        for pi,pu in enumerate(game.finish_order):
            pv=game.scores.get(pu,0)
            pw="\u043e\u0447\u043a\u043e" if pv%10==1 and pv%100!=11 else ("\u043e\u0447\u043a\u0430" if pv%10 in (2,3,4) and not 11<=pv%100<=14 else "\u043e\u0447\u043a\u043e\u0432")
            t+=str(pi+1)+". "+game.player_names.get(pu,str(pu))+" \u2014 "+str(pv)+" "+pw+"\n"
        t+="\u23f1 "+game.duration_str()
        await bot.send_message(cid,t); games.pop(cid,None); return
    if act=="choose_color":
        await bot.send_message(cid,"\U0001f308",reply_markup=kb_colors(uid)); return
    if act=="swap_7":
        await bot.send_message(cid,"\U0001f504",reply_markup=kb_swap(game,uid)); waiting_swap_target[cid]=uid; return
    if act=="rotate_0":
        game.rotate_hands()
        await bot.send_message(cid,"\U0001f504 \u0412\u0441\u0435 \u0438\u0433\u0440\u043e\u043a\u0438 \u043f\u043e\u043c\u0435\u043d\u044f\u043b\u0438\u0441\u044c \u043a\u0430\u0440\u0442\u0430\u043c\u0438 \u0441\u043b\u0443\u0447\u0430\u0439\u043d\u044b\u043c \u043e\u0431\u0440\u0430\u0437\u043e\u043c!")
    # For skip/reverse/draw_two/wild_draw_four: turn already advanced in play_card
    # For wild/number: need to call next_turn
    if not adv and act!="choose_color": game.next_turn()
    # UNO check handled in next_turn()
    await send_state(cid,game,skip_sticker=True)

# ================= INTERCEPT UNO_ MESSAGES =================
@dp.message_handler(lambda m: m.text and m.text.startswith("UNO_"))
async def intercept_uno(msg):
    t=msg.text.strip(); uid=msg.from_user.id; cid=msg.chat.id
    game=games.get(cid)
    if not game or not game.is_active:
        try: await msg.delete()
        except: pass; return

    if t.startswith("UNO_PLAY:"):
        iid=t[9:]
        if iid not in game.inline_map:
            try: await msg.delete()
            except: pass; return
        cuid,cidx,cp=game.inline_map[iid]
        if cuid!=uid or not cp:
            try: await msg.delete()
            except: pass; return
        is_turn=game.current_player()==uid
        interv=game.settings.get("intervention",True)
        if not is_turn and not interv:
            try: await msg.delete()
            except: pass; return
        if not is_turn and interv:
            if uid in game.intervened_this_turn:
                try: await msg.delete()
                except: pass; return
        ok,mt,act,adv=game.play_card(uid,cidx)
        if act=="skip": await bot.send_message(cid,"\U0001f6ab "+game.player_names.get(game.skip_target,IGROK_CAP)+" \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430\u0435\u0442 \u0445\u043e\u0434")
        if not ok:
            try: await msg.delete()
            except: pass; return
        if not is_turn: game.intervened_this_turn.add(uid)
        try: await msg.delete()
        except: pass
        if game.winner is not None:
            if game.turn_timer_task: game.turn_timer_task.cancel()
            update_leaderboard(game.winner,list(game.players.keys()),cid)
            wn=game.player_names[game.winner]
            await bot.send_message(cid,"\U0001f3c6 "+wn+"!"); games.pop(cid,None); return
        if act=="choose_color":
            await bot.send_message(cid,"\U0001f308",reply_markup=kb_colors(uid)); return
        if act=="swap_7":
            await bot.send_message(cid,"\U0001f504",reply_markup=kb_swap(game,uid)); waiting_swap_target[cid]=uid; return
        if act=="rotate_0":
            game.rotate_hands()
            await bot.send_message(cid,"\U0001f504 \u0412\u0441\u0435 \u0438\u0433\u0440\u043e\u043a\u0438 \u043f\u043e\u043c\u0435\u043d\u044f\u043b\u0438\u0441\u044c \u043a\u0430\u0440\u0442\u0430\u043c\u0438 \u0441\u043b\u0443\u0447\u0430\u0439\u043d\u044b\u043c \u043e\u0431\u0440\u0430\u0437\u043e\u043c!")
        if not adv and act!="choose_color": game.next_turn()
        await send_state(cid,game,skip_sticker=True); return

    elif t.startswith("UNO_STATS:"):
        st=t[10:]
        try: await msg.delete()
        except: pass
        nm=game.player_names.get(uid,IGROK_CAP)
        await bot.send_message(cid,"\U0001f512 "+nm+":\n"+st); return

    elif t.startswith("UNO_ACTION:"):
        ps=t.split(":")
        if len(ps)<3:
            try: await msg.delete()
            except: pass; return
        act2=ps[1]; auid=int(ps[2])
        if auid!=uid:
            try: await msg.delete()
            except: pass; return
        try: await msg.delete()
        except: pass
        if act2=="draw":
            if game.current_player()!=uid: return
            pending=game.pending_draw.get(uid,0)
            nm=game.player_names.get(uid,IGROK_CAP)
            if pending>0:
                game.process_pending_draw(uid)
                await bot.send_message(cid,"\U0001f0cf "+nm+" взял "+str(pending)+" карт")
                if game.discard and game.discard[-1].ctype=="draw_two":
                    game.discard[-1].value="resolved"
                elif game.discard and game.discard[-1].ctype=="wild_draw_four":
                    game.discard[-1].ctype="number"
                    game.discard[-1].value=""
                    game.pending_draw.pop(uid,None)
                game.next_turn()
                await send_state(cid,game,skip_sticker=True)
            else:
                drawn=game.draw_until_playable(uid)
                if drawn>0: await bot.send_message(cid,"\U0001f0cf "+nm+" взял "+str(drawn)+" карт")
                if game.has_playable(uid):
                    game.pending_draw[uid]=-1
                    await bot.send_message(cid,"\u2705 "+nm,reply_markup=kb_cards())
                else: game.next_turn(); await send_state(cid,game,skip_sticker=True)
        elif act2=="pass":
            game.pending_draw.pop(uid,None)
            if game.current_player()!=uid: return
            game.next_turn(); await send_state(cid,game,skip_sticker=True)
        elif act2=="bluff":
            if game.current_player()!=uid: return
            if game.last_wild_player is None:
                await bot.send_message(cid,"\u26a0\ufe0f"); return
            buid=game.last_wild_player
            bnm=game.player_names.get(buid,"?")
            anm=game.player_names.get(uid,IGROK_CAP)
            if game.last_wild_had_alternative:
                game._deal(buid,4)
                await bot.send_message(cid,"\U0001f3ad +4 "+bnm)
            else:
                game._deal(uid,6)
                await bot.send_message(cid,"\U0001f3ad +6 "+anm)
            game.last_wild_player=None
            if game.discard and game.discard[-1].ctype=="wild_draw_four":
                game.discard[-1].ctype="number"
                game.discard[-1].value=""
                game.pending_draw.pop(uid,None)
            game.next_turn(); await send_state(cid,game,skip_sticker=True)
        return

    try: await msg.delete()
    except: pass

# ================= COMMANDS =================
@dp.message_handler(commands=["start"])
async def cmd_start(msg):
    register_user(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    await msg.answer("\U0001f0cf <b>UNO Bot</b>\n/startuno | /unostat | /top",parse_mode="HTML")

@dp.message_handler(commands=["top"])
async def cmd_top(msg):
    rows=get_top(msg.chat.id)
    if not rows: return await msg.answer("\U0001f4ca \u041d\u0435\u0442 \u0438\u0433\u0440.")
    medals=["\U0001f947","","\U0001f949"]; t="\U0001f3c6 \u0422\u043e\u043f-25 \u0438\u0433\u0440\u043e\u043a\u043e\u0432:\n"
    for i,row in enumerate(rows):
        uid=row[0]
        if len(row)>=4: w,gc=row[2],row[3]
        else: w,gc=row[1],row[2]
        conn=sqlite3.connect(DB_PATH); c=conn.cursor()
        c.execute("SELECT full_name,username FROM users WHERE id=?",(uid,))
        urow=c.fetchone(); conn.close()
        if urow and urow[0]: name=urow[0]
        elif urow and urow[1]: name=urow[1]
        else: name=str(uid)
        name=str(name).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        m=medals[i] if i<3 else str(i+1)+"."
        t+=m+" <a href='tg://user?id="+str(uid)+"'>"+name+"</a> \U0001f3c6"+str(w)+"/\U0001f3ae"+str(gc)+"\n"
    await msg.answer(t,parse_mode="HTML")

@dp.message_handler(commands=["unostat"])
async def cmd_unostat(msg):
    game=games.get(msg.chat.id)
    if not game or not game.is_active: return await msg.answer("\u26a0\ufe0f \u041d\u0435\u0442 \u0438\u0433\u0440\u044b.")
    top=game.discard[-1] if game.discard else None
    tt=top.display() if top else "?"
    cur=game.player_names.get(game.current_player(),"?")
    await msg.answer("\U0001f4ca "+COLOR_RU.get(top.color,"")+" → ход игрока "+cur+"\n"+game.get_stats()+"\n⏱ "+game.duration_str())

@dp.message_handler(commands=["startuno"])
async def cmd_startuno(msg):
    if msg.chat.type=="private": return await msg.answer("\u2757 \u0422\u043e\u043b\u044c\u043a\u043e \u0432 \u0433\u0440\u0443\u043f\u043f\u0430\u0445!")
    register_user(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    cid=msg.chat.id
    uid=msg.from_user.id
    name=msg.from_user.full_name or (IGROK_CAP+str(uid))
    game=games.get(cid)
    # Active game: auto-join
    if game and game.is_active:
        if uid in game.players:
            return await msg.answer("\u26a0\ufe0f \u0412\u044b \u0443\u0436\u0435 \u0432 \u0438\u0433\u0440\u0435!")
        game.add_player(uid,name)
        game.turn_order.append(uid)
        game.afk_count[uid]=0
        await msg.answer("\U0001f389 <a href='tg://user?id="+str(uid)+"'>"+name+"</a> \u043f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u043b\u0441\u044f \u043a \u0438\u0433\u0440\u0435!",parse_mode="HTML")
        await send_state(cid,game,skip_sticker=True)
        return
    # Lobby exists: join lobby
    if game and not game.is_active:
        if uid in game.players:
            return await msg.answer("\u26a0\ufe0f \u0412\u044b \u0443\u0436\u0435 \u0432 \u043b\u043e\u0431\u0431\u0438!")
        game.add_player(uid,name)
        await update_lobby_msg(game)
        await msg.answer("\U0001f389 <a href='tg://user?id="+str(uid)+"'>"+name+"</a> \u043f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u043b\u0441\u044f \u043a \u043b\u043e\u0431\u0431\u0438!",parse_mode="HTML")
        return
    sent=await msg.answer("\u23f3 \u0412\u0440\u0435\u043c\u044f:",reply_markup=kb_wait())
    try: await bot.pin_chat_message(cid,sent.message_id,disable_notification=True)
    except: pass


@dp.callback_query_handler(Text(startswith="wt:"))
async def cb_wt(q):
    sec=int(q.data.split(":")[1])
    cfg=game_settings_cache.setdefault(q.message.chat.id,{"limit_8":False,"mode_07":False,"turn_time":30,"intervention":True,"auto_uno":False})
    try: await q.message.edit_text("\u2699\ufe0f ("+str(sec)+"\u0441)",reply_markup=kb_settings(sec,cfg),parse_mode="HTML")
    except: pass
    await q.answer()

@dp.callback_query_handler(Text(startswith="cfg:"))
async def cb_cfg(q):
    ps=q.data.split(":"); p,s=ps[1],ps[2]
    cfg=game_settings_cache.setdefault(q.message.chat.id,{"limit_8":False,"mode_07":False,"turn_time":30,"intervention":True,"auto_uno":False})
    if p=="limit": cfg["limit_8"]=not cfg.get("limit_8",False)
    elif p=="07": cfg["mode_07"]=not cfg.get("mode_07",False)
    elif p=="turn":
        ts=[15,30,45,60,90,120]; cur=cfg.get("turn_time",30)
        i=ts.index(cur) if cur in ts else 1; cfg["turn_time"]=ts[(i+1)%len(ts)]
    elif p=="interv": cfg["intervention"]=not cfg.get("intervention",True)
    elif p=="autouno": cfg["auto_uno"]=not cfg.get("auto_uno",False)
    elif p=="auto_uno": cfg["auto_uno"]=not cfg.get("auto_uno",False)
    try: await q.message.edit_reply_markup(reply_markup=kb_settings(int(s),cfg))
    except: pass
    await q.answer()

@dp.callback_query_handler(Text(startswith="go:"))
async def cb_go(q):
    sec=int(q.data.split(":")[1]); cid=q.message.chat.id
    cfg=game_settings_cache.get(cid,{"limit_8":False,"mode_07":False,"turn_time":30,"intervention":True,"auto_uno":False})
    game=UnoGame(cid,cfg.copy(),message_id=q.message.message_id); games[cid]=game
    cuid=q.from_user.id; cn=q.from_user.full_name or (IGROK_CAP+str(cuid))
    game.add_player(cuid,cn)
    t="\U0001f0cf <b>UNO "+str(sec)+"\u0441</b>\n\U0001f465 (1):\n"+game.players_list_text()
    try: await q.message.edit_text(t,reply_markup=kb_join(),parse_mode="HTML")
    except: pass
    try: await bot.pin_chat_message(cid,q.message.message_id,disable_notification=True)
    except: pass
    async def cd():
        await asyncio.sleep(sec); g=games.get(cid)
        if not g or g.is_active: return
        if len(g.players)<2: await bot.send_message(cid,"\u274c"); games.pop(cid,None); return
        g.start(); await send_state(cid,g)
    wait_tasks[cid]=asyncio.ensure_future(cd())
    await q.answer("\u23f3")

@dp.callback_query_handler(lambda q: q.data=="join")
async def cb_join(q):
    game=games.get(q.message.chat.id)
    if not game: return await q.answer()
    register_user(q.from_user.id, q.from_user.username, q.from_user.full_name)
    uid=q.from_user.id; name=q.from_user.full_name or (IGROK_CAP+str(uid))
    if game.add_player(uid,name):
        await update_lobby_msg(game)

@dp.callback_query_handler(Text(startswith="color:"))
async def cb_color(q):
    game=games.get(q.message.chat.id)
    if not game: return await q.answer("\u26a0\ufe0f",show_alert=True)
    ps=q.data.split(":"); color,puid=ps[1],int(ps[2])
    if game.waiting_color_for!=puid: return await q.answer("\u26a0\ufe0f \u041d\u0435 \u0432\u0430\u0448 \u0432\u044b\u0431\u043e\u0440!",show_alert=True)
    game.waiting_color_for=None
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    game.set_color(color)
    game.next_turn(); await send_state(q.message.chat.id,game,skip_sticker=True); await q.answer()

@dp.callback_query_handler(Text(startswith="swap7:"))
async def cb_swap7(q):
    game=games.get(q.message.chat.id)
    if not game: return await q.answer("\u26a0\ufe0f",show_alert=True)
    target=q.data.split(":")[1]; req=waiting_swap_target.pop(q.message.chat.id,None)
    if req is None: return await q.answer("\u26a0\ufe0f \u0423\u0436\u0435 \u0432\u044b\u0431\u0440\u0430\u043d\u043e",show_alert=True)
    if q.from_user.id!=req: return await q.answer("\u26a0\ufe0f \u041d\u0435 \u0432\u0430\u0448 \u0432\u044b\u0431\u043e\u0440!",show_alert=True)
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    if target!="skip":
        tuid=int(target)
        if req in game.finish_order or tuid in game.finish_order:
            return await q.answer("\u26a0\ufe0f",show_alert=True)
        game.swap_hands(req,tuid)
        await bot.send_message(q.message.chat.id,"\U0001f504 "+game.player_names.get(req,IGROK_CAP)+" \u043f\u043e\u043c\u0435\u043d\u044f\u043b\u0441\u044f \u043a\u0430\u0440\u0442\u0430\u043c\u0438 \u0441 "+game.player_names.get(tuid,IGROK_CAP)+"!")
    else:
        await bot.send_message(q.message.chat.id,"\U0001f504 "+game.player_names.get(req,IGROK_CAP)+" \u043d\u0435 \u0441\u0442\u0430\u043b \u043c\u0435\u043d\u044f\u0442\u044c\u0441\u044f \u043a\u0430\u0440\u0442\u0430\u043c\u0438")
    game.next_turn(); await send_state(q.message.chat.id,game,skip_sticker=True); await q.answer()

# ================= ADMIN =================
@dp.message_handler(lambda m: m.from_user.id==DEV_ID and m.text and m.text.strip().startswith("/set ") and m.reply_to_message is not None and m.reply_to_message.sticker is not None)
async def cmd_set_sticker(msg):
    key=msg.text.strip()[5:].strip()
    set_sticker_db(key,msg.reply_to_message.sticker.file_id,msg.reply_to_message.sticker.file_unique_id)
    await msg.answer("✅ Стикер зарегистрирован: "+key)

@dp.message_handler(lambda m: m.from_user.id==DEV_ID and m.text and m.text.strip()=="/mystickers")
async def admin_ms(msg):
    rows=get_all_stickers()
    if not rows: return await msg.answer("\U0001f4ed")
    for k,f in rows:
        try: await bot.send_sticker(msg.chat.id,f); await msg.answer("<code>"+k+"</code>",parse_mode="HTML")
        except: pass

@dp.message_handler(lambda m: m.from_user.id==DEV_ID and m.text and m.text.strip()=="/autostickers",state="*")
async def admin_as(msg,state):
    ak=get_all_card_keys()
    await state.set_state(AdminStates.auto_setup)
    await state.update_data(auto_keys=ak,auto_idx=0)
    k0,d0=ak[0]; await msg.answer("1/"+str(len(ak))+": "+d0+" <code>"+k0+"</code>",parse_mode="HTML")

@dp.message_handler(content_types=ContentTypes.STICKER,state=AdminStates.auto_setup)
async def admin_ar(msg,state):
    data=await state.get_data(); keys=data.get("auto_keys",[]); idx=data.get("auto_idx",0)
    if idx>=len(keys): await state.finish(); return
    k,d=keys[idx]; set_sticker_db(k,msg.sticker.file_id)
    await msg.answer("\u2705 <code>"+k+"</code>",parse_mode="HTML")
    idx+=1
    if idx>=len(keys): await state.finish(); return await msg.answer("\U0001f389 "+str(len(keys)))
    await state.update_data(auto_idx=idx)
    nk,nd=keys[idx]; await msg.answer(str(idx+1)+"/"+str(len(keys))+": "+nd+" <code>"+nk+"</code>",parse_mode="HTML")

@dp.message_handler(lambda m: m.from_user.id==DEV_ID,state=AdminStates.auto_setup)
async def admin_aw(msg,state):
    data=await state.get_data(); keys=data.get("auto_keys",[]); idx=data.get("auto_idx",0)
    if idx<len(keys): await msg.answer(str(idx+1)+"/"+str(len(keys))+": "+keys[idx][1])

@dp.message_handler(lambda m: m.from_user.id==DEV_ID and m.text and m.text.startswith("/setsticker"),state="*")
async def admin_sc(msg,state):
    ps=msg.text.split(maxsplit=1)
    if len(ps)<2 or not ps[1].strip(): return await msg.answer("/setsticker <key>")
    k=ps[1].strip()
    await state.set_state(AdminStates.waiting_sticker)
    await state.update_data(sticker_key=k)
    await msg.answer("\U0001f4ce <code>"+k+"</code>",parse_mode="HTML")

@dp.message_handler(content_types=ContentTypes.STICKER,state=AdminStates.waiting_sticker)
async def admin_sr(msg,state):
    data=await state.get_data(); k=data.get("sticker_key")
    if not k: await state.finish(); return
    set_sticker_db(k,msg.sticker.file_id); await state.finish()
    await msg.answer("\u2705 <code>"+k+"</code>",parse_mode="HTML")

@dp.message_handler(lambda m: m.from_user.id==DEV_ID,state=AdminStates.waiting_sticker)
async def admin_sw(msg,state):
    await msg.answer("\u26a0\ufe0f")


@dp.message_handler(commands=["unoleave"])
async def cmd_unoleave(msg):
    cid=msg.chat.id; uid=msg.from_user.id
    game=games.get(cid)
    if not game:
        return await msg.answer("⚠️ Нет активной игры.")
    if uid not in game.players:
        return await msg.answer("⚠️ Вы не в игре.")
    nm=game.player_names.get(uid,IGROK_CAP)
    game.remove_player(uid)
    if game.is_active:
        game.finish_order.append(uid); game.scores[uid]=0
    await msg.answer("🚪 "+nm+" вышел из игры.")
    if not game.is_active:
        # Lobby mode - just update lobby message
        await update_lobby_msg(game)
    elif len(game.players)>=2:
        await send_state(cid,game,skip_sticker=True)
        if len(game.players)==0:
            games.pop(cid,None)
    else:
        # Active game
        if len(game.players)<2:
            await msg.answer("❌ Недостаточно игроков. Игра окончена.")
            if game.turn_timer_task: game.turn_timer_task.cancel()
            games.pop(cid,None)
        else:
            if game.current_player()==uid or uid not in game.turn_order:
                pass
            await send_state(cid,game,skip_sticker=True)


# UNO command handler
@dp.message_handler(lambda m: m.text and m.text.strip().lower() in ("uno","уно","уно"))
async def cmd_uno(msg):
    cid=msg.chat.id; uid=msg.from_user.id
    game=games.get(cid)
    if not game or not game.is_active: return
    if uid not in game.uno_pending: return
    # Player said UNO in time!
    del game.uno_pending[uid]
    if uid in game.uno_task:
        game.uno_task[uid].cancel()
        del game.uno_task[uid]
    nm=game.player_names.get(uid,IGROK_CAP)
    await msg.answer("✅ "+nm+" сказал Уно!")

@dp.message_handler(commands=["unogo"])
async def cmd_unogo(msg):
    cid=msg.chat.id; uid=msg.from_user.id
    game=games.get(cid)
    if not game or game.is_active:
        return await msg.answer("\u26a0\ufe0f \u041d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0433\u043e \u043b\u043e\u0431\u0431\u0438.")
    owner=getattr(msg.chat,"owner_id",None)
    if uid!=DEV_ID and uid!=owner and uid!=getattr(game,"host",None):
        return await msg.answer("\u26a0\ufe0f \u0422\u043e\u043b\u044c\u043a\u043e \u0433\u043b\u0430\u0432\u043d\u044b\u0439 \u0430\u0434\u043c\u0438\u043d, \u0441\u043e\u0437\u0434\u0430\u0442\u0435\u043b\u044c \u0433\u0440\u0443\u043f\u043f\u044b \u0438\u043b\u0438 \u0441\u043e\u0437\u0434\u0430\u0442\u0435\u043b\u044c \u043b\u043e\u0431\u0431\u0438 \u043c\u043e\u0436\u0435\u0442 \u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c \u0438\u0433\u0440\u0443.")
    if len(game.players)<2:
        return await msg.answer("\u26a0\ufe0f \u041d\u0443\u0436\u043d\u043e \u043c\u0438\u043d\u0438\u043c\u0443\u043c 2 \u0438\u0433\u0440\u043e\u043a\u0430.")
    t=wait_tasks.pop(cid,None)
    if t: t.cancel()
    game.start(); await send_state(cid,game)

async def on_startup(dp):
    cmds=[
        BotCommand(command="start",description="\u0418\u043d\u0444\u043e"),
        BotCommand(command="startuno",description="\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0438\u0433\u0440\u0443"),
        BotCommand(command="unogo",description="\u041d\u0430\u0447\u0430\u0442\u044c \u0438\u0433\u0440\u0443 \u0441\u0440\u0430\u0437\u0443"),
        BotCommand(command="unoleave",description="\u041f\u043e\u043a\u0438\u043d\u0443\u0442\u044c \u0438\u0433\u0440\u0443"),
        BotCommand(command="unostat",description="\u0418\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f \u043e \u0442\u0435\u043a\u0443\u0449\u0435\u0439 \u0438\u0433\u0440\u0435"),
        BotCommand(command="top",description="\u0422\u043e\u043f \u0438\u0433\u0440\u043e\u043a\u043e\u0432"),
    ]
    r1=await bot.set_my_commands(cmds)
    print("set_my_commands result:",r1)
    try:
        r2=await bot.set_my_commands(cmds,scope={"type":"all_group_chats"})
        print("groups scope result:",r2)
    except Exception as e:
        print("groups scope ERR:",e)

if __name__=="__main__":
    init_db()
    print(" UNO Bot OK")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
