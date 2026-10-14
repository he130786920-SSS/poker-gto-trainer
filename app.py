import streamlit as st
import random
import itertools
from collections import Counter

# ==========================================
# 1. 撲克底層算法 (Pure Python)
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
        return "Wet / Dynamic (濕滑動態面)"
    return "Dry / Static (乾燥乾燥面)"

# 6-Max No-Rake 100BB GTO 開牌基準線
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
        if RANK_VALUES[r1] >= std['pairs']:
            return "✅ **GTO 翻前評估**: 100% 頻率 Open Raise（具備絕佳純價值與強大攤牌勝率）。"
        return "⚠️ **GTO 翻前評估**: 邊緣口袋對子。在早中位容易遭遇 3-Bet 壓縮，建議棄牌或混合極低頻率防守。"
    if is_suited and r1 == 'A' and RANK_VALUES[r2] >= std['suited_ax']:
        return "✅ **GTO 翻前評估**: 100% Open Raise（同花 A 具備強大阻擋牌與 Nuts 同花潛力）。"
    if hand_cat in std['broadway_off'] or hand_cat in std.get('connectors', []):
        return "✅ **GTO 翻前評估**: 標準 Open Raise 範圍。"
    return "❌ **GTO 翻前評估**: 純負 EV 牌型，理論標準直接 Fold。"

def analyze_postflop_gto_slider(custom_bet, pot, board_texture):
    pct = (custom_bet / pot) * 100 if pot > 0 else 0
    feedback = []
    feedback.append(f"🎯 **你的實際下注**: **{custom_bet:.1f} BB**（相當於 **{pct:.1f}% 底池**）")

    # GTO 尺度吸附四捨五入算法
    if pct <= 45:
        target = "33% 底池 (小尺寸)"
        feedback.append(f"📌 **GTO 基準錨定**: 最接近 **{target}**。")
        if "Dry" in board_texture:
            feedback.append("💡 **理論解讀**: **非常優秀**。在乾燥面（如 K-8-2r），翻前進攻者擁有極高勝率優勢，GTO 建議用 25%-33% 的高頻率下注持續施壓邊緣牌。")
        else:
            feedback.append("⚠️ **理論解讀**: **尺寸偏小**。在濕滑動態面（如 J-T-8 雙花），小下注給予了對手高達 1:4 以上的極佳買牌賠率，難以保護你的價值範圍。")
    elif pct <= 90:
        target = "67% - 75% 底池 (標準大尺寸)"
        feedback.append(f"📌 **GTO 基準錨定**: 最接近 **{target}**。")
        if "Wet" in board_texture:
            feedback.append("💡 **理論解讀**: **非常優秀**。濕滑牌面需要使用 66%-75% 尺寸建立『堅果保護』，既能剝奪對手追花追順的隱含賠率，又能最大化強成牌的價值。")
        else:
            feedback.append("⚠️ **理論解讀**: **略微過大**。在乾燥面上不需要如此昂貴的保護，過大尺寸會把對手所有的弱牌打蓋，只留下比你強的牌跟注。")
    else:
        target = "125%+ 底池 (超池 Overbet)"
        feedback.append(f"📌 **GTO 基準錨定**: 最接近 **{target}**。")
        feedback.append("💡 **理論解讀**: **極化打法（Polarized Strategy）**。GTO 只會在你在牌面具有顯著『堅果優勢（Nut Advantage）』時才進行超池下注。如果對手是個棄牌率極高的緊弱玩家（Nit），這也是個高收益的剝削型詐唬尺寸！")

    return feedback

# ==========================================
# 2. 擬真隨機偏離機器人 (Realistic Bots)
# ==========================================
class RealisticBot:
    def __init__(self, name, archetype, stack=100):
        self.name = name
        self.archetype = archetype
        self.stack = float(stack)
        self.current_bet = 0.0
        jitter = lambda: random.uniform(-0.05, 0.05)
        if 'TAG' in archetype:
            self.vpip, self.agg = 0.20 + jitter(), 0.65
        elif 'LAG' in archetype:
            self.vpip, self.agg = 0.30 + jitter(), 0.80
        elif 'Station' in archetype:
            self.vpip, self.agg = 0.45 + jitter(), 0.20
        elif 'Nit' in archetype:
            self.vpip, self.agg = 0.12 + jitter(), 0.30
        else: # Maniac
            self.vpip, self.agg = 0.50 + jitter(), 0.90

# ==========================================
# 3. 牌局 Session 狀態控管
# ==========================================
st.set_page_config(page_title="GTO 擬真撲克競技訓練器", layout="wide", page_icon="♠️")

POSITIONS = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']

if 'hand_count' not in st.session_state:
    st.session_state.hand_count = 1
    st.session_state.btn_pos_idx = 0
    st.session_state.hero_stack = 100.0
    st.session_state.hero_current_bet = 0.0
    st.session_state.bots = [
        RealisticBot("Bot 1 (TAG)", "TAG (緊兇常客)", 100.0),
        RealisticBot("Bot 2 (LAG)", "LAG (鬆兇玩家)", 100.0),
        RealisticBot("Bot 3 (Station)", "Calling Station (跟注站)", 100.0),
        RealisticBot("Bot 4 (Nit)", "Nit (極緊石頭人)", 100.0),
        RealisticBot("Bot 5 (Maniac)", "Maniac (狂暴玩家)", 100.0)
    ]
    st.session_state.stage = 'INIT'
    st.session_state.review_reports = []

def start_new_hand():
    # 破產自動補至 100BB
    if st.session_state.hero_stack <= 0:
        st.session_state.hero_stack = 100.0
    for b in st.session_state.bots:
        if b.stack <= 0:
            b.stack = 100.0

    st.session_state.deck = create_deck()
    random.shuffle(st.session_state.deck)
    st.session_state.hero_cards = [st.session_state.deck.pop(), st.session_state.deck.pop()]
    st.session_state.board = []
    st.session_state.review_reports = []
    
    # 輪轉位置
    st.session_state.btn_pos_idx = (st.session_state.btn_pos_idx + 1) % 6
    st.session_state.hero_pos = POSITIONS[st.session_state.btn_pos_idx]
    
    # 盲注設定 (SB: 0.5 BB, BB: 1.0 BB)
    st.session_state.pot = 1.5
    st.session_state.hero_current_bet = 0.0
    for b in st.session_state.bots:
        b.current_bet = 0.0

    # 模擬盲注扣除
    if st.session_state.hero_pos == 'SB':
        st.session_state.hero_current_bet = 0.5
        st.session_state.hero_stack -= 0.5
    elif st.session_state.hero_pos == 'BB':
        st.session_state.hero_current_bet = 1.0
        st.session_state.hero_stack -= 1.0
        
    st.session_state.stage = 'PREFLOP'

if st.session_state.stage == 'INIT':
    start_new_hand()

# ==========================================
# 4. GGPoker 風格牌桌 UI (純 CSS 渲染)
# ==========================================
def render_card_html(card):
    suit = card[-1]
    rank = card[:-1]
    color = "#e53e3e" if suit in ['♥', '♦'] else "#1a202c"
    return f"""
    <div style="display:inline-block; width:48px; height:68px; background:#ffffff; border-radius:6px; 
                border:1px solid #718096; margin:2px; font-weight:bold; font-size:18px; 
                line-height:68px; text-align:center; color:{color}; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        {rank}{suit}
    </div>
    """

board_html = "".join([render_card_html(c) for c in st.session_state.board]) if st.session_state.board else "<span style='color:#a0aec0; font-size:14px;'>等待翻牌發出...</span>"
hero_cards_html = "".join([render_card_html(c) for c in st.session_state.hero_cards])

# 6 個座位在橢圓桌的相對佈局
table_html = f"""
<div style="background-color:#121212; padding:20px; border-radius:16px;">
  <div style="
    position: relative;
    width: 100%;
    max-width: 850px;
    height: 480px;
    margin: 0 auto;
    background: radial-gradient(circle, #1e4d2b 0%, #0d2818 85%, #05140b 100%);
    border: 14px solid #3c2415;
    border-radius: 220px;
    box-shadow: inset 0 0 40px rgba(0,0,0,0.9), 0 10px 25px rgba(0,0,0,0.8);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  ">
    <!-- 中央底池與公牌區 -->
    <div style="position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
      <div style="background: rgba(0,0,0,0.7); padding: 5px 16px; border-radius: 20px; color: #f6e05e; font-weight:bold; font-size:16px; border: 1px solid #d69e2e; margin-bottom: 8px; display:inline-block;">
        🪙 Total Pot: {st.session_state.pot:.1f} BB
      </div>
      <div>{board_html}</div>
    </div>

    <!-- 座位 1 (Top Left) -->
    <div style="position: absolute; top: 8%; left: 18%; text-align: center;">
      <div style="color: #68d391; font-weight: bold; font-size: 13px;">{st.session_state.bots[0].current_bet:.1f} BB 🟡</div>
      <div style="background: #1a202c; border: 2px solid #4a5568; border-radius: 8px; padding: 4px 10px; color: white;">
        <span style="background: #e2e8f0; color: black; border-radius: 4px; padding: 1px 4px; font-size: 10px; font-weight: bold;">HJ</span> {st.session_state.bots[0].name.split()[0]}
        <div style="color: #ecc94b; font-weight: bold; font-size: 12px;">{st.session_state.bots[0].stack:.1f} BB</div>
      </div>
    </div>

    <!-- 座位 2 (Top Center) -->
    <div style="position: absolute; top: 4%; left: 45%; text-align: center;">
      <div style="color: #68d391; font-weight: bold; font-size: 13px;">{st.session_state.bots[1].current_bet:.1f} BB 🟡</div>
      <div style="background: #1a202c; border: 2px solid #4a5568; border-radius: 8px; padding: 4px 10px; color: white;">
        <span style="background: #e2e8f0; color: black; border-radius: 4px; padding: 1px 4px; font-size: 10px; font-weight: bold;">CO</span> {st.session_state.bots[1].name.split()[0]}
        <div style="color: #ecc94b; font-weight: bold; font-size: 12px;">{st.session_state.bots[1].stack:.1f} BB</div>
      </div>
    </div>

    <!-- 座位 3 (Top Right) -->
    <div style="position: absolute; top: 8%; right: 18%; text-align: center;">
      <div style="color: #68d391; font-weight: bold; font-size: 13px;">{st.session_state.bots[2].current_bet:.1f} BB 🟡</div>
      <div style="background: #1a202c; border: 2px solid #4a5568; border-radius: 8px; padding: 4px 10px; color: white;">
        <span style="background: #e2e8f0; color: black; border-radius: 4px; padding: 1px 4px; font-size: 10px; font-weight: bold;">BTN</span> {st.session_state.bots[2].name.split()[0]}
        <div style="color: #ecc94b; font-weight: bold; font-size: 12px;">{st.session_state.bots[2].stack:.1f} BB</div>
      </div>
    </div>

    <!-- 座位 4 (Bottom Right) -->
    <div style="position: absolute; bottom: 12%; right: 12%; text-align: center;">
      <div style="color: #68d391; font-weight: bold; font-size: 13px;">{st.session_state.bots[3].current_bet:.1f} BB 🟡</div>
      <div style="background: #1a202c; border: 2px solid #4a5568; border-radius: 8px; padding: 4px 10px; color: white;">
        <span style="background: #e2e8f0; color: black; border-radius: 4px; padding: 1px 4px; font-size: 10px; font-weight: bold;">SB</span> {st.session_state.bots[3].name.split()[0]}
        <div style="color: #ecc94b; font-weight: bold; font-size: 12px;">{st.session_state.bots[3].stack:.1f} BB</div>
      </div>
    </div>

    <!-- 座位 5 (Bottom Left) -->
    <div style="position: absolute; bottom: 12%; left: 12%; text-align: center;">
      <div style="color: #68d391; font-weight: bold; font-size: 13px;">{st.session_state.bots[4].current_bet:.1f} BB 🟡</div>
      <div style="background: #1a202c; border: 2px solid #4a5568; border-radius: 8px; padding: 4px 10px; color: white;">
        <span style="background: #e2e8f0; color: black; border-radius: 4px; padding: 1px 4px; font-size: 10px; font-weight: bold;">BB</span> {st.session_state.bots[4].name.split()[0]}
        <div style="color: #ecc94b; font-weight: bold; font-size: 12px;">{st.session_state.bots[4].stack:.1f} BB</div>
      </div>
    </div>

    <!-- HERO 玩家席位 (Bottom Center - 正下方) -->
    <div style="position: absolute; bottom: -8px; left: 50%; transform: translateX(-50%); text-align: center;">
      <div style="color: #48bb78; font-weight: bold; font-size: 14px; text-shadow: 0 1px 3px black;">
        {f'下注: {st.session_state.hero_current_bet:.1f} BB' if st.session_state.hero_current_bet > 0 else 'CHECK'}
      </div>
      <div>{hero_cards_html}</div>
      <div style="background: #2d3748; border: 2px solid #ecc94b; border-radius: 8px; padding: 4px 16px; color: white; display:inline-block; margin-top:-5px;">
        <span style="background: #ecc94b; color: black; border-radius: 4px; padding: 1px 6px; font-size: 11px; font-weight: bold;">{st.session_state.hero_pos}</span> <strong>HERO (你)</strong>
        <div style="color: #48bb78; font-weight: bold; font-size: 13px;">{st.session_state.hero_stack:.1f} BB</div>
      </div>
    </div>
  </div>
</div>
"""
st.markdown(table_html, unsafe_allow_html=True)
st.write("")

# ==========================================
# 5. 操作控制台與下注滑桿 (Controls)
# ==========================================
hand_cat = get_hand_category(st.session_state.hero_cards[0], st.session_state.hero_cards[1])
texture = evaluate_board_texture(st.session_state.board)

if st.session_state.stage == 'PREFLOP':
    st.subheader(f"🎮 翻前輪到你行動 (位置: {st.session_state.hero_pos} | 手牌類別: {hand_cat})")
    col_act, col_slider = st.columns([1, 2])
    
    with col_act:
        pf_action = st.radio("你的決策:", ['Fold', 'Call (1.0 BB)', 'Open Raise'], horizontal=True)
        
    with col_slider:
        if pf_action == 'Open Raise':
            raise_size = st.slider("選擇加注尺寸 (BB):", min_value=2.0, max_value=min(10.0, float(st.session_state.hero_stack)), value=2.5, step=0.5)
        else:
            st.info("點擊下方確認按鈕推進手牌。")

    if st.button("確認翻前行動", type="primary"):
        gto_eval = analyze_preflop_gto(hand_cat, st.session_state.hero_pos)
        st.session_state.review_reports.append(gto_eval)
        
        if pf_action == 'Fold':
            st.session_state.stage = 'SHOWDOWN'
            st.session_state.review_reports.append("ℹ️ 你選擇了 Fold。本局提前結束。")
        else:
            cost = 1.0 if 'Call' in pf_action else raise_size
            st.session_state.hero_stack -= cost
            st.session_state.pot += cost
            st.session_state.hero_current_bet = cost
            # 發出翻牌 3 張
            st.session_state.board = [st.session_state.deck.pop(), st.session_state.deck.pop(), st.session_state.deck.pop()]
            st.session_state.stage = 'FLOP'
        st.rerun()

elif st.session_state.stage == 'FLOP':
    st.subheader(f"🎮 翻牌圈決策 (牌面結構: {texture})")
    col_act, col_slider = st.columns([1, 2])
    
    with col_act:
        flop_action = st.radio("選擇行動:", ['Check', 'C-bet 下注'], horizontal=True)
        
    with col_slider:
        if flop_action == 'C-bet 下注':
            # 支援滑桿無級別選擇，並即時顯示換算成 % Pot
            max_bet = float(min(st.session_state.hero_stack, st.session_state.pot * 2.5))
            cbet_val = st.slider("C-bet 尺寸 (BB):", min_value=1.0, max_value=max_bet, value=round(st.session_state.pot * 0.33, 1), step=0.5)
            pct_pot = (cbet_val / st.session_state.pot) * 100
            st.caption(f"⚡ 當前選擇相當於底池的 **{pct_pot:.1f}%**")

    if st.button("確認翻牌圈行動並取得 GTO 分析", type="primary"):
        if flop_action == 'C-bet 下注':
            st.session_state.hero_stack -= cbet_val
            st.session_state.pot += cbet_val
            st.session_state.hero_current_bet = cbet_val
            cbet_evals = analyze_postflop_gto_slider(cbet_val, st.session_state.pot - cbet_val, texture)
            st.session_state.review_reports.extend(cbet_evals)
        else:
            st.session_state.hero_current_bet = 0.0
            st.session_state.review_reports.append("🛡️ **Check 決策評估**: 控制底池完全符合 GTO 混合策略。當手牌沒有堅果優勢時，過牌是標準防守線。")

        st.session_state.stage = 'SHOWDOWN'
        st.rerun()

elif st.session_state.stage == 'SHOWDOWN':
    st.markdown("### 🧠 GTO 教練覆盤與剝削指導")
    for r in st.session_state.review_reports:
        st.markdown(r)
        
    st.divider()
    if st.button("下一手牌 (繼續對局)", type="primary"):
        st.session_state.hand_count += 1
        # 模擬分配底池（若有下注且未棄牌，Hero 依勝率拿回或隨機結算籌碼動態）
        st.session_state.hero_stack += st.session_state.pot
        start_new_hand()
        st.rerun()
