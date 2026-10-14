import streamlit as st
import random
import itertools
from collections import Counter

# ==========================================
# 1. 撲克底層算法
# ==========================================
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

def create_deck():
    return [r + s for r in RANKS for s in SUITS]

def get_hand_category(card1, card2):
    r1, s1 = card1[:-1], card1[-1]
    r2, s2 = card2[:-1], card2[-1]
    v1, v2 = RANK_VALUES[r1], RANK_VALUES[r2]
    high = r1 if v1 >= v2 else r2
    low = r2 if v1 >= v2 else r1
    suited = 's' if s1 == s2 else 'o'
    return high + low + ('' if high == low else suited)

def evaluate_board_texture(board):
    if len(board) < 3: return "Preflop"
    ranks = [RANK_VALUES[c[:-1]] for c in board]
    suits = [c[-1] for c in board]
    if len(set(ranks[:3])) < 3: return "Paired Board (對子面)"
    if len(set(suits[:3])) == 1: return "Monotone (單色面)"
    if max(ranks[:3]) - min(ranks[:3]) <= 4: return "Wet / Dynamic (濕滑動態面)"
    return "Dry / Static (乾燥靜態面)"

# ==========================================
# 2. GTO 覆盤引擎
# ==========================================
GTO_OPEN_STANDARDS = {
    'UTG': {'pairs': 7, 'suited_ax': 10, 'broadway_off': ['AKo', 'AQo', 'AJo', 'KQo'], 'connectors': ['JTs', 'T9s', '98s']},
    'HJ':  {'pairs': 5, 'suited_ax': 6,  'broadway_off': ['AKo', 'AQo', 'AJo', 'ATo', 'KQo', 'KJo'], 'connectors': ['JTs', 'T9s', '98s', '87s']},
    'CO':  {'pairs': 2, 'suited_ax': 2,  'broadway_off': ['AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'KQo', 'KJo', 'QJo'], 'connectors': ['JTs', 'T9s', '98s', '87s', '76s', '65s']},
    'BTN': {'pairs': 2, 'suited_ax': 2,  'broadway_off': ['AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'A7o', 'A5o', 'KQo', 'KJo', 'QJo', 'JTo'], 'connectors': ['T9s', '98s', '87s', '76s', '65s', '54s', 'J8s', 'T8s']},
    'SB':  {'pairs': 2, 'suited_ax': 2,  'broadway_off': ['AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'KQo', 'KJo', 'QJo'], 'connectors': ['T9s', '98s', '87s', '76s']}
}

def analyze_preflop_gto(hand_cat, position):
    std = GTO_OPEN_STANDARDS.get(position, GTO_OPEN_STANDARDS['UTG'])
    r1, r2 = hand_cat[0], hand_cat[1]
    
    if r1 == r2:
        if RANK_VALUES[r1] >= std['pairs']: return "✅ **GTO 翻前**: 100% 頻率 Open Raise（具備絕佳純價值與攤牌勝率）。"
        return "⚠️ **GTO 翻前**: 邊緣口袋對子。在早中位容易遭遇 3-Bet，建議棄牌或混合極低頻率防守。"
    if hand_cat.endswith('s') and r1 == 'A' and RANK_VALUES[r2] >= std['suited_ax']:
        return "✅ **GTO 翻前**: 100% Open Raise（同花 A 具備強大阻擋牌與 Nuts 潛力）。"
    if hand_cat in std['broadway_off'] or hand_cat in std.get('connectors', []):
        return "✅ **GTO 翻前**: 標準 Open Raise 範圍。"
    return "❌ **GTO 翻前**: 純負 EV 牌型，理論標準直接 Fold。"

def analyze_postflop_gto(custom_bet, pot, board_texture):
    pct = (custom_bet / pot) * 100 if pot > 0 else 0
    feedback = [f"🎯 **你的下注**: **{custom_bet:.1f} BB** (相當於 **{pct:.1f}% 底池**)"]

    if pct <= 45:
        feedback.append("📌 **GTO 基準**: 接近 **33% 底池 (小尺寸)**")
        if "Dry" in board_texture:
            feedback.append("💡 **理論解讀**: **非常優秀**。乾燥面（如 K-8-2r）你有範圍優勢，GTO 建議用小注高頻施壓。")
        else:
            feedback.append("⚠️ **理論解讀**: **尺寸偏小**。濕滑面給對手買牌賠率太好，無法保護價值範圍。")
    elif pct <= 90:
        feedback.append("📌 **GTO 基準**: 接近 **67%-75% 底池 (大尺寸)**")
        if "Wet" in board_texture:
            feedback.append("💡 **理論解讀**: **非常優秀**。濕滑牌面需要大尺寸建立『堅果保護』，剝奪對手隱含賠率。")
        else:
            feedback.append("⚠️ **理論解讀**: **略微過大**。乾燥面不需要這麼昂貴的保護，容易把對手弱牌打蓋。")
    else:
        feedback.append("📌 **GTO 基準**: 接近 **125%+ 底池 (超池 Overbet)**")
        feedback.append("💡 **理論解讀**: **極化打法**。需具備顯著『堅果優勢』時使用。若對手是緊弱玩家，也是很好的剝削詐唬尺寸！")
    return feedback

# ==========================================
# 3. 狀態管理
# ==========================================
st.set_page_config(page_title="GTO 手機響應式訓練器", layout="centered")

POSITIONS = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

class Bot:
    def __init__(self, name):
        self.name = name
        self.stack = 100.0
        self.bet = 0.0

if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.bots = [Bot("Bot_HJ"), Bot("Bot_CO"), Bot("Bot_BTN"), Bot("Bot_SB"), Bot("Bot_BB")]
    st.session_state.hero_stack = 100.0
    st.session_state.hero_bet = 0.0
    st.session_state.btn_idx = 0
    st.session_state.stage = 'INIT'
    st.session_state.reports = []

def start_hand():
    if st.session_state.hero_stack <= 0: st.session_state.hero_stack = 100.0
    for b in st.session_state.bots:
        if b.stack <= 0: b.stack = 100.0
        b.bet = 0.0

    st.session_state.deck = create_deck()
    random.shuffle(st.session_state.deck)
    st.session_state.hero_cards = [st.session_state.deck.pop(), st.session_state.deck.pop()]
    st.session_state.board = []
    st.session_state.reports = []
    st.session_state.btn_idx = (st.session_state.btn_idx + 1) % 6
    st.session_state.hero_pos = POSITIONS[st.session_state.btn_idx]
    
    st.session_state.pot = 1.5
    st.session_state.hero_bet = 0.0
    
    if st.session_state.hero_pos == 'SB':
        st.session_state.hero_bet = 0.5
        st.session_state.hero_stack -= 0.5
    elif st.session_state.hero_pos == 'BB':
        st.session_state.hero_bet = 1.0
        st.session_state.hero_stack -= 1.0
        
    st.session_state.stage = 'PREFLOP'

if st.session_state.stage == 'INIT': start_hand()

# ==========================================
# 4. RWD 響應式 SVG 牌桌繪製引擎 (強制去縮排)
# ==========================================
def draw_card(card, x, y):
    if not card: return ""
    rank, suit = card[:-1], card[-1]
    color = "#e53e3e" if suit in ['♥', '♦'] else "#1a202c"
    # 強制去縮排
    return f"""<g transform="translate({x}, {y})">
<rect x="0" y="0" width="36" height="52" rx="4" fill="white" stroke="#718096" stroke-width="1"/>
<text x="18" y="26" font-family="Arial" font-size="20" font-weight="bold" fill="{color}" text-anchor="middle" dominant-baseline="central">{rank}{suit}</text>
</g>"""

def draw_player(cx, cy, name, pos, stack, bet, is_hero=False, cards=None):
    svg = ""
    if bet > 0:
        bx = cx + (400 - cx) * 0.25
        by = cy + (250 - cy) * 0.25
        svg += f"""<rect x="{bx-25}" y="{by-12}" width="50" height="24" rx="12" fill="rgba(0,0,0,0.7)"/>
<text x="{bx}" y="{by}" font-family="Arial" font-size="12" font-weight="bold" fill="#68d391" text-anchor="middle" dominant-baseline="central">{bet}</text>"""
    
    border = "#ecc94b" if is_hero else "#4a5568"
    bg = "#2d3748" if is_hero else "#1a202c"
    badge = "#ecc94b" if is_hero else "#e2e8f0"
    
    svg += f"""<rect x="{cx-45}" y="{cy-18}" width="90" height="36" rx="6" fill="{bg}" stroke="{border}" stroke-width="2"/>
<rect x="{cx-42}" y="{cy-14}" width="22" height="14" rx="3" fill="{badge}"/>
<text x="{cx-31}" y="{cy-7}" font-family="Arial" font-size="9" font-weight="bold" fill="black" text-anchor="middle" dominant-baseline="central">{pos}</text>
<text x="{cx-15}" y="{cy-7}" font-family="Arial" font-size="11" font-weight="bold" fill="white" dominant-baseline="central">{name}</text>
<text x="{cx}" y="{cy+8}" font-family="Arial" font-size="12" font-weight="bold" fill="#ecc94b" text-anchor="middle" dominant-baseline="central">{stack} BB</text>"""
    
    if is_hero and cards:
        svg += draw_card(cards[0], cx-40, cy-75)
        svg += draw_card(cards[1], cx+4, cy-75)
    return svg

board_w = len(st.session_state.board) * 40 - 4
start_x = 400 - board_w / 2
cards_svg = "".join([draw_card(c, start_x + i*40, 210) for i, c in enumerate(st.session_state.board)])

# 最關鍵的修改：table_svg 內部絕對不留任何換行縮排
table_svg = f"""<div style="width:100%; max-width:800px; margin:auto; background:#121212; border-radius:12px; padding:10px;">
<svg viewBox="0 0 800 500" width="100%" height="100%" style="display:block;">
<ellipse cx="400" cy="250" rx="350" ry="180" fill="#1e4d2b" stroke="#3c2415" stroke-width="12" style="box-shadow:inset 0 0 20px black;"/>
<rect x="340" y="165" width="120" height="28" rx="14" fill="rgba(0,0,0,0.6)"/>
<text x="400" y="179" font-family="Arial" font-size="14" font-weight="bold" fill="#f6e05e" text-anchor="middle" dominant-baseline="central">Pot: {st.session_state.pot:.1f} BB</text>
{cards_svg}
{draw_player(160, 110, "TAG", "HJ", st.session_state.bots[0].stack, st.session_state.bots[0].bet)}
{draw_player(400, 70,  "LAG", "CO", st.session_state.bots[1].stack, st.session_state.bots[1].bet)}
{draw_player(640, 110, "Fish", "BTN", st.session_state.bots[2].stack, st.session_state.bots[2].bet)}
{draw_player(680, 340, "Nit", "SB", st.session_state.bots[3].stack, st.session_state.bots[3].bet)}
{draw_player(120, 340, "Maniac", "BB", st.session_state.bots[4].stack, st.session_state.bots[4].bet)}
{draw_player(400, 420, "HERO", st.session_state.hero_pos, st.session_state.hero_stack, st.session_state.hero_bet, True, st.session_state.hero_cards)}
</svg>
</div>"""

st.markdown(table_svg, unsafe_allow_html=True)

# ==========================================
# 5. 手機友善操控面板
# ==========================================
st.write("---")
hand_cat = get_hand_category(st.session_state.hero_cards[0], st.session_state.hero_cards[1])
texture = evaluate_board_texture(st.session_state.board)

if st.session_state.stage == 'PREFLOP':
    st.subheader(f"🎮 翻前行動 (位置: {st.session_state.hero_pos})")
    action = st.radio("你的決策:", ['Fold', 'Call (1.0 BB)', 'Open Raise'])
    
    raise_val = 2.5
    if action == 'Open Raise':
        raise_val = st.slider("加注尺寸 (BB):", 2.0, 10.0, 2.5, 0.5)

    if st.button("確認行動", type="primary", use_container_width=True):
        st.session_state.reports.append(analyze_preflop_gto(hand_cat, st.session_state.hero_pos))
        
        if action == 'Fold':
            st.session_state.stage = 'SHOWDOWN'
        else:
            cost = 1.0 if 'Call' in action else raise_val
            st.session_state.hero_stack -= cost
            st.session_state.pot += cost
            st.session_state.hero_bet = cost
            st.session_state.board = [st.session_state.deck.pop(), st.session_state.deck.pop(), st.session_state.deck.pop()]
            st.session_state.stage = 'FLOP'
        st.rerun()

elif st.session_state.stage == 'FLOP':
    st.subheader(f"🎮 翻牌圈 (牌面: {texture})")
    action = st.radio("你的決策:", ['Check', 'C-bet 下注'])
    
    cbet_val = 0.0
    if action == 'C-bet 下注':
        max_bet = min(st.session_state.hero_stack, st.session_state.pot * 2.5)
        cbet_val = st.slider("選擇 C-bet 尺寸 (左右滑動):", 1.0, float(max_bet), round(st.session_state.pot * 0.33, 1), 0.5)
        st.caption(f"⚡ 目前尺寸約為底池的 **{(cbet_val/st.session_state.pot)*100:.0f}%**")

    if st.button("確認行動並看 GTO 分析", type="primary", use_container_width=True):
        if action == 'C-bet 下注':
            st.session_state.hero_stack -= cbet_val
            st.session_state.pot += cbet_val
            st.session_state.hero_bet = cbet_val
            st.session_state.reports.extend(analyze_postflop_gto(cbet_val, st.session_state.pot - cbet_val, texture))
        else:
            st.session_state.hero_bet = 0.0
            st.session_state.reports.append("🛡️ **Check 評估**: 控制底池符合 GTO。無堅果優勢時，過牌是標準防守。")
            
        st.session_state.stage = 'SHOWDOWN'
        st.rerun()

elif st.session_state.stage == 'SHOWDOWN':
    st.success("✅ **牌局分析報告**")
    for r in st.session_state.reports:
        st.markdown(r)
    
    if st.button("下一手牌", type="primary", use_container_width=True):
        st.session_state.hero_stack += st.session_state.pot
        start_hand()
        st.rerun()
