"""
game_logic.py — Splendor 完整遊戲規則引擎
包含牌庫定義、狀態管理、合法動作驗證、勝利判斷
"""
from __future__ import annotations
import random
import copy
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
# 常數定義
# ─────────────────────────────────────────────
GEMS = ["white", "blue", "green", "red", "black"]
GOLD = "gold"
ALL_GEMS = GEMS + [GOLD]

GEMS_PER_COLOR_2P = 4   # 2人局每色寶石數量
GEMS_PER_COLOR_3P = 5
GEMS_PER_COLOR_4P = 7
GOLD_COUNT = 5
WIN_SCORE = 15
MAX_HAND = 3            # 保留手牌上限

# ─────────────────────────────────────────────
# 發展卡資料（完整90張）
# level, color, points, cost: {white, blue, green, red, black}
# ─────────────────────────────────────────────
def _make_deck() -> list[dict]:
    """
    完整90張發展卡牌庫。
    資料來源：bouk/splendimax CSV + mcandocia/splendor_ai CSV + Google Sheets
    三方交叉驗證，與實體遊戲完全一致。
    欄位順序：level, color, points, cost(white, blue, green, red, black)
    """
    raw = [
        # ── Level 1：黑色加成 ──
        (1,"black",0, 1,1,1,1,0),
        (1,"black",0, 1,2,1,1,0),
        (1,"black",0, 2,2,0,1,0),
        (1,"black",0, 0,0,1,3,1),
        (1,"black",0, 0,0,2,1,0),
        (1,"black",0, 2,0,2,0,0),
        (1,"black",0, 0,0,3,0,0),
        (1,"black",1, 0,4,0,0,0),
        # ── Level 1：藍色加成 ──
        (1,"blue",0,  1,0,1,1,1),
        (1,"blue",0,  1,0,1,2,1),
        (1,"blue",0,  1,0,2,2,0),
        (1,"blue",0,  0,1,3,1,0),
        (1,"blue",0,  1,0,0,0,2),
        (1,"blue",0,  0,0,2,0,2),
        (1,"blue",0,  0,0,0,0,3),
        (1,"blue",1,  0,0,0,4,0),
        # ── Level 1：白色加成 ──
        (1,"white",0, 0,1,1,1,1),
        (1,"white",0, 0,1,2,1,1),
        (1,"white",0, 0,2,2,0,1),
        (1,"white",0, 3,1,0,0,1),
        (1,"white",0, 0,0,0,2,1),
        (1,"white",0, 0,2,0,0,2),
        (1,"white",0, 0,3,0,0,0),
        (1,"white",1, 0,0,4,0,0),
        # ── Level 1：綠色加成 ──
        (1,"green",0, 1,1,0,1,1),
        (1,"green",0, 1,1,0,1,2),
        (1,"green",0, 0,1,0,2,2),
        (1,"green",0, 1,3,1,0,0),
        (1,"green",0, 2,1,0,0,0),
        (1,"green",0, 0,2,0,2,0),
        (1,"green",0, 0,0,0,3,0),
        (1,"green",1, 0,0,0,0,4),
        # ── Level 1：紅色加成 ──
        (1,"red",0,   1,1,1,0,1),
        (1,"red",0,   2,1,1,0,1),
        (1,"red",0,   2,0,1,0,2),
        (1,"red",0,   1,0,0,1,3),
        (1,"red",0,   0,2,1,0,0),
        (1,"red",0,   2,0,0,2,0),
        (1,"red",0,   3,0,0,0,0),
        (1,"red",1,   4,0,0,0,0),

        # ── Level 2：黑色加成 ──
        (2,"black",1, 3,2,2,0,0),
        (2,"black",1, 3,0,3,0,2),
        (2,"black",2, 0,1,4,2,0),
        (2,"black",2, 0,0,5,3,0),
        (2,"black",2, 5,0,0,0,0),
        (2,"black",3, 0,0,0,0,6),
        # ── Level 2：藍色加成 ──
        (2,"blue",1,  0,2,2,3,0),
        (2,"blue",1,  0,2,3,0,3),
        (2,"blue",2,  5,3,0,0,0),
        (2,"blue",2,  2,0,0,1,4),
        (2,"blue",2,  0,5,0,0,0),
        (2,"blue",3,  0,6,0,0,0),
        # ── Level 2：白色加成 ──
        (2,"white",1, 0,0,3,2,2),
        (2,"white",1, 2,3,0,3,0),
        (2,"white",2, 0,0,1,4,2),
        (2,"white",2, 0,0,0,5,3),
        (2,"white",2, 0,0,0,5,0),
        (2,"white",3, 6,0,0,0,0),
        # ── Level 2：綠色加成 ──
        (2,"green",1, 3,0,2,3,0),
        (2,"green",1, 2,3,0,0,2),
        (2,"green",2, 4,2,0,0,1),
        (2,"green",2, 0,5,3,0,0),
        (2,"green",2, 0,0,5,0,0),
        (2,"green",3, 0,0,6,0,0),
        # ── Level 2：紅色加成 ──
        (2,"red",1,   2,0,0,2,3),
        (2,"red",1,   0,3,0,2,3),
        (2,"red",2,   1,4,2,0,0),
        (2,"red",2,   3,0,0,0,5),
        (2,"red",2,   0,0,0,0,5),
        (2,"red",3,   0,0,0,6,0),

        # ── Level 3：黑色加成 ──
        (3,"black",3, 3,3,5,3,0),
        (3,"black",4, 0,0,0,7,0),
        (3,"black",4, 0,0,3,6,3),
        (3,"black",5, 0,0,0,7,3),
        # ── Level 3：藍色加成 ──
        (3,"blue",3,  3,0,3,3,5),
        (3,"blue",4,  7,0,0,0,0),
        (3,"blue",4,  6,3,0,0,3),
        (3,"blue",5,  7,3,0,0,0),
        # ── Level 3：白色加成 ──
        (3,"white",3, 0,3,3,5,3),
        (3,"white",4, 0,0,0,0,7),
        (3,"white",4, 3,0,0,3,6),
        (3,"white",5, 3,0,0,0,7),
        # ── Level 3：綠色加成 ──
        (3,"green",3, 5,3,0,3,3),
        (3,"green",4, 0,7,0,0,0),
        (3,"green",4, 3,6,3,0,0),
        (3,"green",5, 0,7,3,0,0),
        # ── Level 3：紅色加成 ──
        (3,"red",3,   3,5,3,0,3),
        (3,"red",4,   0,0,7,0,0),
        (3,"red",4,   0,3,6,3,0),
        (3,"red",5,   0,0,7,3,0),
    ]

    cards = []
    for cid, (level, color, pts, w, u, g, r, k) in enumerate(raw):
        cards.append({
            "id": cid,
            "level": level,
            "color": color,
            "points": pts,
            "cost": {"white": w, "blue": u, "green": g, "red": r, "black": k},
        })
    return cards


# ─────────────────────────────────────────────
# 貴族牌資料（官方完整10張）
# 需求為已購卡的顏色張數，勝利點數均為3分
# 資料來源：官方規則書，與實體遊戲一致
# ─────────────────────────────────────────────
def _make_nobles() -> list[dict]:
    """
    官方10張貴族牌，每局隨機取(玩家數+1)張。
    requirement 欄位為需要的各色卡張數（非寶石）。
    """
    raw = [
        # (white, blue, green, red, black)
        (0, 0, 3, 3, 3),   # 馬基維利
        (0, 4, 0, 0, 4),   # 瑪麗·斯圖亞特
        (0, 4, 4, 0, 0),   # 查理五世
        (3, 0, 0, 3, 3),   # 奧地利的安妮
        (3, 3, 3, 0, 0),   # 卡斯提亞的伊莎貝拉
        (0, 0, 4, 4, 0),   # 蘇萊曼大帝
        (4, 0, 0, 4, 0),   # 凱薩琳·梅迪奇
        (4, 0, 0, 0, 4),   # 法蘭西斯一世
        (4, 4, 0, 0, 0),   # 奧地利的伊麗莎白
        (3, 0, 3, 0, 3),   # 瑪麗·梅迪奇
    ]
    nobles = []
    for nid, (w, u, g, r, k) in enumerate(raw):
        nobles.append({
            "id": nid,
            "points": 3,
            "requirement": {"white": w, "blue": u, "green": g, "red": r, "black": k},
        })
    return nobles


ALL_CARDS = _make_deck()
ALL_NOBLES = _make_nobles()


# ─────────────────────────────────────────────
# 玩家狀態
# ─────────────────────────────────────────────
class Player:
    def __init__(self, player_id: int, name: str):
        self.player_id = player_id
        self.name = name
        self.gems: dict[str, int] = {g: 0 for g in ALL_GEMS}
        self.cards: list[dict] = []        # 已購買的發展卡
        self.reserved: list[dict] = []     # 保留手牌（上限3）
        self.nobles: list[dict] = []       # 已到訪的貴族
        self.score: int = 0

    def gem_bonus(self) -> dict[str, int]:
        """計算已購卡提供的永久折扣（每色卡的張數）"""
        bonus = {g: 0 for g in GEMS}
        for card in self.cards:
            bonus[card["color"]] += 1
        return bonus

    def total_gems(self) -> int:
        return sum(self.gems[g] for g in ALL_GEMS)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "gems": dict(self.gems),
            "cards": list(self.cards),
            "reserved": list(self.reserved),
            "nobles": list(self.nobles),
            "score": self.score,
            "gem_bonus": self.gem_bonus(),
        }


# ─────────────────────────────────────────────
# 遊戲狀態
# ─────────────────────────────────────────────
class GameState:
    def __init__(self, mode: str = "pve", difficulty: str = "medium", seed: Optional[int] = None):
        """
        mode: 'pvp' 或 'pve'
        difficulty: 'easy' / 'medium' / 'hard'（僅 pve 有效）
        """
        self.mode = mode
        self.difficulty = difficulty
        self.rng = random.Random(seed)

        # 牌庫
        deck = copy.deepcopy(ALL_CARDS)
        self.rng.shuffle(deck)
        self.deck_l1 = [c for c in deck if c["level"] == 1]
        self.deck_l2 = [c for c in deck if c["level"] == 2]
        self.deck_l3 = [c for c in deck if c["level"] == 3]

        # 場上發展卡（每排4張）
        self.board: dict[int, list[Optional[dict]]] = {
            1: [self.deck_l1.pop() if self.deck_l1 else None for _ in range(4)],
            2: [self.deck_l2.pop() if self.deck_l2 else None for _ in range(4)],
            3: [self.deck_l3.pop() if self.deck_l3 else None for _ in range(4)],
        }

        # 貴族牌（2人局：3張）
        nobles_pool = copy.deepcopy(ALL_NOBLES)
        self.rng.shuffle(nobles_pool)
        num_nobles = 3  # 2人局
        self.nobles: list[dict] = nobles_pool[:num_nobles]

        # 寶石銀行（2人局每色4顆）
        gems_count = GEMS_PER_COLOR_2P
        self.bank: dict[str, int] = {g: gems_count for g in GEMS}
        self.bank[GOLD] = GOLD_COUNT

        # 玩家
        self.players = [
            Player(0, "玩家一"),
            Player(1, "玩家二" if mode == "pvp" else "AI"),
        ]
        self.current_player_idx = 0
        self.turn = 1
        self.game_over = False
        self.winner_id: Optional[int] = None
        self.last_round_trigger: Optional[int] = None  # 誰觸發了最後一輪
        self.action_log: list[str] = []

    # ── 屬性 ──────────────────────────────────
    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_idx]

    # ── 牌庫補牌 ──────────────────────────────
    def _refill_board(self, level: int, slot: int):
        deck = {1: self.deck_l1, 2: self.deck_l2, 3: self.deck_l3}[level]
        self.board[level][slot] = deck.pop() if deck else None

    # ── 貴族自動到訪 ──────────────────────────
    def _check_nobles(self, player: Player) -> list[dict]:
        """檢查並結算玩家可獲得的貴族（若多張則取第一張符合的）"""
        bonus = player.gem_bonus()
        visited = []
        for noble in list(self.nobles):
            req = noble["requirement"]
            if all(bonus.get(g, 0) >= req.get(g, 0) for g in GEMS):
                player.nobles.append(noble)
                player.score += noble["points"]
                self.nobles.remove(noble)
                visited.append(noble)
                break  # 每回合最多一位貴族
        return visited

    # ── 勝利判斷 ──────────────────────────────
    def _check_win_trigger(self, player: Player):
        """若玩家達到15分，觸發最後一輪"""
        if player.score >= WIN_SCORE and self.last_round_trigger is None:
            self.last_round_trigger = player.player_id

    def _finalize_if_last_round(self):
        """
        最後一輪：讓每位玩家都能在同一輪結束，
        然後由分數最高者勝（同分則購卡數少者勝）
        """
        if self.last_round_trigger is None:
            return
        # 等到玩家0（先手）即將開始下一輪時結算
        if self.current_player_idx == 0:
            # 結算
            best = max(
                self.players,
                key=lambda p: (p.score, -len(p.cards))
            )
            self.winner_id = best.player_id
            self.game_over = True

    # ── 驗證：拿寶石 ──────────────────────────
    def _validate_take_gems(self, player: Player, gems: dict[str, int]) -> Optional[str]:
        """
        合法的拿寶石動作：
        (a) 拿3顆不同色（每色1顆，不含黃金）
        (b) 拿2顆同色（該色銀行≥4顆）
        玩家拿完後上限10顆，超出需歸還。
        """
        colors = [g for g, cnt in gems.items() if cnt > 0]
        if GOLD in colors:
            return "不能直接拿黃金寶石"

        # 檢查合法模式
        total_take = sum(gems.values())
        if total_take == 3:
            if len(colors) != 3:
                return "拿3顆必須選3種不同顏色"
            for g in colors:
                if gems[g] != 1:
                    return "拿3顆時每色只能拿1顆"
                if self.bank.get(g, 0) < 1:
                    return f"銀行 {g} 寶石不足"
        elif total_take == 2:
            if len(colors) != 1:
                return "拿2顆必須是同一種顏色"
            g = colors[0]
            if gems[g] != 2:
                return "拿2顆同色需要剛好2顆"
            if self.bank.get(g, 0) < 4:
                return f"銀行 {g} 寶石不足4顆，無法拿2顆"
        elif total_take == 1:
            # 允許只拿1顆（銀行某色不夠3顆時的合法變體）
            g = colors[0]
            if self.bank.get(g, 0) < 1:
                return f"銀行 {g} 寶石不足"
        else:
            return f"無效的寶石數量：{total_take}"

        return None

    # ── 驗證：保留卡 ──────────────────────────
    def _validate_reserve(self, player: Player, card_id: Optional[int],
                          level: Optional[int]) -> Optional[str]:
        if len(player.reserved) >= MAX_HAND:
            return "保留手牌已達上限（3張）"
        if card_id is None and level is None:
            return "必須指定保留的卡片或牌堆"
        if card_id is not None:
            card = self._find_board_card(card_id)
            if card is None:
                return "場上找不到該卡片"
        return None

    # ── 驗證：購買卡 ──────────────────────────
    def _validate_buy(self, player: Player, card_id: int) -> Optional[str]:
        card = self._find_buyable_card(player, card_id)
        if card is None:
            return "找不到可購買的卡片（場上或手牌）"
        if not self._can_afford(player, card):
            cost = self._effective_cost(player, card)
            gold_short = cost[GOLD] - player.gems[GOLD]
            return f"寶石不足，還差 {gold_short} 顆黃金（萬用幣）"
        return None

    # ── 輔助：尋找卡片 ──────────────────────────
    def _find_board_card(self, card_id: int) -> Optional[dict]:
        for level in [1, 2, 3]:
            for card in self.board[level]:
                if card and card["id"] == card_id:
                    return card
        return None

    def _find_board_slot(self, card_id: int) -> Optional[tuple[int, int]]:
        for level in [1, 2, 3]:
            for i, card in enumerate(self.board[level]):
                if card and card["id"] == card_id:
                    return (level, i)
        return None

    def _find_buyable_card(self, player: Player, card_id: int) -> Optional[dict]:
        """找場上或保留手牌中的卡"""
        board_card = self._find_board_card(card_id)
        if board_card:
            return board_card
        for card in player.reserved:
            if card["id"] == card_id:
                return card
        return None

    # ── 計算實際費用（扣掉折扣）─────────────
    def _effective_cost(self, player: Player, card: dict) -> dict[str, int]:
        """
        回傳玩家購買該卡需支付的各色寶石數量。
        先扣折扣（已購卡），不足用黃金補，最終可能為負（代表有多餘折扣）。
        回傳 {color: 需支付數量（已含黃金分配）, "gold": 需用黃金數}
        """
        bonus = player.gem_bonus()
        cost = {}
        gold_needed = 0
        for g in GEMS:
            raw = card["cost"].get(g, 0)
            after_bonus = raw - bonus.get(g, 0)
            after_gems = after_bonus - player.gems.get(g, 0)
            if after_bonus <= 0:
                cost[g] = 0
            elif player.gems.get(g, 0) >= after_bonus:
                cost[g] = after_bonus
            else:
                cost[g] = player.gems.get(g, 0)
                gold_needed += max(0, after_gems)
        cost[GOLD] = gold_needed
        return cost

    def _can_afford(self, player: Player, card: dict) -> bool:
        """
        計算購買費用：先扣折扣（已購卡 bonus），再扣玩家手上的彩色寶石，
        剩餘缺口必須由黃金（萬用幣）補足。
        若黃金不夠，即負擔不起。
        """
        bonus = player.gem_bonus()
        gold_needed = 0
        for g in GEMS:
            raw        = card["cost"].get(g, 0)
            after_disc = raw - bonus.get(g, 0)          # 折扣後需求
            if after_disc <= 0:
                continue
            have = player.gems.get(g, 0)
            if have < after_disc:
                gold_needed += after_disc - have         # 缺口補黃金
        return gold_needed <= player.gems.get(GOLD, 0)

    # ── 公開：驗證動作 ─────────────────────────
    def validate_action(self, action: dict) -> Optional[str]:
        """
        驗證動作合法性，回傳錯誤訊息（None = 合法）。
        action 格式：
          {"type": "take_gems", "gems": {"white":1,"blue":1,"green":1}}
          {"type": "reserve",   "card_id": 5}  或  {"type": "reserve", "level": 2}
          {"type": "buy",       "card_id": 12}
          {"type": "discard",   "gems": {"white":1,...}}  （超出10顆時）
        """
        if self.game_over:
            return "遊戲已結束"
        player = self.current_player
        t = action.get("type")
        if t == "take_gems":
            return self._validate_take_gems(player, action.get("gems", {}))
        elif t == "reserve":
            return self._validate_reserve(player,
                                          action.get("card_id"),
                                          action.get("level"))
        elif t == "buy":
            return self._validate_buy(player, action.get("card_id"))
        else:
            return f"未知動作類型：{t}"

    # ── 公開：執行動作 ─────────────────────────
    def apply_action(self, action: dict) -> dict:
        """
        執行動作並推進遊戲狀態。
        回傳 {"ok": True, "nobles_visited": [...], "game_over": bool}
        """
        err = self.validate_action(action)
        if err:
            return {"ok": False, "error": err}

        player = self.current_player
        t = action["type"]
        nobles_visited = []

        if t == "take_gems":
            gems = action["gems"]
            for g, cnt in gems.items():
                player.gems[g] = player.gems.get(g, 0) + cnt
                self.bank[g] -= cnt
            self.action_log.append(
                f"玩家{player.player_id} 拿了寶石: {gems}"
            )

        elif t == "reserve":
            card_id = action.get("card_id")
            level = action.get("level")
            if card_id is not None:
                slot_info = self._find_board_slot(card_id)
                if slot_info:
                    lv, idx = slot_info
                    card = self.board[lv][idx]
                    self.board[lv][idx] = None
                    self._refill_board(lv, idx)
                else:
                    return {"ok": False, "error": "找不到該卡"}
            else:
                # 從牌堆頂保留
                deck = {1: self.deck_l1, 2: self.deck_l2, 3: self.deck_l3}[level]
                if not deck:
                    return {"ok": False, "error": f"等級{level}牌堆已空"}
                card = deck.pop()

            player.reserved.append(card)
            # 拿黃金
            if self.bank[GOLD] > 0:
                player.gems[GOLD] += 1
                self.bank[GOLD] -= 1
            self.action_log.append(
                f"玩家{player.player_id} 保留了卡片 {card['id']}"
            )

        elif t == "buy":
            card_id = action["card_id"]
            card = self._find_buyable_card(player, card_id)
            cost = self._effective_cost(player, card)

            # 扣除寶石
            for g in GEMS:
                player.gems[g] -= cost.get(g, 0)
                self.bank[g] += cost.get(g, 0)
            gold_used = cost.get(GOLD, 0)
            player.gems[GOLD] -= gold_used
            self.bank[GOLD] += gold_used

            # 移除卡片
            board_slot = self._find_board_slot(card_id)
            if board_slot:
                lv, idx = board_slot
                self.board[lv][idx] = None
                self._refill_board(lv, idx)
            else:
                # 從保留手牌移除
                player.reserved = [c for c in player.reserved if c["id"] != card_id]

            player.cards.append(card)
            player.score += card["points"]
            self.action_log.append(
                f"玩家{player.player_id} 購買了卡片 {card['id']} ({card['color']} {card['points']}分)"
            )

        # 貴族到訪
        nobles_visited = self._check_nobles(player)

        # 檢查觸發勝利
        self._check_win_trigger(player)

        # 切換玩家
        self.current_player_idx = 1 - self.current_player_idx
        if self.current_player_idx == 0:
            self.turn += 1

        # 判斷最後一輪是否結束
        self._finalize_if_last_round()

        return {
            "ok": True,
            "nobles_visited": nobles_visited,
            "game_over": self.game_over,
            "winner_id": self.winner_id,
        }

    # ── 超出10顆歸還 ──────────────────────────
    def apply_discard(self, player_id: int, gems: dict[str, int]) -> dict:
        """
        玩家拿寶石後若超過10顆，需選擇歸還。
        此動作在 take_gems 之後由前端觸發。
        """
        player = self.players[player_id]
        total_discard = sum(gems.values())
        excess = player.total_gems() - 10
        if total_discard != excess:
            return {"ok": False, "error": f"需歸還 {excess} 顆，但選了 {total_discard} 顆"}
        for g, cnt in gems.items():
            if player.gems.get(g, 0) < cnt:
                return {"ok": False, "error": f"{g} 寶石不足以歸還"}
            player.gems[g] -= cnt
            self.bank[g] += cnt
        return {"ok": True}

    # ── 取得合法動作列表（供 MCTS 使用）──────
    def get_legal_actions(self) -> list[dict]:
        player = self.current_player
        actions = []

        # 拿寶石
        available = [g for g in GEMS if self.bank.get(g, 0) > 0]
        # (a) 拿3顆不同色
        if len(available) >= 3:
            from itertools import combinations
            for combo in combinations(available, 3):
                actions.append({
                    "type": "take_gems",
                    "gems": {g: 1 for g in combo}
                })
        # (b) 拿2顆同色（銀行≥4）
        for g in GEMS:
            if self.bank.get(g, 0) >= 4:
                actions.append({
                    "type": "take_gems",
                    "gems": {g: 2}
                })
        # (b') 拿1顆（銀行剩1~3顆時的合法變體）
        if len(available) == 1:
            actions.append({
                "type": "take_gems",
                "gems": {available[0]: 1}
            })
        elif len(available) == 2:
            for g in available:
                actions.append({"type":"take_gems","gems":{g:1}})
            actions.append({"type":"take_gems","gems":{available[0]:1,available[1]:1}})

        # 保留卡
        if len(player.reserved) < MAX_HAND:
            for level in [1, 2, 3]:
                for card in self.board[level]:
                    if card:
                        actions.append({"type": "reserve", "card_id": card["id"]})
            # 從牌堆頂保留
            for level in [1, 2, 3]:
                deck = {1: self.deck_l1, 2: self.deck_l2, 3: self.deck_l3}[level]
                if deck:
                    actions.append({"type": "reserve", "level": level})

        # 購買卡
        for level in [1, 2, 3]:
            for card in self.board[level]:
                if card and self._can_afford(player, card):
                    actions.append({"type": "buy", "card_id": card["id"]})
        for card in player.reserved:
            if self._can_afford(player, card):
                actions.append({"type": "buy", "card_id": card["id"]})

        return actions

    # ── 狀態序列化 ─────────────────────────────
    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "difficulty": self.difficulty,
            "turn": self.turn,
            "current_player_idx": self.current_player_idx,
            "current_player_name": self.current_player.name,
            "bank": dict(self.bank),
            "board": {
                str(lv): [c if c else None for c in self.board[lv]]
                for lv in [1, 2, 3]
            },
            "deck_counts": {
                "1": len(self.deck_l1),
                "2": len(self.deck_l2),
                "3": len(self.deck_l3),
            },
            "nobles": list(self.nobles),
            "players": [p.to_dict() for p in self.players],
            "game_over": self.game_over,
            "winner_id": self.winner_id,
            "last_round_trigger": self.last_round_trigger,
            "action_log": self.action_log[-10:],  # 最近10筆
        }

    def clone(self) -> "GameState":
        """深複製，供 MCTS 模擬使用"""
        return copy.deepcopy(self)
