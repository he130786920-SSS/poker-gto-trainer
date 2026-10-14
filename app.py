import streamlit as st
import random
from collections import Counter
import itertools

# ==========================================
# 1. 撲克底層算法與牌力評估 (Pure Python)
# ==========================================
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

def create_deck():
    return [r + s for r in RANKS for s in SUITS]

def get_hand_category(cards):
    if not cards or len(cards) < 2: return "Unknown"
    r1, s1 = cards[0][:-1], cards[0][-1]
    r2, s2 = cards[1][:-1], cards[1][-1]
    v1, v2 = RANK_VALUES[r1], RANK_VALUES[r2]
    high, low = (r1, r2) if v1 >= v2 else (r2, r1)
    suited = 's' if s1 == s2 else 'o'
    return high + low + ('' if high == low else suited)

def evaluate_5card(hand):
    ranks = sorted([RANK_VALUES[c[:-1]] for c in hand], reverse=True)
    suits = [c[-1] for c in hand]
    is_flush = len(set(suits)) == 1
    
    unique_ranks = sorted(list(set(ranks)), reverse=True)
    is_straight = False
    straight_high = 0
    if len(unique_ranks) >= 5:
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i+4] == 4:
                is_straight = True
                straight_high = unique_ranks[i]
                break
        if not is_straight and set([14, 2, 3, 4, 5]).issubset(set(ranks)):
            is_straight = True
            straight_high = 5
            
    counts = Counter(ranks)
    count_vals = sorted(counts.values(), reverse=True)
    order_ranks = sorted(counts.keys(), key=lambda r: (counts[r], r), reverse=True)
    
    if is_straight and is_flush: return (8, straight_high)
    if count_vals == [4, 1]: return (7, order_ranks)
    if count_vals == [3, 2]: return (6, order_ranks)
    if is_flush: return (5, ranks)
    if is_straight: return (4, straight_high)
    if count_vals == [3, 1, 1]: return (3, order_ranks)
    if count_vals == [2, 2, 1]: return (2, order_ranks)
    if count_vals == [2, 1, 1, 1]: return (1, order_ranks)
    return (0, ranks)

def get_hand_score(cards):
    best = (-1, [])
    for comb in itertools.combinations(cards, 5):
        s = evaluate_5card(comb)
        if s > best: best = s
    return best

def evaluate_board_texture(board):
    if len(board) < 3: return "翻前階段"
    ranks = [RANK_VALUES[c[:-1]] for c in board]
    suits = [c[-1] for c in board]
    if len(set(ranks[:3])) < 3: return "對子面 (Paired)"
    if len(set(suits[:3])) == 1: return "單色面 (Monotone)"
    if max(ranks[:3]) - min(ranks[:3]) <= 4: return "濕滑動態面 (Wet)"
    return "乾燥靜態面 (Dry)"

# ==========================================
# 2. 嚴謹 GTO 範圍庫 (分位置、分情境)
# ==========================================
GTO_RANGES = {
    'UTG': {'pairs': 7, 'suited_ax': 10, 'broadway': ['AKo', 'AQo', 'AJo', 'KQo'], 'connectors': ['JTs', 'T9s', '98s']},
    'HJ':  {'pairs': 5, 'suited_ax': 8,  'broadway': ['AKo', 'AQo', 'AJo', 'ATo', 'KQo', 'KJo'], 'connectors': ['JTs', 'T9s', '98s', '87s']},
    'CO':  {'pairs': 2, 'suited_ax': 4,  'broadway': ['AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'KQo', 'KJo', 'QJo'], 'connectors': ['JTs', 'T9s', '98s', '87s', '76s', '65s']},
    'BTN': {'pairs': 2, 'suited_ax': 2,  'broadway': ['AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'A7o', 'A5o', 'KQo', 'KJo', 'QJo', 'JTo'], 'connectors': ['T9s', '98s', '87s', '76s', '65s', '54s', 'J8s', 'T8s']},
    'SB':  {'pairs': 2, 'suited_ax': 2,  'broadway': ['AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'KQo', 'KJo', 'QJo'], 'connectors': ['T9s', '98s', '87s', '76s']}
}

def analyze_gto_preflop(hand_cat, pos, to_call, is_open):
    r1, r2 = hand_cat[0], hand_cat[1]
    is_pair = (r1 == r2)
    is_suited = hand_cat.endswith('s')
    
    # 大盲位 (BB) 專用特殊邏輯
    if pos == 'BB':
        if to_call == 0:
            return "✅ **GTO 大盲免費選擇權 (Option)**: 所有玩家皆平跟或無加注，你有權利免費看翻牌。若拿極強牌（QQ+, AK）應發起 Iso-Raise 加注驅逐弱牌；邊緣牌直接 Check 免費進攻！"
        else:
            pot_odds_req = (to_call / (to_call + 3.5)) * 100
            if is_pair or is_suited or (r1 in ['A', 'K', 'Q', 'J'] and r2 in ['A', 'K', 'Q', 'J', 'T', '9']):
                return f"✅ **GTO 大盲防守標準**: 你翻前已投入 1BB，面對 Open 只需補 {to_call:.1f}BB，所需勝率僅約 {pot_odds_req:.0f}%。{hand_cat} 擁有足夠勝率與隱含賠率，跟注是高 EV 決定！"
            return f"⚠️ **GTO 大盲防守標準**: 面對加注，{hand_cat} 牌力過於邊緣，即便底池賠率優秀，翻後極易遭受逆向隱含賠率打擊，應適度棄牌。"

    # 非大盲位置判斷
    if is_open:
        std = GTO_RANGES.get(pos, GTO_RANGES['UTG'])
        if is_pair and RANK_VALUES[r1] >= std['pairs']: return f"✅ **GTO 建議**: {pos} 位置 100% Open Raise。"
        if is_suited and r1 == 'A' and RANK_VALUES[r2] >= std['suited_ax']: return f"✅ **GTO 建議**: {pos} 位置 100% Open Raise (同花 A 具備強阻擋牌與 Nuts 同花潛力)。"
        if hand_cat in std['broadway'] or hand_cat in std['connectors']: return f"✅ **GTO 建議**: {pos} 位置標準 Open Raise 範圍。"
        return f"❌ **GTO 建議**: 在 {pos} 位置此手牌為負期望值 (-EV)，翻前應直接 Fold。"
    else:
        if hand_cat in ['AA', 'KK', 'QQ', 'AKs', 'AKo']: return "🔥 **GTO 建議**: 核心價值 3-Bet / 4-Bet 範圍，建立大底池。"
        if is_pair or (is_suited and r1 in ['A', 'K', 'Q']): return "🛡️ **GTO 建議**: 翻前跟注防守 (Call) 或混合部分 3-Bet 詐唬阻擋。"
        return "❌ **GTO 建議**: 面對身前開牌加注，該手牌勝率不足，應標準棄牌。"

def analyze_gto_postflop(street_name, custom_bet, pot, board_texture):
    if custom_bet == 0:
        return f"🛡️ **{street_name} 評估**: 過牌 (Check) 控制底池。在缺少堅果優勢或攤牌價值中等時，符合 GTO 防守頻率。"
    pct = (custom_bet / pot) * 100 if pot > 0 else 0
    if pct <= 40:
        return f"🎯 **{street_name} C-bet ({pct:.0f}% 底池)**: 小尺寸下注。乾燥面具有『整體範圍優勢』時的高頻剝削尺寸。"
    elif pct <= 85:
        return f"🎯 **{street_name} C-bet ({pct:.0f}% 底池)**: 標準大尺寸。在動態或濕滑面上能剝奪對手追花追順的隱含賠率，並提供價值保護。"
    else:
        return f"🚀 **{street_name} C-bet ({pct:.0f}% 超池/All-in)**: 極化尺寸 (Polarized)。GTO 僅在具備絕對堅果優勢或極致詐唬時使用。"

# ==========================================
# 3. 遊戲流程控管 (支援五條街與動態輪轉)
# ==========================================
POS_LIST = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

def start_new_hand():
    st.session_state.deck = create_deck()
    random.shuffle(st.session_state.deck)
    st.session_state.board = []
    st.session_state.street = 'PREFLOP' # PREFLOP -> FLOP -> TURN -> RIVER -> SHOWDOWN
    st.session_state.street_idx = 0     # 0:Pre, 1:Flop, 2:Turn, 3:River, 4:Showdown
    st.session_state.logs = []
    st.session_state.gto_reports = []
    st.session_state.btn_idx = (st.session_state.get('btn_idx', 0) + 1) % 6
    st.session_state.hero_pos = POS_LIST[st.session_state.btn_idx]
    
    # 建立 6 名玩家 (含 Hero)，依順序發牌
    st.session_state.players = []
    for p in POS_LIST:
        is_h = (p == st.session_state.hero_pos)
        stk = st.session_state.hero_stack if is_h else st.session_state.get(f'bot_stack_{p}', 100.0)
        cards = [st.session_state.deck.pop(), st.session_state.deck.pop()]
        st.session_state.players.append({
            'pos': p,
            'name': 'HERO (你)' if is_h else f"Bot_{p}",
            'is_hero': is_h,
            'stack': stk,
            'bet': 0.0,
            'cards': cards,
            'active': True
        })
        
    # 強制下盲注 (SB 0.5, BB 1.0)
    for pl in st.session_state.players:
        if pl['pos'] == 'SB':
            pl['bet'] = 0.5
            pl['stack'] -= 0.5
        elif pl['pos'] == 'BB':
            pl['bet'] = 1.0
            pl['stack'] -= 1.0
            
    st.session_state.pot = 1.5
    st.session_state.current_bet = 1.0
    st.session_state.turn_idx = 0 # 翻前從 UTG 開始 (索引 0)
    process_bots_turn()

def process_bots_turn():
    while st.session_state.street != 'SHOWDOWN':
        curr_p = st.session_state.players[st.session_state.turn_idx]
        
        # 輪到 Hero 且 Hero 尚未棄牌，中斷等待用戶操作
        if curr_p['is_hero'] and curr_p['active']:
            break
            
        # 機器人行動邏輯 (具備 GTO 加注、跟注與棄牌)
        if curr_p['active']:
            to_call = st.session_state.current_bet - curr_p['bet']
            roll = random.random()
            pos = curr_p['pos']
            
            if st.session_state.street == 'PREFLOP':
                if st.session_state.current_bet == 1.0: # 無人加注
                    if roll < (0.42 if pos in ['BTN', 'CO'] else 0.18):
                        # 正常 GTO Open Raise
                        raise_amt = 2.5
                        curr_p['stack'] -= (raise_amt - curr_p['bet'])
                        curr_p['bet'] = raise_amt
                        st.session_state.pot += (raise_amt - curr_p['bet'])
                        st.session_state.current_bet = raise_amt
                        st.session_state.logs.append(f"🤖 {curr_p['pos']} 發起 Open Raise 到 {raise_amt:.1f} BB")
                    else:
                        if pos == 'BB':
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 免費 Check 過牌")
                        else:
                            curr_p['active'] = False
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌 (Fold)")
                else: # 面對加注
                    if roll < 0.18: # 3-bet
                        raise_amt = st.session_state.current_bet * 3
                        curr_p['stack'] -= (raise_amt - curr_p['bet'])
                        curr_p['bet'] = raise_amt
                        st.session_state.pot += (raise_amt - curr_p['bet'])
                        st.session_state.current_bet = raise_amt
                        st.session_state.logs.append(f"🔥 🤖 {curr_p['pos']} 3-Bet 加注至 {raise_amt:.1f} BB")
                    elif roll < (0.50 if pos == 'BB' else 0.28): # BB 寬防守跟注
                        curr_p['stack'] -= to_call
                        curr_p['bet'] += to_call
                        st.session_state.pot += to_call
                        st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                    else:
                        curr_p['active'] = False
                        st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌 (Fold)")
            else: # 翻後街道 (Flop, Turn, River)
                if to_call == 0:
                    if roll < 0.35: # 主動 C-bet
                        bet_amt = round(st.session_state.pot * 0.45, 1)
                        bet_amt = min(bet_amt, curr_p['stack'])
                        curr_p['stack'] -= bet_amt
                        curr_p['bet'] = bet_amt
                        st.session_state.pot += bet_amt
                        st.session_state.current_bet = bet_amt
                        st.session_state.logs.append(f"🎯 🤖 {curr_p['pos']} 下注 {bet_amt:.1f} BB")
                    else:
                        st.session_state.logs.append(f"🤖 {curr_p['pos']} 過牌 (Check)")
                else:
                    if roll < 0.40:
                        curr_p['stack'] -= to_call
                        curr_p['bet'] += to_call
                        st.session_state.pot += to_call
                        st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                    else:
                        curr_p['active'] = False
                        st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌 (Fold)")
                        
        # 推進指針
        st.session_state.turn_idx = (st.session_state.turn_idx + 1) % 6
        
        # 檢查活著的玩家是否都已平注 (Round Over)
        actives = [p for p in st.session_state.players if p['active']]
        if len(actives) == 1:
            st.session_state.street = 'SHOWDOWN'
            st.session_state.logs.append(f"🏆 其餘玩家皆已棄牌，{actives[0]['name']} 獲勝！")
            break
            
        all_settled = all(p['bet'] == st.session_state.current_bet for p in actives)
        if all_settled and st.session_state.turn_idx == (0 if st.session_state.street == 'PREFLOP' else 4): # SB/BB 順序後結束
            next_street()

def next_street():
    for p in st.session_state.players: p['bet'] = 0.0
    st.session_state.current_bet = 0.0
    st.session_state.turn_idx = 4 # 翻後由 SB (索引 4) 先動
    
    if st.session_state.street == 'PREFLOP':
        st.session_state.street = 'FLOP'
        st.session_state.board.extend([st.session_state.deck.pop(), st.session_state.deck.pop(), st.session_state.deck.pop()])
        st.session_state.logs.append("--- 🎴 發出翻牌圈 (Flop) ---")
    elif st.session_state.street == 'FLOP':
        st.session_state.street = 'TURN'
        st.session_state.board.append(st.session_state.deck.pop())
        st.session_state.logs.append("--- 🎴 發出轉牌圈 (Turn) ---")
    elif st.session_state.street == 'TURN':
        st.session_state.street = 'RIVER'
        st.session_state.board.append(st.session_state.deck.pop())
        st.session_state.logs.append("--- 🎴 發出河牌圈 (River) ---")
    elif st.session_state.street == 'RIVER':
        st.session_state.street = 'SHOWDOWN'
        st.session_state.logs.append("--- 🏁 進入攤牌階段 (Showdown) ---")

# ==========================================
# 4. Streamlit 介面與高解析 SVG 繪製 (去縮排防跑版)
# ==========================================
st.set_page_config(page_title="GTO 競技對決模擬器", layout="centered")

if 'hero_stack' not in st.session_state:
    st.session_state.hero_stack = 100.0
    start_new_hand()

hero_player = next(p for p in st.session_state.players if p['is_hero'])

# SVG 卡牌與座位渲染 (攤牌時全部翻開)
def draw_card(card, x, y):
    r, s = card[:-1], card[-1]
    color = "#e53e3e" if s in ['♥', '♦'] else "#1a202c"
    return f"""<g transform="translate({x}, {y})"><rect x="0" y="0" width="34" height="48" rx="4" fill="white" stroke="#718096" stroke-width="1"/><text x="17" y="24" font-family="Arial" font-size="18" font-weight="bold" fill="{color}" text-anchor="middle" dominant-baseline="central">{r}{s}</text></g>"""

def draw_card_back(x, y):
    return f"""<g transform="translate({x}, {y})"><rect x="0" y="0" width="34" height="48" rx="4" fill="#2b6cb0" stroke="#cbd5e0" stroke-width="1.5"/><rect x="4" y="4" width="26" height="40" rx="2" fill="#2c5282"/></g>"""

def draw_player_node(cx, cy, p):
    is_h = p['is_hero']
    dim = "opacity: 0.35;" if not p['active'] else "opacity: 1.0;"
    border = "#ecc94b" if is_h else "#4a5568"
    bg = "#2d3748" if is_h else "#1a202c"
    
    svg = f'<g style="{dim}">'
    # 籌碼投出顯示
    if p['bet'] > 0:
        bx = cx + (400 - cx) * 0.28
        by = cy + (250 - cy) * 0.28
        svg += f"""<rect x="{bx-24}" y="{by-11}" width="48" height="22" rx="11" fill="rgba(0,0,0,0.8)"/><text x="{bx}" y="{by}" font-family="Arial" font-size="11" font-weight="bold" fill="#68d391" text-anchor="middle" dominant-baseline="central">{p['bet']:.1f}</text>"""
    
    # 玩家名牌框
    svg += f"""<rect x="{cx-45}" y="{cy-18}" width="90" height="36" rx="6" fill="{bg}" stroke="{border}" stroke-width="2"/><rect x="{cx-42}" y="{cy-14}" width="24" height="14" rx="3" fill="{'#ecc94b' if is_h else '#e2e8f0'}"/><text x="{cx-30}" y="{cy-7}" font-family="Arial" font-size="9" font-weight="bold" fill="black" text-anchor="middle" dominant-baseline="central">{p['pos']}</text><text x="{cx-12}" y="{cy-7}" font-family="Arial" font-size="11" font-weight="bold" fill="white" dominant-baseline="central">{p['name'][:7]}</text><text x="{cx}" y="{cy+8}" font-family="Arial" font-size="12" font-weight="bold" fill="#ecc94b" text-anchor="middle" dominant-baseline="central">{p['stack']:.1f} BB</text>"""
    
    # 手牌顯示：Hero 永遠看得到；機器人平時看牌背，Showdown 時未棄牌則 100% 翻開秀牌！
    show_cards = is_h or (st.session_state.street == 'SHOWDOWN' and p['active'])
    if p['active']:
        if show_cards:
            svg += draw_card(p['cards'][0], cx-38, cy-70)
            svg += draw_card(p['cards'][1], cx+4, cy-70)
        else:
            svg += draw_card_back(cx-38, cy-70)
            svg += draw_card_back(cx+4, cy-70)
    svg += '</g>'
    return svg

# 公共牌 SVG
board_svg = "".join([draw_card(c, 400 - (len(st.session_state.board)*38)/2 + i*38, 215) for i, c in enumerate(st.session_state.board)])

# 固定座標分配 (橢圓 6 人桌)
coords = [(160, 110), (400, 70), (640, 110), (680, 340), (400, 430), (120, 340)]
pos_map = {p['pos']: coords[i] for i, p in enumerate(st.session_state.players)}
players_svg = "".join([draw_player_node(pos_map[p['pos']][0], pos_map[p['pos']][1], p) for p in st.session_state.players])

table_svg = f"""<div style="width:100%; max-width:800px; margin:auto; background:#121212; border-radius:12px; padding:10px;">
<svg viewBox="0 0 800 500" width="100%" height="100%" style="display:block;">
<ellipse cx="400" cy="250" rx="355" ry="185" fill="#1e4d2b" stroke="#3c2415" stroke-width="14"/>
<rect x="330" y="165" width="140" height="30" rx="15" fill="rgba(0,0,0,0.65)"/>
<text x="400" y="180" font-family="Arial" font-size="14" font-weight="bold" fill="#f6e05e" text-anchor="middle" dominant-baseline="central">Pot: {st.session_state.pot:.1f} BB</text>
{board_svg}
{players_svg}
</svg>
</div>"""
st.markdown(table_svg, unsafe_allow_html=True)

# ==========================================
# 5. 操作面板 (包含無級距 All-in 滑桿與 BB 防守修正)
# ==========================================
if st.session_state.street != 'SHOWDOWN' and hero_player['active']:
    to_call = st.session_state.current_bet - hero_player['bet']
    c_log, c_action = st.columns([1, 1.2])
    
    with c_log:
        st.markdown("**📜 牌局即時動態**")
        st.caption("<br>".join(st.session_state.logs[-4:]), unsafe_allow_html=True)

    with c_action:
        st.markdown(f"**🎮 輪到你行動** (階段: **{st.session_state.street}** | 位置: **{hero_player['pos']}**)")
        
        # 決定行動選項 (大盲未被加注時絕無 Fold！)
        options = []
        if to_call > 0:
            options.append('Fold')
            options.append(f"Call ({to_call:.1f} BB)")
        else:
            options.append('Check')
        options.append('Bet / Raise')
        
        act = st.radio("你的決策:", options, horizontal=True, label_visibility="collapsed")
        
        # 滑桿設置：Min-raise 到 All-in
        min_r = max(st.session_state.current_bet * 2, 2.0 if st.session_state.street == 'PREFLOP' else 1.0)
        max_r = float(hero_player['stack'] + hero_player['bet'])
        if min_r >= max_r: min_r = max_r
        
        chosen_val = min_r
        if act == 'Bet / Raise':
            if min_r < max_r:
                chosen_val = st.slider("下注/加注尺寸 (拖曳到底為 All-in):", float(min_r), float(max_r), float(min_r), 0.5)
            else:
                st.warning("⚠️ 籌碼已達極限，只能 All-in！")
                chosen_val = max_r
                
        if st.button("確認行動", type="primary", use_container_width=True):
            hand_cat = get_hand_category(hero_player['cards'])
            texture = evaluate_board_texture(st.session_state.board)
            
            # GTO 覆盤收集
            if st.session_state.street == 'PREFLOP':
                st.session_state.gto_reports.append(analyze_gto_preflop(hand_cat, hero_player['pos'], to_call, is_open=(act == 'Bet / Raise')))
            else:
                bet_amt = chosen_val if act == 'Bet / Raise' else 0
                st.session_state.gto_reports.append(analyze_gto_postflop(st.session_state.street, bet_amt, st.session_state.pot, texture))

            # 執行 Hero 籌碼扣除
            if act == 'Fold':
                hero_player['active'] = False
                st.session_state.logs.append(f"👤 HERO ({hero_player['pos']}) 選擇 棄牌")
            elif 'Call' in act or 'Check' in act:
                hero_player['stack'] -= to_call
                hero_player['bet'] += to_call
                st.session_state.pot += to_call
                st.session_state.logs.append(f"👤 HERO ({hero_player['pos']}) {'過牌' if to_call == 0 else f'跟注 {to_call:.1f} BB'}")
            else:
                diff = chosen_val - hero_player['bet']
                hero_player['stack'] -= diff
                hero_player['bet'] = chosen_val
                st.session_state.pot += diff
                st.session_state.current_bet = chosen_val
                st.session_state.logs.append(f"🔥 👤 HERO ({hero_player['pos']}) 加注至 {chosen_val:.1f} BB")
                
            # 推進下一步
            st.session_state.turn_idx = (st.session_state.turn_idx + 1) % 6
            process_bots_turn()
            st.rerun()

elif st.session_state.street == 'SHOWDOWN' or not hero_player['active']:
    st.subheader("🏁 牌局結算 (已攤開對手底牌)")
    
    # 計算獲勝者
    actives = [p for p in st.session_state.players if p['active']]
    if len(actives) > 1 and len(st.session_state.board) == 5:
        winner = max(actives, key=lambda p: get_hand_score(p['cards'] + st.session_state.board))
        st.success(f"🏆 勝者是 **{winner['name']}** ({winner['pos']})！贏得底池 **{st.session_state.pot:.1f} BB**")
        winner['stack'] += st.session_state.pot
    elif len(actives) == 1:
        st.success(f"🏆 **{actives[0]['name']}** 獲勝！收獲底池 **{st.session_state.pot:.1f} BB**")
        actives[0]['stack'] += st.session_state.pot
        
    st.info("📜 **本局 GTO 教練覆盤與建議**")
    for r in st.session_state.gto_reports:
        st.markdown(r)
        
    # 保存籌碼至下一輪
    st.session_state.hero_stack = hero_player['stack']
    for p in st.session_state.players:
        if not p['is_hero']: st.session_state[f'bot_stack_{p["pos"]}'] = p['stack']
        
    if st.button("發下一手牌 (Next Hand)", type="primary", use_container_width=True):
        start_new_hand()
        st.rerun()
