import streamlit as st
import random
import itertools
import base64
from collections import Counter

# ==========================================
# 1. 撲克底層算法與牌力評估
# ==========================================
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

def create_deck(): return [r + s for r in RANKS for s in SUITS]

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
    is_straight, straight_high = False, 0
    if len(unique_ranks) >= 5:
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i+4] == 4:
                is_straight = True; straight_high = unique_ranks[i]; break
        if not is_straight and set([14, 2, 3, 4, 5]).issubset(set(ranks)):
            is_straight = True; straight_high = 5
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
    if len(board) < 3: return "翻前"
    ranks = [RANK_VALUES[c[:-1]] for c in board]
    suits = [c[-1] for c in board]
    if len(set(ranks[:3])) < 3: return "對子面 (Paired)"
    if len(set(suits[:3])) == 1: return "單色面 (Monotone)"
    if max(ranks[:3]) - min(ranks[:3]) <= 4: return "濕滑動態面 (Wet)"
    return "乾燥靜態面 (Dry)"

def classify_hero_postflop_hand(hero_cards, board):
    if len(board) < 3 or not hero_cards: return "未知"
    score, _ = get_hand_score(hero_cards + board)
    board_ranks = sorted([RANK_VALUES[c[:-1]] for c in board], reverse=True)
    h_ranks = sorted([RANK_VALUES[c[:-1]] for c in hero_cards], reverse=True)
    h_suits = [c[-1] for c in hero_cards]
    b_suits = [c[-1] for c in board]
    
    if score >= 3: return "超強成牌 (兩對以上/三條/順花堅果)"
    if score == 2: return "兩對 (Two Pair)"
    if h_ranks[0] == h_ranks[1] and h_ranks[0] > board_ranks[0]: return "超對 (Overpair)"
    if board_ranks[0] in h_ranks:
        kicker = h_ranks[1] if h_ranks[0] == board_ranks[0] else h_ranks[0]
        return "頂對好踢腳 (TPTK)" if kicker >= 10 else "頂對弱踢腳 (TPWK)"
    if len(board_ranks) > 1 and board_ranks[1] in h_ranks: return "中對 (Middle Pair)"
    if board_ranks[-1] in h_ranks: return "底對 (Bottom Pair)"
    
    suit_counts = Counter(h_suits + b_suits)
    for s, cnt in suit_counts.items():
        if cnt == 4 and (s in h_suits): return "同花聽牌 (Flush Draw)"
    return "高牌空氣 (Air / Overcards)"

# ==========================================
# 2. GTO 三動作頻率分解與總結引擎
# ==========================================
def calculate_preflop_frequencies(hand_cat, pos, to_call):
    r1, r2 = hand_cat[0], hand_cat[1]
    is_pair = (r1 == r2)
    is_suited = hand_cat.endswith('s')
    v1, v2 = RANK_VALUES[r1], RANK_VALUES[r2]
    
    # 大盲免費過牌情境
    if pos == 'BB' and to_call == 0:
        if hand_cat in ['AA', 'KK', 'QQ', 'AKs']:
            return {'Fold': 0, 'Check_Call': 25, 'Raise': 75, 'Raise_Size': '3.5BB (Iso-Raise)'}
        elif is_pair or is_suited or v1 >= 10:
            return {'Fold': 0, 'Check_Call': 85, 'Raise': 15, 'Raise_Size': '3.0BB'}
        return {'Fold': 0, 'Check_Call': 100, 'Raise': 0, 'Raise_Size': '-'}
    
    # 翻前無人加注 (Open 情境)
    if to_call <= 1.0:
        if hand_cat in ['AA', 'KK', 'QQ', 'JJ', 'AKs', 'AQs', 'AKo']:
            return {'Fold': 0, 'Check_Call': 0, 'Raise': 100, 'Raise_Size': '2.5BB'}
        if pos in ['BTN', 'CO', 'SB']:
            if is_pair or (is_suited and v1 >= 8) or (v1 >= 10 and v2 >= 9):
                return {'Fold': 15, 'Check_Call': 0, 'Raise': 85, 'Raise_Size': '2.5BB'}
            if is_suited:
                return {'Fold': 50, 'Check_Call': 0, 'Raise': 50, 'Raise_Size': '2.5BB'}
            return {'Fold': 80, 'Check_Call': 0, 'Raise': 20, 'Raise_Size': '2.5BB'}
        else: # 早位 UTG / HJ
            if is_pair and v1 >= 7: return {'Fold': 10, 'Check_Call': 0, 'Raise': 90, 'Raise_Size': '2.5BB'}
            if is_suited and v1 == 14 and v2 >= 10: return {'Fold': 0, 'Check_Call': 0, 'Raise': 100, 'Raise_Size': '2.5BB'}
            return {'Fold': 95, 'Check_Call': 0, 'Raise': 5, 'Raise_Size': '2.5BB'}
            
    # 面對加注 / 3-Bet
    else:
        if hand_cat in ['AA', 'KK']: return {'Fold': 0, 'Check_Call': 15, 'Raise': 85, 'Raise_Size': '3-Bet / 4-Bet (3x)'}
        if hand_cat in ['QQ', 'JJ', 'AKs', 'AKo']: return {'Fold': 0, 'Check_Call': 55, 'Raise': 45, 'Raise_Size': '3-Bet (3x)'}
        if pos == 'BB': # 大盲賠率優勢防守
            if is_pair or is_suited or (v1 >= 10 and v2 >= 8):
                return {'Fold': 30, 'Check_Call': 65, 'Raise': 5, 'Raise_Size': '3-Bet'}
            return {'Fold': 75, 'Check_Call': 25, 'Raise': 0, 'Raise_Size': '-'}
        else:
            if is_pair or (is_suited and v1 >= 10):
                return {'Fold': 55, 'Check_Call': 40, 'Raise': 5, 'Raise_Size': '3-Bet'}
            return {'Fold': 90, 'Check_Call': 8, 'Raise': 2, 'Raise_Size': '3-Bet'}

def calculate_postflop_frequencies(hand_type, texture, to_call, is_multiway):
    # 多人底池下注頻率全面下修
    mw_factor = 0.55 if is_multiway else 1.0
    
    if to_call == 0:
        if "超強成牌" in hand_type or "超對" in hand_type:
            if "Wet" in texture:
                return {'Check': 20, 'Bet_33': round(25 * mw_factor), 'Bet_75': round(50 * mw_factor), 'Overbet': 5}
            return {'Check': 30, 'Bet_33': round(50 * mw_factor), 'Bet_75': round(18 * mw_factor), 'Overbet': 2}
        elif "頂對好踢腳" in hand_type:
            if "Wet" in texture:
                return {'Check': 25, 'Bet_33': round(30 * mw_factor), 'Bet_75': round(42 * mw_factor), 'Overbet': 3}
            return {'Check': 35, 'Bet_33': round(55 * mw_factor), 'Bet_75': round(10 * mw_factor), 'Overbet': 0}
        elif "頂對弱踢腳" in hand_type or "中對" in hand_type or "底對" in hand_type:
            return {'Check': 65, 'Bet_33': round(30 * mw_factor), 'Bet_75': round(5 * mw_factor), 'Overbet': 0}
        elif "同花聽牌" in hand_type:
            return {'Check': 40, 'Bet_33': round(35 * mw_factor), 'Bet_75': round(22 * mw_factor), 'Overbet': 3}
        else: # 空氣牌
            if "Dry" in texture and not is_multiway:
                return {'Check': 50, 'Bet_33': 45, 'Bet_75': 5, 'Overbet': 0}
            return {'Check': 85, 'Bet_33': round(12 * mw_factor), 'Bet_75': round(3 * mw_factor), 'Overbet': 0}
    else: # 面對下注 (防守頻率)
        if "超強成牌" in hand_type:
            return {'Fold': 0, 'Call': 60, 'Raise': 40}
        elif "頂對好踢腳" in hand_type or "超對" in hand_type:
            return {'Fold': 5, 'Call': 80, 'Raise': 15}
        elif "中對" in hand_type or "頂對弱踢腳" in hand_type or "同花聽牌" in hand_type:
            return {'Fold': 35, 'Call': 60, 'Raise': 5}
        else:
            return {'Fold': 85, 'Call': 12, 'Raise': 3}

# ==========================================
# 3. 遊戲狀態與 AI 迴圈
# ==========================================
POS_LIST = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

def start_new_hand():
    st.session_state.deck = create_deck()
    random.shuffle(st.session_state.deck)
    st.session_state.board = []
    st.session_state.street = 'PREFLOP'
    st.session_state.logs = []
    st.session_state.hand_history = []
    st.session_state.last_actor = None
    st.session_state.btn_idx = (st.session_state.get('btn_idx', 0) + 1) % 6
    st.session_state.hero_pos = POS_LIST[st.session_state.btn_idx]
    
    if st.session_state.get('hero_stack', 100.0) <= 0: st.session_state.hero_stack = 100.0
        
    st.session_state.players = []
    for p in POS_LIST:
        is_h = (p == st.session_state.hero_pos)
        if is_h: stk = st.session_state.hero_stack
        else:
            bot_key = f'bot_stack_{p}'
            if bot_key not in st.session_state or st.session_state[bot_key] <= 0: st.session_state[bot_key] = 100.0
            stk = st.session_state[bot_key]
            
        st.session_state.players.append({
            'pos': p, 'name': 'HERO' if is_h else f"Bot_{p}", 'is_hero': is_h,
            'stack': float(stk), 'bet': 0.0, 'active': True, 'acted_this_street': False,
            'cards': [st.session_state.deck.pop(), st.session_state.deck.pop()]
        })
        
    for pl in st.session_state.players:
        if pl['pos'] == 'SB':
            amt = min(0.5, pl['stack']); pl['bet'] = amt; pl['stack'] -= amt
        elif pl['pos'] == 'BB':
            amt = min(1.0, pl['stack']); pl['bet'] = amt; pl['stack'] -= amt
            
    st.session_state.pot = sum(p['bet'] for p in st.session_state.players)
    st.session_state.current_bet = 1.0
    st.session_state.turn_idx = 0
    st.session_state.hero_acted_this_street = False
    process_bots_turn()

def next_street():
    for p in st.session_state.players: p['bet'] = 0.0; p['acted_this_street'] = False
    st.session_state.current_bet = 0.0
    st.session_state.turn_idx = 4
    st.session_state.hero_acted_this_street = False
    
    if st.session_state.street == 'PREFLOP':
        st.session_state.street = 'FLOP'
        st.session_state.board.extend([st.session_state.deck.pop(), st.session_state.deck.pop(), st.session_state.deck.pop()])
        st.session_state.logs.append("--- 🎴 翻牌圈 (Flop) ---")
    elif st.session_state.street == 'FLOP':
        st.session_state.street = 'TURN'
        st.session_state.board.append(st.session_state.deck.pop())
        st.session_state.logs.append("--- 🎴 轉牌圈 (Turn) ---")
    elif st.session_state.street == 'TURN':
        st.session_state.street = 'RIVER'
        st.session_state.board.append(st.session_state.deck.pop())
        st.session_state.logs.append("--- 🎴 河牌圈 (River) ---")
    elif st.session_state.street == 'RIVER':
        st.session_state.street = 'SHOWDOWN'

def process_bots_turn():
    while st.session_state.street != 'SHOWDOWN':
        curr_p = st.session_state.players[st.session_state.turn_idx]
        
        if curr_p['active']:
            to_call = st.session_state.current_bet - curr_p['bet']
            
            if curr_p['is_hero']:
                if curr_p['stack'] > 0.01 and (to_call > 0 or not st.session_state.hero_acted_this_street): break
            
            if curr_p['stack'] <= 0.01: pass
            elif not curr_p['is_hero']:
                to_call = min(to_call, curr_p['stack'])
                max_allow = curr_p['stack'] + curr_p['bet']
                roll = random.random()
                st.session_state.last_actor = curr_p['pos']
                
                if st.session_state.street == 'PREFLOP':
                    if st.session_state.current_bet == 1.0:
                        if roll < 0.22:
                            r_amt = min(2.5, max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} Open 加注至 {r_amt:.1f} BB")
                        elif roll < 0.35:
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 平跟 (Call) 1.0 BB")
                        else:
                            if curr_p['pos'] == 'BB': st.session_state.logs.append(f"🤖 {curr_p['pos']} 過牌 (Check)")
                            else: curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
                    elif st.session_state.current_bet <= 5.0:
                        if roll < 0.12:
                            r_amt = min(st.session_state.current_bet * 3, max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🔥 🤖 {curr_p['pos']} 3-Bet 加注至 {r_amt:.1f} BB!")
                        elif roll < 0.35:
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                        else: curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
                    else:
                        if roll < 0.10:
                            r_amt = min(st.session_state.current_bet * 2.2, max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🚀 🤖 {curr_p['pos']} 4-Bet/All-in 至 {r_amt:.1f} BB!")
                        elif roll < 0.25:
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                        else: curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
                else:
                    if to_call == 0:
                        if roll < 0.35:
                            b_amt = min(round(st.session_state.pot * 0.45, 1), curr_p['stack'])
                            curr_p['stack'] -= b_amt; curr_p['bet'] = b_amt; st.session_state.pot += b_amt
                            st.session_state.current_bet = b_amt
                            st.session_state.logs.append(f"🎯 🤖 {curr_p['pos']} 下注 {b_amt:.1f} BB")
                        else: st.session_state.logs.append(f"🤖 {curr_p['pos']} 過牌 (Check)")
                    else:
                        if roll < 0.08:
                            r_amt = min(to_call * 2.5 + curr_p['bet'], max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🔥 🤖 {curr_p['pos']} 加注至 {r_amt:.1f} BB!")
                        elif roll < 0.45:
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                        else: curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
            curr_p['acted_this_street'] = True
            
        st.session_state.turn_idx = (st.session_state.turn_idx + 1) % 6
        actives = [p for p in st.session_state.players if p['active']]
        if len(actives) == 1: st.session_state.street = 'SHOWDOWN'; break
        if all(p.get('acted_this_street', False) for p in actives) and all((p['bet'] == st.session_state.current_bet or p['stack'] <= 0.01) for p in actives): next_street()

# ==========================================
# 4. 動態 SVG 渲染引擎 (含 CSS 轉場動畫)
# ==========================================
st.set_page_config(page_title="GTO 競技訓練大師", layout="centered")
if 'hero_stack' not in st.session_state: st.session_state.hero_stack = 100.0
if 'street' not in st.session_state: start_new_hand()

def draw_card(c, x, y, animated=True):
    if not c: return ""
    r, s = c[:-1], c[-1]
    col = "#e53e3e" if s in ['♥', '♦'] else "#1a202c"
    anim_class = 'class="card-anim"' if animated else ''
    return f'<g transform="translate({x},{y})" {anim_class}><rect width="36" height="52" rx="4" fill="white" stroke="#718096" stroke-width="1"/><text x="18" y="26" font-family="Arial" font-size="20" font-weight="bold" fill="{col}" text-anchor="middle" dominant-baseline="central">{r}{s}</text></g>'

def draw_back(x, y):
    return f'<g transform="translate({x},{y})"><rect width="36" height="52" rx="4" fill="#2b6cb0" stroke="#cbd5e0" stroke-width="1"/><rect x="4" y="4" width="28" height="44" rx="2" fill="#2c5282"/></g>'

def draw_player(cx, cy, p):
    is_h = p['is_hero']
    dim = "opacity: 0.35;" if not p['active'] else "opacity: 1.0;"
    bg, bd = ("#2d3748", "#ecc94b") if is_h else ("#1a202c", "#4a5568")
    is_acting = (p['pos'] == st.session_state.get('last_actor'))
    seat_class = 'class="active-player-glow"' if is_acting else ''
    
    svg = f'<g style="{dim}">'
    if p['bet'] > 0:
        bx, by = cx + (400 - cx) * 0.28, cy + (250 - cy) * 0.28
        svg += f'<g transform="translate({bx-25},{by-12})" class="chip-pop-anim"><rect width="50" height="24" rx="12" fill="rgba(0,0,0,0.85)" stroke="#68d391" stroke-width="1.5"/><text x="25" y="12" font-family="Arial" font-size="12" font-weight="bold" fill="#68d391" text-anchor="middle" dominant-baseline="central">{p["bet"]:.1f}</text></g>'
    
    svg += f'<g {seat_class}><rect x="{cx-48}" y="{cy-20}" width="96" height="40" rx="6" fill="{bg}" stroke="{bd}" stroke-width="2"/><rect x="{cx-45}" y="{cy-16}" width="26" height="16" rx="3" fill="{"#ecc94b" if is_h else "#e2e8f0"}"/><text x="{cx-32}" y="{cy-8}" font-family="Arial" font-size="10" font-weight="bold" fill="black" text-anchor="middle" dominant-baseline="central">{p["pos"]}</text><text x="{cx-14}" y="{cy-8}" font-family="Arial" font-size="12" font-weight="bold" fill="white" dominant-baseline="central">{p["name"][:7]}</text><text x="{cx}" y="{cy+10}" font-family="Arial" font-size="13" font-weight="bold" fill="#ecc94b" text-anchor="middle" dominant-baseline="central">{p["stack"]:.1f} BB</text></g>'
    
    if p['active']:
        if is_h or st.session_state.street == 'SHOWDOWN':
            svg += draw_card(p['cards'][0], cx-40, cy-78) + draw_card(p['cards'][1], cx+4, cy-78)
        else:
            svg += draw_back(cx-40, cy-78) + draw_back(cx+4, cy-78)
    svg += '</g>'
    return svg

b_svg = "".join([draw_card(c, 400 - (len(st.session_state.board)*40)/2 + i*40, 210) for i, c in enumerate(st.session_state.board)])
pos_map = {'UTG':(160,110), 'HJ':(400,70), 'CO':(640,110), 'BTN':(680,340), 'SB':(400,430), 'BB':(120,340)}
p_svg = "".join([draw_player(pos_map[p['pos']][0], pos_map[p['pos']][1], p) for p in st.session_state.players])

anim_styles = """
<style>
  @keyframes cardDrop { 0% { transform: translateY(-28px); opacity: 0; } 100% { transform: translateY(0); opacity: 1; } }
  @keyframes chipPop { 0% { transform: scale(0.3); opacity: 0; } 60% { transform: scale(1.2); opacity: 1; } 100% { transform: scale(1); opacity: 1; } }
  @keyframes activePulse { 0%, 100% { filter: drop-shadow(0 0 2px #ecc94b); } 50% { filter: drop-shadow(0 0 10px #f6e05e); } }
  .card-anim { animation: cardDrop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
  .chip-pop-anim { animation: chipPop 0.35s ease-out; }
  .active-player-glow { animation: activePulse 1.2s infinite; }
</style>
"""

full_svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="800" height="500">{anim_styles}<rect width="800" height="500" fill="#121212" rx="16"/><ellipse cx="400" cy="250" rx="360" ry="190" fill="#1e4d2b" stroke="#3c2415" stroke-width="16"/><rect x="330" y="165" width="140" height="30" rx="15" fill="rgba(0,0,0,0.7)"/><text x="400" y="180" font-family="Arial" font-size="15" font-weight="bold" fill="#f6e05e" text-anchor="middle" dominant-baseline="central">Pot: {st.session_state.pot:.1f} BB</text>{b_svg}{p_svg}</svg>'
b64_svg = base64.b64encode(full_svg_str.encode('utf-8')).decode('utf-8')
st.markdown(f'<div style="text-align:center;"><img src="data:image/svg+xml;base64,{b64_svg}" style="width:100%; max-width:800px; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);"></div>', unsafe_allow_html=True)

# ==========================================
# 5. 13x13 翻前矩陣
# ==========================================
def get_gto_action(hand, pos):
    rv = lambda r: RANK_VALUES[r]
    if pos == 'UTG':
        if hand[0]==hand[1] and rv(hand[0])>=7: return 'Raise'
        if hand.endswith('s') and hand[0]=='A' and rv(hand[1])>=10: return 'Raise'
        if hand in ['KQs','KJs','QJs','JTs','T9s','AKo','AQo']: return 'Raise'
    elif pos == 'HJ':
        if hand[0]==hand[1] and rv(hand[0])>=5: return 'Raise'
        if hand.endswith('s') and hand[0]=='A' and rv(hand[1])>=8: return 'Raise'
        if hand.endswith('s') and hand[0]=='K' and rv(hand[1])>=10: return 'Raise'
        if hand in ['QJs','QTs','JTs','T9s','98s','87s','AKo','AQo','AJo','KQo']: return 'Raise'
    elif pos == 'CO':
        if hand[0]==hand[1]: return 'Raise'
        if hand.endswith('s') and hand[0]=='A': return 'Raise'
        if hand.endswith('s') and hand[0]=='K' and rv(hand[1])>=8: return 'Raise'
        if hand.endswith('s') and hand[0]=='Q' and rv(hand[1])>=9: return 'Raise'
        if hand.endswith('s') and rv(hand[0])-rv(hand[1])<=2 and rv(hand[1])>=6: return 'Raise'
        if hand in ['AKo','AQo','AJo','ATo','KQo','KJo','QJo']: return 'Raise'
    elif pos in ['BTN', 'SB']:
        if hand[0]==hand[1]: return 'Raise'
        if hand.endswith('s') and hand[0]=='A': return 'Raise'
        if hand.endswith('s') and hand[0]=='K' and rv(hand[1])>=2: return 'Raise'
        if hand.endswith('s') and hand[0]=='Q' and rv(hand[1])>=5: return 'Raise'
        if hand.endswith('s') and hand[0]=='J' and rv(hand[1])>=7: return 'Raise'
        if hand.endswith('s') and rv(hand[0])-rv(hand[1])<=3 and rv(hand[1])>=4: return 'Raise'
        if hand.endswith('o') and hand[0]=='A' and rv(hand[1])>=(2 if pos=='BTN' else 5): return 'Raise'
        if hand.endswith('o') and hand[0]=='K' and rv(hand[1])>=8: return 'Raise'
        if hand.endswith('o') and hand[0]=='Q' and rv(hand[1])>=9: return 'Raise'
        if hand in ['JTo','J9o','T9o']: return 'Raise'
    elif pos == 'BB':
        if hand in ['AA','KK','QQ','JJ','TT','AKs','AQs','AJs','AKo','AQo']: return 'Raise'
        if hand[0]==hand[1] or hand.endswith('s') or (hand.endswith('o') and hand[0] in ['A','K','Q'] and rv(hand[1])>=8) or hand in ['JTo','J9o','T9o']: return 'Call'
    return 'Fold'

def generate_13x13_html(pos, hero_hand):
    ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    rv = lambda r: RANK_VALUES[r]
    html = '<div style="display:grid; grid-template-columns:repeat(13, 1fr); gap:1px; background-color:#121212; padding:3px; border-radius:6px;">'
    for r1 in ranks:
        for r2 in ranks:
            if rv(r1) > rv(r2): hand = r1 + r2 + 's'
            elif rv(r1) < rv(r2): hand = r2 + r1 + 'o'
            else: hand = r1 + r2
            act = get_gto_action(hand, pos)
            bg = "#e53e3e" if act == 'Raise' else ("#38a169" if act == 'Call' else "#2d3748")
            border = "border:2px solid #f6e05e; color:#f6e05e; z-index:10; transform:scale(1.15); box-shadow: 0 0 5px #f6e05e;" if hand == hero_hand else "border:1px solid #1a202c; color:white;"
            html += f'<div style="background-color:{bg}; {border} font-size:10px; font-weight:bold; text-align:center; padding:3px 0; border-radius:2px;">{hand}</div>'
    html += '</div>'
    return html

# ==========================================
# 6. 操作面板與覆盤總結
# ==========================================
hero = next(p for p in st.session_state.players if p['is_hero'])
active_count = len([p for p in st.session_state.players if p['active']])
is_multiway = active_count > 2

st.write("---")
if st.session_state.street != 'SHOWDOWN' and hero['active'] and hero['stack'] > 0.01:
    to_call = min(st.session_state.current_bet - hero['bet'], hero['stack'])
    
    col_log, col_action = st.columns([1, 1.2])
    with col_log:
        st.markdown("**📜 牌局即時動態**")
        st.caption("<br>".join(st.session_state.logs[-4:]), unsafe_allow_html=True)

    with col_action:
        c1, c2 = st.columns([1, 1])
        with c1: st.markdown(f"**🎮 輪到你行動** ({st.session_state.street})")
        with c2:
            if hero['stack'] <= 200:
                if st.button("💰 補充 100BB", help="最高上限 300BB"):
                    hero['stack'] = min(300.0, hero['stack'] + 100.0); st.session_state.hero_stack = hero['stack']; st.rerun()

        if st.session_state.street == 'PREFLOP':
            hero_hand_cat = get_hand_category(hero['cards'])
            with st.expander(f"📊 查看 {hero['pos']} 13x13 翻前矩陣 (當前: {hero_hand_cat})"):
                st.markdown(generate_13x13_html(hero['pos'], hero_hand_cat), unsafe_allow_html=True)

        options = []
        if to_call > 0: options.extend(['Fold', f"Call ({to_call:.1f} BB)"])
        else: options.append('Check')
        options.append('Bet / Raise')
        
        act = st.radio("你的決策:", options, horizontal=True, label_visibility="collapsed")
        min_r = max(st.session_state.current_bet * 2, 2.0 if st.session_state.street == 'PREFLOP' else 1.0)
        max_r = float(hero['stack'] + hero['bet'])
        min_r = min(min_r, max_r)
        
        c_val = min_r
        if act == 'Bet / Raise':
            if min_r < max_r: c_val = st.slider("下注/加注尺寸 (拖曳到底為 All-in):", float(min_r), float(max_r), float(min_r), 0.5)
            else: st.warning("籌碼不足，強制 All-in！"); c_val = max_r
                
        if st.button("確認行動", type="primary", use_container_width=True):
            st.session_state.last_actor = hero['pos']
            
            # 記錄每一條街的決策資訊
            st.session_state.hand_history.append({
                'street': st.session_state.street,
                'hero_cards': list(hero['cards']),
                'board': list(st.session_state.board),
                'pos': hero['pos'],
                'pot': st.session_state.pot,
                'to_call': to_call,
                'action': act,
                'bet_size': c_val if act == 'Bet / Raise' else (to_call if 'Call' in act else 0),
                'is_multiway': is_multiway
            })

            if act == 'Fold': hero['active'] = False; st.session_state.logs.append(f"👤 HERO 棄牌")
            elif 'Call' in act or 'Check' in act:
                hero['stack'] -= to_call; hero['bet'] += to_call; st.session_state.pot += to_call
                st.session_state.logs.append(f"👤 HERO {'過牌' if to_call == 0 else f'跟注 {to_call:.1f} BB'}")
            else:
                diff = c_val - hero['bet']; hero['stack'] -= diff; hero['bet'] = c_val; st.session_state.pot += diff
                st.session_state.current_bet = c_val; st.session_state.logs.append(f"🔥 👤 HERO 加注至 {c_val:.1f} BB")
                
            hero['acted_this_street'] = True; st.session_state.hero_acted_this_street = True
            st.session_state.turn_idx = (st.session_state.turn_idx + 1) % 6
            
            actives = [p for p in st.session_state.players if p['active']]
            if all(p.get('acted_this_street', False) for p in actives) and all((p['bet'] == st.session_state.current_bet or p['stack'] <= 0.01) for p in actives): next_street()
            process_bots_turn()
            st.rerun()

elif st.session_state.street == 'SHOWDOWN' or not hero['active']:
    st.subheader("🏁 牌局結算 (已攤牌)")
    if 'winner_resolved' not in st.session_state:
        actives = [p for p in st.session_state.players if p['active']]
        if len(actives) > 1 and len(st.session_state.board) == 5:
            best_s = (-1, []); winners = []
            for p in actives:
                s = get_hand_score(p['cards'] + st.session_state.board)
                if s > best_s: best_s = s; winners = [p]
                elif s == best_s: winners.append(p)
            win_amt = st.session_state.pot / len(winners)
            for w in winners: w['stack'] += win_amt; st.success(f"🏆 {w['name']} 獲勝！贏得 {win_amt:.1f} BB")
        elif len(actives) == 1:
            actives[0]['stack'] += st.session_state.pot; st.success(f"🏆 {actives[0]['name']} 獲勝！收獲 {st.session_state.pot:.1f} BB")
            
        for p in st.session_state.players:
            if p['is_hero']: st.session_state.hero_stack = p['stack']
            else: st.session_state[f'bot_stack_{p["pos"]}'] = p['stack']
        st.session_state.winner_resolved = True
        
    st.markdown("---")
    st.subheader("📊 GTO 三動作頻率覆盤與戰略總結")
    
    # --- 逐條街三動作頻率輸出 ---
    for rec in st.session_state.hand_history:
        st_name = rec['street']
        cat = get_hand_category(rec['hero_cards'])
        
        if st_name == 'PREFLOP':
            freq = calculate_preflop_frequencies(cat, rec['pos'], rec['to_call'])
            st.markdown(f"#### 🔹 【翻前 PREFLOP】（位置: {rec['pos']} | 手牌: `{rec['hero_cards'][0]}` `{rec['hero_cards'][1]}` `{cat}`）")
            
            c_f, c_c, c_r = st.columns(3)
            with c_f: st.metric("❌ Fold 棄牌頻率", f"{freq['Fold']}%")
            with c_c: st.metric("🛡️ Check/Call 頻率", f"{freq['Check_Call']}%")
            with c_r: st.metric("🔥 Raise 加注頻率", f"{freq['Raise']}%", f"建議: {freq['Raise_Size']}")
            st.caption(f"👉 你的實際行動：**{rec['action']}** (投入: {rec['bet_size']:.1f} BB)")
            
        else:
            h_type = classify_hero_postflop_hand(rec['hero_cards'], rec['board'])
            texture = evaluate_board_texture(rec['board'])
            freq = calculate_postflop_frequencies(h_type, texture, rec['to_call'], rec['is_multiway'])
            
            st.markdown(f"#### 🔹 【{st_name}】（牌面: {' '.join(rec['board'])} | 手牌實力: **{h_type}**）")
            
            if rec['to_call'] == 0:
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("🛡️ Check 過牌", f"{freq['Check']}%")
                with c2: st.metric("🎯 Bet 33% (小注)", f"{freq['Bet_33']}%")
                with c3: st.metric("🔥 Bet 75% (大注)", f"{freq['Bet_75']}%")
                with c4: st.metric("🚀 Overbet (超池)", f"{freq['Overbet']}%")
            else:
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("❌ Fold 棄牌", f"{freq['Fold']}%")
                with c2: st.metric("🛡️ Call 跟注", f"{freq['Call']}%")
                with c3: st.metric("🔥 Raise 加注", f"{freq['Raise']}%")
            st.caption(f"👉 你的實際行動：**{rec['action']}** (下注量: {rec['bet_size']:.1f} BB | 底池: {rec['pot']:.1f} BB)")
            
        st.write("")

    # --- 最後一段戰略總結 ---
    st.markdown("### 🧠 整手牌 GTO 戰略理由與頻率總結")
    
    if st.session_state.hand_history:
        last_rec = st.session_state.hand_history[-1]
        final_cards = last_rec['hero_cards']
        final_board = st.session_state.board
        cat = get_hand_category(final_cards)
        
        if len(final_board) >= 3:
            h_type = classify_hero_postflop_hand(final_cards, final_board)
            texture = evaluate_board_texture(final_board)
            
            summary_text = f"""
            在這手牌中，你持有 **{final_cards[0]} {final_cards[1]} ({cat})** 在 **{last_rec['pos']}** 位置進入對局，翻後形成了【**{h_type}**】。
            在『**{texture}**』的結構下，GTO 策略的核心圍繞在 **「範圍優勢（Range Advantage）」** 與 **「手牌保護（Protection）」** 的博弈：
            
            1. **下注尺寸與保護權益**：
               當你在動態牌面持有頂對或強聽牌時，對手有大量隱含賠率去追順子與同花。GTO 傾向使用 **67%–75% 的大尺寸** 來剝奪對手的跟注賠率（Equity Denial），這正是為什麼該尺寸擁有不可替代的進攻頻率；若是在乾燥面，則應切換為 **33% 小注高頻施壓**。
            
            2. **過牌頻率的重要性（避免被剝削）**：
               許多玩家容易犯下「有一點牌就 100% 下注」的錯誤。GTO 要求你在各條街必須維持 **25%–65% 的過牌頻率**，將中等成牌或弱頂對置入過牌範圍中，用來**保護你的過牌範圍（Protecting Checking Range）**。如此一來，激進的對手便無法在看到你 Check 後肆無忌憚地下注詐唬。
            
            3. **頻率平衡思維**：
               這手牌的每一個決策點都不存在絕對的「純策略（100% 同一動作）」。透過在相同情境下混合執行加注與過牌，你的整體範圍才能達到無法被對手洞悉與剝削的賽局理論均衡點。
            """
            st.info(summary_text)
        else:
            st.info(f"你在翻前持有 **{final_cards[0]} {final_cards[1]} ({cat})**。翻前範圍是整套 GTO 的地基，嚴格遵守各位置的開池頻率（UTG 15% 到 BTN 45%），能讓你在翻後避開絕大多數逆向隱含賠率的劣勢局面。")
            
    if st.button("發下一手牌 (Next Hand)", type="primary", use_container_width=True):
        del st.session_state.winner_resolved; start_new_hand(); st.rerun()
