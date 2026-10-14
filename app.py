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
    if len(board) < 3: return "翻前階段"
    ranks = [RANK_VALUES[c[:-1]] for c in board]
    suits = [c[-1] for c in board]
    if len(set(ranks[:3])) < 3: return "對子面 (Paired)"
    if len(set(suits[:3])) == 1: return "單色面 (Monotone)"
    if max(ranks[:3]) - min(ranks[:3]) <= 4: return "動態面 (Wet/Dynamic)"
    return "乾燥面 (Dry/Static)"

# ==========================================
# 2. GTO 頻率、保護與多人底池教練模組
# ==========================================
def analyze_gto_preflop(hand_cat, pos, to_call, is_raise):
    if pos == 'BB' and to_call == 0:
        return "🛡️ **GTO 混合策略 (大盲)**：你擁有大盲免費過牌權。只有頂端 10-15% 強牌需加注 (保護/價值)，其餘 85% 頻率應 Check 實現攤牌價值。"
    if to_call == 0: # First to act or facing limpers
        return f"🎯 **GTO 頻率 (位置 {pos})**：起手牌 {hand_cat}。GTO 翻前是嚴格的頻率遊戲。強牌 (AQ+, 88+) 100% Open；邊緣同花連牌 (如 87s) 在此位置建議 20%-50% 頻率混合加注，其餘棄牌。"
    if is_raise: # 3-Bet or 4-Bet
        return f"🔥 **GTO 頻率 (3-Bet/4-Bet)**：面對加注選擇反加！GTO 在此會使用兩極化範圍：用頂端強牌 (AA, KK, AK) 打價值，並混合 30% 頻率的同花 A 或同花連牌進行半詐唬，給予對手極大壓力。"
    # Calling a raise
    return f"⚖️ **GTO 頻率 (平跟防守)**：面對加注，平跟 (Flat Call) 通常佔防守範圍的 40%-60%（尤其是大盲位有賠率優勢時）。但要注意，平跟太多容易導致多人底池 (Multi-way)，使手牌勝率稀釋。"

def analyze_gto_postflop(street, bet, pot, texture, is_multiway):
    mw_text = "🧑‍🤝‍🧑 **[多人底池注意]**：" if is_multiway else "🤺 **[單挑底池]**："
    
    if bet == 0: 
        adv = f"{mw_text} 在『{texture}』過牌。GTO 中過牌頻率通常佔 40%-60%。"
        if is_multiway: adv += " 在多人底池中，你的防守負擔被分攤，且對手有強牌的機率大增，GTO 要求你**大幅提高過牌頻率**，放棄邊緣牌的詐唬。"
        else: adv += " 建議用中等牌力 (弱頂對/中對) 過牌來實現攤牌價值，保護過牌範圍不被剝削。"
        return adv
    
    pct = (bet / pot) * 100
    if pct <= 45: 
        adv = f"🎯 **GTO 頻率 (小注 {pct:.0f}%)**：高頻 (約 60-80%) 尺寸。"
        adv += f" {mw_text} 特別在乾燥面上，小注能便宜地進行**權益剝奪 (Equity Denial)**。若是多人底池，小注也能用來測試水溫，不至於過度膨脹底池。"
        return adv
    if pct <= 85: 
        adv = f"🔥 **GTO 頻率 (大注 {pct:.0f}%)**：低頻 (約 25-40%) 但破壞力強的尺寸。"
        adv += f" {mw_text} 在動態/濕滑面上，你的牌極需要**保護 (Protection)**。大注能極大化向聽牌收取費用，破壞對手底池賠率。"
        return adv
    
    return f"🚀 **GTO 頻率 (超池/All-in {pct:.0f}%)**：極化打法。頻率低於 10%。{mw_text} 通常只在你擁有**絕對堅果優勢 (Nut Advantage)** 時使用，用最頂端價值牌與純詐唬混合，極限施壓。"

# ==========================================
# 3. 遊戲狀態與激進 AI 迴圈
# ==========================================
POS_LIST = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

def start_new_hand():
    st.session_state.deck = create_deck()
    random.shuffle(st.session_state.deck)
    st.session_state.board = []
    st.session_state.street = 'PREFLOP'
    st.session_state.logs = []
    st.session_state.gto_reports = []
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
                
                # --- AI 邏輯 ---
                if st.session_state.street == 'PREFLOP':
                    if st.session_state.current_bet == 1.0: # 無人加注
                        if roll < 0.22: # Open Raise
                            r_amt = min(2.5, max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} Open 到 {r_amt:.1f} BB")
                        elif roll < 0.35: # Limp
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 平跟 (Call) 1.0 BB")
                        else:
                            if curr_p['pos'] == 'BB': st.session_state.logs.append(f"🤖 {curr_p['pos']} 過牌 (Check)")
                            else: curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
                    elif st.session_state.current_bet <= 5.0: # 面對一般 Open
                        if roll < 0.12: # 3-Bet!
                            r_amt = min(st.session_state.current_bet * 3, max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🔥 🤖 {curr_p['pos']} 3-Bet 加注到 {r_amt:.1f} BB!")
                        elif roll < 0.35: # Call
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                        else:
                            curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
                    else: # 面對 3-Bet/4-Bet
                        if roll < 0.10: # 4-Bet / All-in!
                            r_amt = min(st.session_state.current_bet * 2.2, max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🚀 🤖 {curr_p['pos']} 4-Bet/All-in 到 {r_amt:.1f} BB!")
                        elif roll < 0.25: # 艱難跟注
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                        else:
                            curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
                else: # 翻後
                    if to_call == 0:
                        if roll < 0.35: # C-bet
                            b_amt = min(round(st.session_state.pot * 0.45, 1), curr_p['stack'])
                            curr_p['stack'] -= b_amt; curr_p['bet'] = b_amt; st.session_state.pot += b_amt
                            st.session_state.current_bet = b_amt
                            st.session_state.logs.append(f"🎯 🤖 {curr_p['pos']} 下注 {b_amt:.1f} BB")
                        else: st.session_state.logs.append(f"🤖 {curr_p['pos']} 過牌 (Check)")
                    else:
                        if roll < 0.08: # Raise
                            r_amt = min(to_call * 2.5 + curr_p['bet'], max_allow)
                            add = r_amt - curr_p['bet']
                            curr_p['stack'] -= add; curr_p['bet'] = r_amt; st.session_state.pot += add
                            st.session_state.current_bet = r_amt
                            st.session_state.logs.append(f"🔥 🤖 {curr_p['pos']} 加注到 {r_amt:.1f} BB!")
                        elif roll < 0.45: # Call
                            curr_p['stack'] -= to_call; curr_p['bet'] += to_call; st.session_state.pot += to_call
                            st.session_state.logs.append(f"🤖 {curr_p['pos']} 跟注 {to_call:.1f} BB")
                        else: curr_p['active'] = False; st.session_state.logs.append(f"🤖 {curr_p['pos']} 棄牌")
            curr_p['acted_this_street'] = True
            
        st.session_state.turn_idx = (st.session_state.turn_idx + 1) % 6
        actives = [p for p in st.session_state.players if p['active']]
        if len(actives) == 1:
            st.session_state.street = 'SHOWDOWN'; break
        if all(p.get('acted_this_street', False) for p in actives) and all((p['bet'] == st.session_state.current_bet or p['stack'] <= 0.01) for p in actives):
            next_street()

# ==========================================
# 4. Base64 SVG 渲染
# ==========================================
st.set_page_config(page_title="GTO 競技教練", layout="centered")
if 'hero_stack' not in st.session_state: st.session_state.hero_stack = 100.0
if 'street' not in st.session_state: start_new_hand()

def draw_card(c, x, y):
    if not c: return ""
    r, s = c[:-1], c[-1]
    col = "#e53e3e" if s in ['♥', '♦'] else "#1a202c"
    return f'<g transform="translate({x},{y})"><rect width="36" height="52" rx="4" fill="white" stroke="#718096" stroke-width="1"/><text x="18" y="26" font-family="Arial" font-size="20" font-weight="bold" fill="{col}" text-anchor="middle" dominant-baseline="central">{r}{s}</text></g>'

def draw_back(x, y):
    return f'<g transform="translate({x},{y})"><rect width="36" height="52" rx="4" fill="#2b6cb0" stroke="#cbd5e0" stroke-width="1"/><rect x="4" y="4" width="28" height="44" rx="2" fill="#2c5282"/></g>'

def draw_player(cx, cy, p):
    is_h = p['is_hero']
    dim = "opacity: 0.35;" if not p['active'] else "opacity: 1.0;"
    bg = "#2d3748" if is_h else "#1a202c"
    bd = "#ecc94b" if is_h else "#4a5568"
    
    svg = f'<g style="{dim}">'
    if p['bet'] > 0:
        bx, by = cx + (400 - cx) * 0.28, cy + (250 - cy) * 0.28
        svg += f'<rect x="{bx-25}" y="{by-12}" width="50" height="24" rx="12" fill="rgba(0,0,0,0.8)"/><text x="{bx}" y="{by}" font-family="Arial" font-size="12" font-weight="bold" fill="#68d391" text-anchor="middle" dominant-baseline="central">{p["bet"]:.1f}</text>'
    
    svg += f'<rect x="{cx-48}" y="{cy-20}" width="96" height="40" rx="6" fill="{bg}" stroke="{bd}" stroke-width="2"/><rect x="{cx-45}" y="{cy-16}" width="26" height="16" rx="3" fill="{"#ecc94b" if is_h else "#e2e8f0"}"/><text x="{cx-32}" y="{cy-8}" font-family="Arial" font-size="10" font-weight="bold" fill="black" text-anchor="middle" dominant-baseline="central">{p["pos"]}</text><text x="{cx-14}" y="{cy-8}" font-family="Arial" font-size="12" font-weight="bold" fill="white" dominant-baseline="central">{p["name"][:7]}</text><text x="{cx}" y="{cy+10}" font-family="Arial" font-size="13" font-weight="bold" fill="#ecc94b" text-anchor="middle" dominant-baseline="central">{p["stack"]:.1f} BB</text>'
    
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

full_svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="800" height="500"><rect width="800" height="500" fill="#121212" rx="16"/><ellipse cx="400" cy="250" rx="360" ry="190" fill="#1e4d2b" stroke="#3c2415" stroke-width="16"/><rect x="330" y="165" width="140" height="30" rx="15" fill="rgba(0,0,0,0.7)"/><text x="400" y="180" font-family="Arial" font-size="15" font-weight="bold" fill="#f6e05e" text-anchor="middle" dominant-baseline="central">Pot: {st.session_state.pot:.1f} BB</text>{b_svg}{p_svg}</svg>'
b64_svg = base64.b64encode(full_svg_str.encode('utf-8')).decode('utf-8')
st.markdown(f'<div style="text-align:center;"><img src="data:image/svg+xml;base64,{b64_svg}" style="width:100%; max-width:800px; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);"></div>', unsafe_allow_html=True)

# ==========================================
# 5. 操作面板與 GTO 頻率分析
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
                    hero['stack'] = min(300.0, hero['stack'] + 100.0)
                    st.session_state.hero_stack = hero['stack']
                    st.rerun()

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
                c_val = st.slider("尺寸 (拖曳到底為 All-in):", float(min_r), float(max_r), float(min_r), 0.5)
            else:
                st.warning("籌碼不足，強制 All-in！"); c_val = max_r
                
        if st.button("確認行動", type="primary", use_container_width=True):
            cat = get_hand_category(hero['cards'])
            tex = evaluate_board_texture(st.session_state.board)
            if st.session_state.street == 'PREFLOP': st.session_state.gto_reports.append(analyze_gto_preflop(cat, hero['pos'], to_call, act == 'Bet / Raise'))
            else: st.session_state.gto_reports.append(analyze_gto_postflop(st.session_state.street, c_val if act == 'Bet / Raise' else 0, st.session_state.pot, tex, is_multiway))

            if act == 'Fold': hero['active'] = False; st.session_state.logs.append(f"👤 HERO 棄牌")
            elif 'Call' in act or 'Check' in act:
                hero['stack'] -= to_call; hero['bet'] += to_call; st.session_state.pot += to_call
                st.session_state.logs.append(f"👤 HERO {'過牌' if to_call == 0 else f'跟注 {to_call:.1f} BB'}")
            else:
                diff = c_val - hero['bet']
                hero['stack'] -= diff; hero['bet'] = c_val; st.session_state.pot += diff
                st.session_state.current_bet = c_val; st.session_state.logs.append(f"🔥 👤 HERO 加注至 {c_val:.1f} BB")
                
            hero['acted_this_street'] = True; st.session_state.hero_acted_this_street = True
            st.session_state.turn_idx = (st.session_state.turn_idx + 1) % 6
            
            actives = [p for p in st.session_state.players if p['active']]
            if all(p.get('acted_this_street', False) for p in actives) and all((p['bet'] == st.session_state.current_bet or p['stack'] <= 0.01) for p in actives): next_street()
            process_bots_turn()
            st.rerun()

elif st.session_state.street == 'SHOWDOWN' or not hero['active']:
    st.subheader("🏁 牌局結算")
    
    if 'winner_resolved' not in st.session_state:
        actives = [p for p in st.session_state.players if p['active']]
        if len(actives) > 1 and len(st.session_state.board) == 5:
            # 【修復重點】：將 best_s 初始化為包含空 list 的 tuple，避免 TypeError 崩潰
            best_s = (-1, [])
            winners = []
            for p in actives:
                s = get_hand_score(p['cards'] + st.session_state.board)
                if s > best_s: best_s = s; winners = [p]
                elif s == best_s: winners.append(p)
            win_amt = st.session_state.pot / len(winners)
            for w in winners:
                w['stack'] += win_amt
                st.success(f"🏆 {w['name']} 獲勝！贏得 {win_amt:.1f} BB")
        elif len(actives) == 1:
            actives[0]['stack'] += st.session_state.pot
            st.success(f"🏆 {actives[0]['name']} 獲勝！收獲底池 {st.session_state.pot:.1f} BB")
            
        for p in st.session_state.players:
            if p['is_hero']: st.session_state.hero_stack = p['stack']
            else: st.session_state[f'bot_stack_{p["pos"]}'] = p['stack']
        st.session_state.winner_resolved = True
        
    st.info("📜 **本局 GTO 頻率與保護策略總結**")
    for r in st.session_state.gto_reports: st.markdown(r)
    
    if st.button("發下一手牌 (Next Hand)", type="primary", use_container_width=True):
        del st.session_state.winner_resolved; start_new_hand(); st.rerun()
