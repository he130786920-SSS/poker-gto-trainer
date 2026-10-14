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
# 2. 169 手牌精準 GTO 頻率分配庫 (Raise / Call / Fold)
# ==========================================
def get_gto_breakdown(hand, pos):
    r1, r2 = hand[0], hand[1]
    is_pair = (r1 == r2)
    is_suited = hand.endswith('s')
    v1, v2 = RANK_VALUES[r1], RANK_VALUES[r2]
    vh, vl = max(v1, v2), min(v1, v2)
    
    if pos == 'UTG':
        if is_pair:
            if vh >= 11: return (100, 0, 0)
            if vh == 10: return (90, 0, 10)
            if vh == 9: return (75, 0, 25)
            if vh == 8: return (55, 0, 45)
            if vh == 7: return (35, 0, 65)
            if vh == 6: return (15, 0, 85)
            return (0, 0, 100)
        if is_suited:
            if vh == 14 and vl >= 10: return (100, 0, 0)
            if vh == 14 and vl in [5, 4]: return (50, 0, 50)
            if vh == 14 and vl == 9: return (30, 0, 70)
            if vh == 13 and vl in [12, 11]: return (100, 0, 0)
            if vh == 13 and vl == 10: return (55, 0, 45)
            if vh == 12 and vl == 11: return (100, 0, 0)
            if vh == 12 and vl == 10: return (45, 0, 55)
            if vh == 11 and vl == 10: return (100, 0, 0)
            if vh == 10 and vl == 9: return (55, 0, 45)
            if vh == 9 and vl == 8: return (35, 0, 65)
            if vh == 8 and vl == 7: return (25, 0, 75)
            return (0, 0, 100)
        if vh == 14 and vl == 13: return (100, 0, 0)
        if vh == 14 and vl == 12: return (85, 0, 15)
        if vh == 14 and vl == 11: return (40, 0, 60)
        if vh == 13 and vl == 12: return (40, 0, 60)
        return (0, 0, 100)

    elif pos == 'HJ':
        if is_pair:
            if vh >= 10: return (100, 0, 0)
            if vh in [9, 8]: return (85, 0, 15)
            if vh == 7: return (65, 0, 35)
            if vh == 6: return (45, 0, 55)
            if vh == 5: return (25, 0, 75)
            return (0, 0, 100)
        if is_suited:
            if vh == 14 and vl >= 8: return (100, 0, 0)
            if vh == 14 and vl in [5, 4]: return (75, 0, 25)
            if vh == 14 and vl in [7, 6, 3]: return (40, 0, 60)
            if vh == 13 and vl >= 10: return (100, 0, 0)
            if vh == 13 and vl == 9: return (50, 0, 50)
            if vh == 12 and vl >= 10: return (90, 0, 10)
            if vh == 12 and vl == 9: return (45, 0, 55)
            if vh == 11 and vl >= 9: return (85, 0, 15)
            if vh == 10 and vl == 9: return (80, 0, 20)
            if vh in [9, 8] and vh - vl == 1: return (55, 0, 45)
            if vh == 7 and vl == 6: return (40, 0, 60)
            return (0, 0, 100)
        if vh == 14 and vl >= 12: return (100, 0, 0)
        if vh == 14 and vl == 11: return (75, 0, 25)
        if vh == 14 and vl == 10: return (35, 0, 65)
        if vh == 13 and vl == 12: return (70, 0, 30)
        if vh == 13 and vl == 11: return (35, 0, 65)
        return (0, 0, 100)

    elif pos == 'CO':
        if is_pair:
            if vh >= 7: return (100, 0, 0)
            if vh in [6, 5]: return (80, 0, 20)
            if vh in [4, 3, 2]: return (60, 0, 40)
        if is_suited:
            if vh == 14: return (100, 0, 0)
            if vh == 13 and vl >= 7: return (90, 0, 10)
            if vh == 13 and vl < 7: return (50, 0, 50)
            if vh == 12 and vl >= 8: return (90, 0, 10)
            if vh == 12 and vl < 8: return (45, 0, 55)
            if vh == 11 and vl >= 7: return (85, 0, 15)
            if vh <= 10 and vh - vl <= 2: return (75, 0, 25)
            return (25, 0, 75)
        if vh == 14 and vl >= 11: return (100, 0, 0)
        if vh == 14 and vl == 10: return (80, 0, 20)
        if vh == 14 and vl == 9: return (50, 0, 50)
        if vh == 13 and vl >= 11: return (85, 0, 15)
        if vh == 13 and vl == 10: return (55, 0, 45)
        if vh == 12 and vl >= 10: return (65, 0, 35)
        return (0, 0, 100)

    elif pos in ['BTN', 'SB']:
        if is_pair: return (100, 0, 0)
        if is_suited:
            if vh == 14: return (100, 0, 0)
            if vh == 13: return (90, 0, 10)
            if vh == 12 and vl >= 4: return (85, 0, 15)
            if vh == 11 and vl >= 4: return (80, 0, 20)
            if vh - vl <= 3: return (80, 0, 20)
            return (45, 0, 55)
        if vh == 14 and vl >= 7: return (100, 0, 0)
        if vh == 14 and vl < 7: return (65, 0, 35)
        if vh == 13 and vl >= 8: return (85, 0, 15)
        if vh == 13 and vl < 8: return (50, 0, 50)
        if vh == 12 and vl >= 8: return (80, 0, 20)
        if vh == 11 and vl >= 8: return (75, 0, 25)
        if vh == 10 and vl >= 8: return (60, 0, 40)
        if vh == 9 and vl == 8: return (50, 0, 50)
        return (0, 0, 100)

    elif pos == 'BB':
        if hand in ['AA', 'KK']: return (85, 15, 0)
        if hand in ['QQ', 'JJ', 'TT', 'AKs', 'AKo']: return (60, 40, 0)
        if is_pair and vh >= 6: return (20, 80, 0)
        if is_pair and vh < 6: return (10, 75, 15)
        if is_suited:
            if vh == 14 and vl >= 10: return (35, 65, 0)
            if vh == 14 and vl < 10: return (15, 80, 5)
            if vh == 13 and vl >= 9: return (15, 85, 0)
            if vh == 13 and vl < 9: return (5, 75, 20)
            if vh == 12 and vl >= 8: return (10, 85, 5)
            if vh <= 11 and vh - vl <= 2: return (15, 85, 0)
            return (0, 65, 35)
        if vh == 14 and vl >= 11: return (25, 75, 0)
        if vh == 14 and vl in [10, 9]: return (10, 75, 15)
        if vh == 14 and vl < 9: return (0, 50, 50)
        if vh == 13 and vl >= 10: return (10, 75, 15)
        if vh == 13 and vl == 9: return (0, 60, 40)
        if vh == 12 and vl >= 9: return (0, 65, 35)
        if vh == 11 and vl >= 9: return (0, 60, 40)
        if vh == 10 and vl == 9: return (0, 60, 40)
        return (0, 15, 85)

    return (0, 0, 100)

# 使用純 CSS 處理放大與樣式，消除任何可能引發 SyntaxError 的 inline escape
def generate_13x13_html(pos, hero_hand):
    ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    rv = lambda r: RANK_VALUES[r]
    
    css = """
    <style>
      .matrix-grid { display:grid; grid-template-columns:repeat(13, 1fr); gap:2px; background-color:#0d1117; padding:4px; border-radius:8px; }
      .matrix-cell { font-size:9.5px; font-family:monospace; font-weight:bold; text-align:center; padding:3.5px 0; border-radius:3px; cursor:pointer; text-shadow:0 1px 2px rgba(0,0,0,0.9); transition:transform 0.12s ease; border:1px solid rgba(255,255,255,0.08); color:#fff; }
      .matrix-cell:hover { transform:scale(1.25) !important; z-index:50 !important; box-shadow:0 0 10px rgba(255,255,255,0.5); }
      .matrix-hero { border:2px solid #f6e05e !important; box-shadow:0 0 8px #f6e05e; transform:scale(1.15); z-index:10; font-weight:900; }
    </style>
    """
    
    cells = []
    for r1 in ranks:
        for r2 in ranks:
            if rv(r1) > rv(r2): hand = r1 + r2 + 's'
            elif rv(r1) < rv(r2): hand = r2 + r1 + 'o'
            else: hand = r1 + r2
            
            r_pct, c_pct, f_pct = get_gto_breakdown(hand, pos)
            
            if r_pct == 100: bg = "#e53e3e"
            elif f_pct == 100: bg = "#2d3748"
            elif c_pct == 100: bg = "#38a169"
            else:
                p1 = r_pct
                p2 = r_pct + c_pct
                bg = f"linear-gradient(to right, #e53e3e 0% {p1}%, #38a169 {p1}% {p2}%, #2d3748 {p2}% 100%)"
            
            title_text = f"【{hand}】&#10;🔥 加注: {r_pct}%&#10;🛡️ 跟注: {c_pct}%&#10;❌ 棄牌: {f_pct}%"
            extra_class = " matrix-hero" if hand == hero_hand else ""
            cells.append(f'<div class="matrix-cell{extra_class}" title="{title_text}" style="background:{bg};">{hand}</div>')
            
    html = css + '<div class="matrix-grid">' + "".join(cells) + '</div>'
    html += """
    <div style="margin-top:8px; font-size:12px; color:#cbd5e0; line-height:1.6;">
      <span style="display:inline-block; width:12px; height:12px; background:#e53e3e; vertical-align:middle; border-radius:2px;"></span> <strong>加注 (Raise)</strong> &nbsp;&nbsp;
      <span style="display:inline-block; width:12px; height:12px; background:#38a169; vertical-align:middle; border-radius:2px;"></span> <strong>跟注 (Call)</strong> &nbsp;&nbsp;
      <span style="display:inline-block; width:12px; height:12px; background:#2d3748; vertical-align:middle; border-radius:2px;"></span> <strong>棄牌 (Fold)</strong><br>
      💡 雙色/三色代表 <strong>GTO 混合頻率</strong>；<strong>滑鼠懸停於任意手牌即可浮現精確百分比</strong>。<br>
      <span style="border:1px solid #f6e05e; padding:0 3px; color:#f6e05e; border-radius:2px;">黃框</span> 為高玩當前手牌。
    </div>
    """
    return html

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
            'pos': p, 'name': '高玩' if is_h else f"Bot_{p}", 'is_hero': is_h,
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
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} Open 到 {r_amt:.1f} BB")
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
                            st.session_state.logs.append(f"🔥 🤖 {curr_p['pos']} 3-Bet 到 {r_amt:.1f} BB!")
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
                            st.session_state.logs.append(f"🚀 🤖 {curr_p['pos']} 4-Bet/All-in 到 {r_amt:.1f} BB!")
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
                            st.session_state.logs.append(f"🔥 🤖 {curr_p['pos']} 加注到 {r_amt:.1f} BB!")
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
# 4. 精確六座位無遮擋座標引擎
# ==========================================
st.set_page_config(page_title="GTO 競技訓練大師", layout="wide")

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

SEAT_LAYOUT = {
    'HJ': {'badge': (400, 52), 'cards': (380, 80, 420, 80), 'chip': (400, 142)},
    'CO': {'badge': (645, 125), 'cards': (607, 48, 647, 48), 'chip': (565, 155)},
    'BTN': {'badge': (660, 375), 'cards': (622, 305, 662, 305), 'chip': (575, 315)},
    'SB': {'badge': (400, 450), 'cards': (380, 372, 420, 372), 'chip': (400, 325)},
    'BB': {'badge': (140, 375), 'cards': (102, 305, 142, 305), 'chip': (225, 315)},
    'UTG': {'badge': (155, 125), 'cards': (117, 48, 157, 48), 'chip': (235, 155)}
}

def draw_player(p):
    pos = p['pos']
    cfg = SEAT_LAYOUT[pos]
    cx, cy = cfg['badge']
    c1_x, c1_y, c2_x, c2_y = cfg['cards']
    chip_x, chip_y = cfg['chip']
    
    is_h = p['is_hero']
    dim = "opacity: 0.35;" if not p['active'] else "opacity: 1.0;"
    bg, bd = ("#2d3748", "#ecc94b") if is_h else ("#1a202c", "#4a5568")
    is_acting = (p['pos'] == st.session_state.get('last_actor'))
    seat_class = 'class="active-player-glow"' if is_acting else ''
    
    svg = f'<g style="{dim}">'
    if p['bet'] > 0:
        svg += f'<g transform="translate({chip_x-25},{chip_y-12})" class="chip-pop-anim"><rect width="50" height="24" rx="12" fill="rgba(0,0,0,0.85)" stroke="#68d391" stroke-width="1.5"/><text x="25" y="12" font-family="Arial" font-size="12" font-weight="bold" fill="#68d391" text-anchor="middle" dominant-baseline="central">{p["bet"]:.1f}</text></g>'
    
    svg += f'<g {seat_class}><rect x="{cx-48}" y="{cy-20}" width="96" height="40" rx="6" fill="{bg}" stroke="{bd}" stroke-width="2"/><rect x="{cx-45}" y="{cy-16}" width="26" height="16" rx="3" fill="{"#ecc94b" if is_h else "#e2e8f0"}"/><text x="{cx-32}" y="{cy-8}" font-family="Arial" font-size="10" font-weight="bold" fill="black" text-anchor="middle" dominant-baseline="central">{p["pos"]}</text><text x="{cx-14}" y="{cy-8}" font-family="Arial" font-size="12" font-weight="bold" fill="white" dominant-baseline="central">{p["name"][:7]}</text><text x="{cx}" y="{cy+10}" font-family="Arial" font-size="13" font-weight="bold" fill="#ecc94b" text-anchor="middle" dominant-baseline="central">{p["stack"]:.1f} BB</text></g>'
    
    if p['active']:
        if is_h or st.session_state.street == 'SHOWDOWN':
            svg += draw_card(p['cards'][0], c1_x - 18, c1_y) + draw_card(p['cards'][1], c2_x - 18, c2_y)
        else:
            svg += draw_back(c1_x - 18, c1_y) + draw_back(c2_x - 18, c2_y)
    svg += '</g>'
    return svg

b_svg = "".join([draw_card(c, 400 - (len(st.session_state.board)*40)/2 + i*40, 205) for i, c in enumerate(st.session_state.board)])
players_svg = "".join([draw_player(p) for p in st.session_state.players])

anim_styles = """
<style>
  @keyframes cardDrop { 0% { transform: translateY(-20px); opacity: 0; } 100% { transform: translateY(0); opacity: 1; } }
  @keyframes chipPop { 0% { transform: scale(0.3); opacity: 0; } 60% { transform: scale(1.2); opacity: 1; } 100% { transform: scale(1); opacity: 1; } }
  @keyframes activePulse { 0%, 100% { filter: drop-shadow(0 0 2px #ecc94b); } 50% { filter: drop-shadow(0 0 10px #f6e05e); } }
  .card-anim { animation: cardDrop 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
  .chip-pop-anim { animation: chipPop 0.3s ease-out; }
  .active-player-glow { animation: activePulse 1.2s infinite; }
</style>
"""

full_svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="800" height="500">{anim_styles}<rect width="800" height="500" fill="#121212" rx="16"/><ellipse cx="400" cy="250" rx="360" ry="190" fill="#1e4d2b" stroke="#3c2415" stroke-width="16"/><rect x="330" y="162" width="140" height="30" rx="15" fill="rgba(0,0,0,0.7)"/><text x="400" y="177" font-family="Arial" font-size="15" font-weight="bold" fill="#f6e05e" text-anchor="middle" dominant-baseline="central">Pot: {st.session_state.pot:.1f} BB</text>{b_svg}{players_svg}</svg>'
b64_svg = base64.b64encode(full_svg_str.encode('utf-8')).decode('utf-8')

# ==========================================
# 5. 寬螢幕雙欄佈局 (左桌右控)
# ==========================================
hero = next(p for p in st.session_state.players if p['is_hero'])
active_count = len([p for p in st.session_state.players if p['active']])
is_multiway = active_count > 2

col_table, col_control = st.columns([1.3, 1.0], gap="medium")

with col_table:
    st.markdown(f'<div style="text-align:center;"><img src="data:image/svg+xml;base64,{b64_svg}" style="width:100%; max-width:800px; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);"></div>', unsafe_allow_html=True)
    c_s1, c_s2, c_s3 = st.columns(3)
    with c_s1: st.info(f"**玩家**: 高玩 (`{hero['pos']}`)")
    with c_s2: st.info(f"**後手籌碼**: `{hero['stack']:.1f} BB`")
    with c_s3: st.info(f"**當前底池**: `{st.session_state.pot:.1f} BB`")

with col_control:
    if st.session_state.street != 'SHOWDOWN' and hero['active'] and hero['stack'] > 0.01:
        to_call = min(st.session_state.current_bet - hero['bet'], hero['stack'])
        
        h_col1, h_col2 = st.columns([1.2, 1.0])
        with h_col1:
            st.markdown(f"### 🎮 輪到高玩行動")
            st.caption(f"階段: **{st.session_state.street}** | 需補齊跟注: **{to_call:.1f} BB**")
        with h_col2:
            if hero['stack'] <= 200:
                if st.button("💰 補充 100BB", use_container_width=True):
                    hero['stack'] = min(300.0, hero['stack'] + 100.0)
                    st.session_state.hero_stack = hero['stack']
                    st.rerun()

        if st.session_state.street == 'PREFLOP':
            hero_hand_cat = get_hand_category(hero['cards'])
            with st.expander(f"📊 {hero['pos']} 13x13 GTO 頻率矩陣 (目前: {hero_hand_cat})"):
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
            if min_r < max_r:
                c_val = st.slider("下注/加注尺寸 (拖曳到底為 All-in):", float(min_r), float(max_r), float(min_r), 0.5)
                pct = (c_val / st.session_state.pot) * 100 if st.session_state.pot > 0 else 0
                st.caption(f"⚡ 當前尺寸約為底池的 **{pct:.0f}%**")
            else:
                st.warning("籌碼不足，強制 All-in！")
                c_val = max_r
                
        if st.button("🔥 確認行動", type="primary", use_container_width=True):
            st.session_state.last_actor = hero['pos']
            
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

            if act == 'Fold': hero['active'] = False; st.session_state.logs.append(f"👤 高玩 棄牌")
            elif 'Call' in act or 'Check' in act:
                hero['stack'] -= to_call; hero['bet'] += to_call; st.session_state.pot += to_call
                st.session_state.logs.append(f"👤 高玩 {'過牌' if to_call == 0 else f'跟注 {to_call:.1f} BB'}")
            else:
                diff = c_val - hero['bet']; hero['stack'] -= diff; hero['bet'] = c_val; st.session_state.pot += diff
                st.session_state.current_bet = c_val; st.session_state.logs.append(f"🔥 👤 高玩 加注至 {c_val:.1f} BB")
                
            hero['acted_this_street'] = True; st.session_state.hero_acted_this_street = True
            st.session_state.turn_idx = (st.session_state.turn_idx + 1) % 6
            
            actives = [p for p in st.session_state.players if p['active']]
            if all(p.get('acted_this_street', False) for p in actives) and all((p['bet'] == st.session_state.current_bet or p['stack'] <= 0.01) for p in actives): next_street()
            process_bots_turn()
            st.rerun()

        st.markdown("---")
        st.markdown("**📜 牌局即時動態**")
        st.caption("<br>".join(st.session_state.logs[-5:]), unsafe_allow_html=True)

    elif st.session_state.street == 'SHOWDOWN' or not hero['active']:
        st.markdown("### 🏁 牌局結算")
        
        if st.button("🚀 發下一手牌 (Next Hand)", type="primary", use_container_width=True):
            if 'winner_resolved' in st.session_state: del st.session_state.winner_resolved
            start_new_hand()
            st.rerun()
            
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

        st.markdown("#### 📊 GTO 三動作頻率覆盤")
        for rec in st.session_state.hand_history:
            st_name = rec['street']
            cat = get_hand_category(rec['hero_cards'])
            
            if st_name == 'PREFLOP':
                r_pct, c_pct, f_pct = get_gto_breakdown(cat, rec['pos'])
                st.markdown(f"**🔹 【翻前 PREFLOP】** (手牌: `{cat}`)")
                c_f, c_c, c_r = st.columns(3)
                with c_f: st.metric("Fold 頻率", f"{f_pct}%")
                with c_c: st.metric("Check/Call 頻率", f"{c_pct}%")
                with c_r: st.metric("Raise 頻率", f"{r_pct}%")
                st.caption(f"👉 實際行動：**{rec['action']}**")
            else:
                h_type = classify_hero_postflop_hand(rec['hero_cards'], rec['board'])
                st.markdown(f"**🔹 【{st_name}】** ({h_type})")
                st.caption(f"👉 實際行動：**{rec['action']}** (下注量: {rec['bet_size']:.1f} BB)")

        st.markdown("#### 🧠 GTO 戰略理由總結")
        if st.session_state.hand_history:
            last_rec = st.session_state.hand_history[-1]
            final_cards = last_rec['hero_cards']
            final_board = st.session_state.board
            cat = get_hand_category(final_cards)
            if len(final_board) >= 3:
                h_type = classify_hero_postflop_hand(final_cards, final_board)
                texture = evaluate_board_texture(final_board)
                st.info(f"高玩持有 **{final_cards[0]} {final_cards[1]} ({cat})** 形成【**{h_type}**】。在『**{texture}**』下，若牌面動態需用 **67%-75% 大尺寸保護手牌**並剝奪對手抽牌勝率；若缺乏堅果優勢，應維持 **30%-60% 過牌頻率**進行控池防守，保護過牌範圍不被剝削。")
