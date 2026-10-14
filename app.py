import streamlit as st
import random
import itertools
from collections import Counter

# ==========================================
# 1. 撲克底層引擎 (Cards & Evaluator)
# ==========================================
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

def create_deck():
    return [r + s for r in RANKS for s in SUITS]

def evaluate_5card(hand):
    """計算 5 張牌的強度分數 (分數越高牌力越大)"""
    ranks = sorted([RANK_VALUES[card[:-1]] for card in hand], reverse=True)
    suits = [card[-1] for card in hand]
    
    is_flush = len(set(suits)) == 1
    
    # 順子判斷 (考慮 A-2-3-4-5 輪轉順)
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
            
    rank_counts = Counter(ranks)
    counts = sorted(rank_counts.values(), reverse=True)
    counts_ranks = sorted(rank_counts.keys(), key=lambda r: (rank_counts[r], r), reverse=True)
    
    # 牌型等級：8: 同花順, 7: 四條, 6: 葫蘆, 5: 同花, 4: 順子, 3: 三條, 2: 兩對, 1: 一對, 0: 高牌
    if is_straight and is_flush:
        return (8, straight_high)
    if counts == [4, 1]:
        return (7, counts_ranks)
    if counts == [3, 2]:
        return (6, counts_ranks)
    if is_flush:
        return (5, ranks)
    if is_straight:
        return (4, straight_high)
    if counts == [3, 1, 1]:
        return (3, counts_ranks)
    if counts == [2, 2, 1]:
        return (2, counts_ranks)
    if counts == [2, 1, 1, 1]:
        return (1, counts_ranks)
    return (0, ranks)

def evaluate_best_hand(cards):
    """從 7 張牌選出最強 5 張組合"""
    best_score = (-1, [])
    for comb in itertools.combinations(cards, 5):
        score = evaluate_5card(comb)
        if score > best_score:
            best_score = score
    return best_score

# ==========================================
# 2. GTO 矩陣與理論分析引擎
# ==========================================
def get_hand_category(card1, card2):
    r1, s1 = card1[:-1], card1[-1]
    r2, s2 = card2[:-1], card2[-1]
    v1, v2 = RANK_VALUES[r1], RANK_VALUES[r2]
    high = r1 if v1 >= v2 else r2
    low = r2 if v1 >= v2 else r1
    suited = 's' if s1 == s2 else 'o'
    return high + low + ('' if high == low else suited)

# 6-Max No-Rake 100BB 標準開牌範圍基準線 (越早位置越緊)
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
    is_pair = r1 == r2
    is_suited = hand_cat.endswith('s')
    
    if is_pair:
        pair_val = RANK_VALUES[r1]
        if pair_val >= std['pairs']:
            return "✅ **GTO 建議**: 100% Open Raise (具備純價值與攤牌勝率)。"
        return "⚠️ **GTO 建議**: 棄牌 (邊緣口袋對子，此位置易被身後加注施壓)。"
    
    if is_suited and r1 == 'A':
        k_val = RANK_VALUES[r2]
        if k_val >= std['suited_ax']:
            return "✅ **GTO 建議**: 100% Open Raise (同花 A 具備強大 Nuts 潛力與阻擋牌效果)。"
    
    if hand_cat in std['broadway_off'] or hand_cat in std.get('connectors', []):
        return "✅ **GTO 建議**: 標準 Open Raise (此位置的動態防守/價值範圍)。"
        
    return "❌ **GTO 建議**: Fold (在 100BB 無抽水環境下，該起手牌在該位置期望值為負)。"

def evaluate_board_texture(board):
    if len(board) < 3:
        return "Preflop"
    ranks = [RANK_VALUES[c[:-1]] for c in board]
    suits = [c[-1] for c in board]
    
    is_monotone = len(set(suits[:3])) == 1
    is_paired = len(set(ranks[:3])) < 3
    span = max(ranks[:3]) - min(ranks[:3])
    
    if is_paired:
        return "Paired Board (對子面)"
    if is_monotone:
        return "Monotone (單色面)"
    if span <= 4:
        return "Wet / Connected (濕滑動態面)"
    return "Dry / Disconnected (乾燥乾燥面)"

# ==========================================
# 3. 擬真隨機偏離機器人 (Realistic Bots)
# ==========================================
class RealisticBot:
    def __init__(self, name, archetype, stack=100):
        self.name = name
        self.archetype = archetype
        self.stack = stack
        # 加入高斯隨機擾動，避免行為固定被抓馬腳
        jitter = lambda: random.uniform(-0.06, 0.06)
        
        if archetype == 'TAG (緊兇-常客)':
            self.vpip = max(0.16, min(0.24, 0.20 + jitter()))
            self.pfr = max(0.14, min(self.vpip, 0.17 + jitter()))
            self.fold_to_cbet = max(0.40, min(0.55, 0.46 + jitter()))
            self.aggression = 0.65
        elif archetype == 'LAG (鬆兇-常客)':
            self.vpip = max(0.26, min(0.35, 0.29 + jitter()))
            self.pfr = max(0.22, min(self.vpip, 0.25 + jitter()))
            self.fold_to_cbet = max(0.32, min(0.45, 0.38 + jitter()))
            self.aggression = 0.80
        elif archetype == 'Calling Station (跟注站)':
            self.vpip = max(0.38, min(0.55, 0.45 + jitter()))
            self.pfr = max(0.05, min(0.12, 0.08 + jitter()))
            self.fold_to_cbet = max(0.15, min(0.28, 0.20 + jitter()))
            self.aggression = 0.25
        elif archetype == 'Nit (石頭人)':
            self.vpip = max(0.10, min(0.15, 0.12 + jitter()))
            self.pfr = max(0.08, min(self.vpip, 0.10 + jitter()))
            self.fold_to_cbet = max(0.60, min(0.75, 0.68 + jitter()))
            self.aggression = 0.35
        else: # Maniac (狂人)
            self.vpip = max(0.45, min(0.65, 0.52 + jitter()))
            self.pfr = max(0.35, min(self.vpip, 0.42 + jitter()))
            self.fold_to_cbet = max(0.20, min(0.35, 0.25 + jitter()))
            self.aggression = 0.90

    def decide_preflop(self, hand_cat, position, current_bet):
        roll = random.random()
        if current_bet <= 1.0: # 未面臨加注
            if roll < self.pfr:
                return "Raise", 2.5
            elif roll < self.vpip:
                return "Call", 1.0
            return "Fold", 0
        else:
            if roll < (self.vpip * 0.45):
                return "Call", current_bet
            elif roll < (self.pfr * 0.25) and self.aggression > 0.6:
                return "Raise", current_bet * 3
            return "Fold", 0

    def decide_postflop(self, pot, facing_bet):
        roll = random.random()
        if facing_bet == 0:
            if roll < self.aggression * 0.65:
                # 隨機化下注尺寸 (33% 或 67%)
                size = round(pot * (0.33 if random.random() > 0.5 else 0.67), 1)
                return "Bet", max(size, 1.0)
            return "Check", 0
        else:
            if roll < self.fold_to_cbet:
                return "Fold", 0
            if roll < (1.0 - self.fold_to_cbet) * 0.8:
                return "Call", facing_bet
            return "Raise", facing_bet * 2.8

# ==========================================
# 4. Streamlit 介面與動態流程管理
# ==========================================
st.set_page_config(page_title="6-Max GTO Poker Trainer", layout="wide", page_icon="♠️")

POSITIONS_6MAX = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.button_index = 0
    st.session_state.hand_count = 1
    
    # 初始化 6 位玩家 (1 位 Hero + 5 位擬真機器人)
    st.session_state.bots = [
        RealisticBot("Bot 1 (HJ)", 'TAG (緊兇-常客)', 100),
        RealisticBot("Bot 2 (CO)", 'LAG (鬆兇-常客)', 100),
        RealisticBot("Bot 3 (BTN)", 'Calling Station (跟注站)', 100),
        RealisticBot("Bot 4 (SB)", 'Nit (石頭人)', 100),
        RealisticBot("Bot 5 (BB)", 'Maniac (狂人)', 100)
    ]
    st.session_state.hero_stack = 100
    st.session_state.deck = create_deck()
    st.session_state.stage = 'START'
    st.session_state.log = []

def start_new_hand():
    # 籌碼破產重置檢查 (Auto-reload)
    if st.session_state.hero_stack <= 0:
        st.session_state.hero_stack = 100
        st.session_state.log.append("🔄 Hero 籌碼已耗盡，已為你重新補充至 100 BB。")
        
    for bot in st.session_state.bots:
        if bot.stack <= 0:
            bot.stack = 100
            st.session_state.log.append(f"🔄 {bot.name} 籌碼耗盡，自動補滿至 100 BB。")
            
    # 輪換莊家位置
    st.session_state.button_index = (st.session_state.button_index + 1) % 6
    st.session_state.deck = create_deck()
    random.shuffle(st.session_state.deck)
    
    # 發牌
    st.session_state.hero_cards = [st.session_state.deck.pop(), st.session_state.deck.pop()]
    st.session_state.board = []
    st.session_state.pot = 1.5 # SB 0.5 + BB 1.0
    st.session_state.hero_pos = POSITIONS_6MAX[st.session_state.button_index]
    st.session_state.stage = 'PREFLOP'
    st.session_state.review_reports = []

# --- 側邊欄：牌桌動態後手與設定 ---
st.sidebar.title("🎰 牌桌動態後手 (No Rake)")
st.sidebar.caption(f"第 {st.session_state.hand_count} 手牌 | 盲注: 0.5 / 1.0 BB")

players_table = [{"玩家": "Hero (你)", "位置": st.session_state.get('hero_pos', 'UTG'), "後手 (BB)": f"{st.session_state.hero_stack:.1f}", "風格": "You"}]
for b in st.session_state.bots:
    players_table.append({"玩家": b.name, "位置": "動態", "後手 (BB)": f"{b.stack:.1f}", "風格": b.archetype})
st.sidebar.table(players_table)

if st.sidebar.button("重新洗牌 / 重置全部籌碼"):
    st.session_state.clear()
    st.rerun()

# --- 主遊戲區 ---
st.title("🃏 6-Max Cash Game GTO 教練系統")

if st.session_state.stage == 'START':
    st.info("點擊下方按鈕開始對局。盲注 0.5 / 1.0 BB，所有玩家 100BB 深度開始，籌碼動態增減。")
    if st.button("開始發牌", type="primary"):
        start_new_hand()
        st.rerun()

elif st.session_state.stage in ['PREFLOP', 'FLOP', 'SHOWDOWN']:
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.subheader("🎴 你的手牌")
        st.markdown(f"## `{st.session_state.hero_cards[0]}` `{st.session_state.hero_cards[1]}`")
        hand_cat = get_hand_category(st.session_state.hero_cards[0], st.session_state.hero_cards[1])
        st.write(f"手牌類別: **{hand_cat}** | 位置: **{st.session_state.hero_pos}**")
        st.write(f"你的當前後手: **{st.session_state.hero_stack:.1f} BB**")
        
    with c2:
        st.subheader("🎯 公共牌面 (Board)")
        board_disp = " ".join([f"`{c}`" for c in st.session_state.board]) if st.session_state.board else "_翻前階段尚無發牌_"
        st.markdown(f"### {board_disp}")
        texture = evaluate_board_texture(st.session_state.board)
        st.write(f"牌面結構: **{texture}** | 當前底池: **{st.session_state.pot:.1f} BB**")

    st.divider()

    # --- 行動控制台與 GTO 決策點 ---
    if st.session_state.stage == 'PREFLOP':
        st.subheader("翻前決策 (Preflop Action)")
        action = st.radio("選擇你的動作:", ['Fold', 'Call (1.0 BB)', 'Open Raise (2.5 BB)'], horizontal=True)
        
        if st.button("執行並獲取 GTO 覆盤"):
            # 翻前 GTO 覆盤生成
            gto_eval = analyze_preflop_gto(hand_cat, st.session_state.hero_pos)
            st.session_state.review_reports.append(gto_eval)
            
            if action == 'Fold':
                st.session_state.stage = 'SHOWDOWN'
                st.session_state.review_reports.append("ℹ️ 你選擇了 Fold。本局結束。")
            else:
                cost = 1.0 if 'Call' in action else 2.5
                st.session_state.hero_stack -= cost
                st.session_state.pot += cost
                # 發 Flop
                st.session_state.board = [st.session_state.deck.pop(), st.session_state.deck.pop(), st.session_state.deck.pop()]
                st.session_state.stage = 'FLOP'
            st.rerun()

    elif st.session_state.stage == 'FLOP':
        st.subheader("翻牌圈決策 (Flop C-bet / Defense)")
        texture = evaluate_board_texture(st.session_state.board)
        action = st.radio("你的行動:", ['Check', 'Bet 33% Pot', 'Bet 67% Pot', 'Overbet 125% Pot'], horizontal=True)
        
        if st.button("確認翻牌圈行動並覆盤"):
            # 翻後下注尺寸 GTO 覆盤生成
            if 'Bet' in action:
                pct = 0.33 if '33%' in action else (0.67 if '67%' in action else 1.25)
                bet_amt = round(st.session_state.pot * pct, 1)
                st.session_state.hero_stack -= bet_amt
                st.session_state.pot += bet_amt
                
                if "Dry" in texture:
                    if pct <= 0.35:
                        st.session_state.review_reports.append("🎯 **C-bet 尺寸評估 (優秀)**: 乾燥面上有顯著的『範圍優勢』，GTO 推薦使用 25%-33% 的小下注保持高頻率施壓。")
                    else:
                        st.session_state.review_reports.append("⚠️ **C-bet 尺寸評估 (不佳)**: 乾燥面上不需要打大注保護，超額下注會讓對手的邊緣跟注範圍輕易逃脫。")
                elif "Wet" in texture:
                    if pct >= 0.65:
                        st.session_state.review_reports.append("🎯 **C-bet 尺寸評估 (優秀)**: 濕滑面存在大量聽牌，GTO 傾向使用 66%-75% 較大尺寸建立堅果保護並剝奪對手賠率。")
                    else:
                        st.session_state.review_reports.append("⚠️ **C-bet 尺寸評估 (偏小)**: 33% 尺寸在動態面給予了對手極佳的隱含賠率去買順子/同花。")
            else:
                st.session_state.review_reports.append("🛡️ **Check 決策評估**: 在缺乏堅果優勢或屬於底池邊緣攤牌價值的牌力時，Check 控制底池完全符合 GTO 混合策略。")
            
            # 直接進 Showdown 結算
            st.session_state.stage = 'SHOWDOWN'
            st.rerun()

    elif st.session_state.stage == 'SHOWDOWN':
        st.subheader("🏁 牌局總結與 GTO / 剝削覆盤報告")
        
        # 顯示教練報告
        for rep in st.session_state.review_reports:
            st.markdown(rep)
            
        st.markdown("---")
        st.markdown("#### 📐 核心 GTO 數學公式核算")
        
        # MDF 公式與底池賠率展示
        st.markdown(r"""
        * **最低防守頻率 (MDF, Minimum Defense Frequency)**:
          $$\text{MDF} = \frac{\text{Pot}}{\text{Pot} + \text{Bet}}$$
          *用以防止對手使用 0 勝率的手牌進行任意無成本詐唬。*
        * **底池賠率 (Pot Odds)**:
          $$\text{Pot Odds} = \frac{\text{Call Amount}}{\text{Current Pot} + \text{Call Amount}}$$
          *你的手牌勝率（Equity）必須大於此數值，跟注才具備長期正期望值 ($+EV$)。*
        """)
        
        # 結算籌碼動態 (模擬給獲勝者或發下一把)
        if st.button("下一手牌 (繼續對局)", type="primary"):
            st.session_state.hand_count += 1
            # 簡單模擬：隨機將底池給予一位玩家，確保籌碼動態演變
            winner = random.choice(['Hero'] + [b.name for b in st.session_state.bots])
            if winner == 'Hero':
                st.session_state.hero_stack += st.session_state.pot
            else:
                for b in st.session_state.bots:
                    if b.name == winner:
                        b.stack += st.session_state.pot
                        break
            start_new_hand()
            st.rerun()
