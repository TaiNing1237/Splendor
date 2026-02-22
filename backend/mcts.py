"""
mcts.py — Monte Carlo Tree Search AI for Splendor
====================================================
Implements UCT (Upper Confidence Bound for Trees) search with:
  - Tree policy:  UCT node selection
  - Rollout policy: greedy heuristic (buy high-point cards first)
  - Backpropagation: win/loss scores propagated up the tree

Difficulty levels control the number of MCTS iterations:
  Easy:   200  iterations
  Medium: 1000 iterations
  Hard:   3000 iterations (time-capped at 5s)
"""
from __future__ import annotations

import math
import time
import random
import copy
from typing import Optional

try:
    from game_logic import GameState
except ImportError:
    from backend.game_logic import GameState

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
DIFFICULTY_ITERATIONS = {
    "easy":   200,
    "medium": 1000,
    "hard":   3000,
}
HARD_TIME_LIMIT = 5.0   # seconds — hard cap for Hard difficulty
UCT_C = 1.41            # exploration constant (≈ sqrt(2))


# ─────────────────────────────────────────────
# MCTS Node
# ─────────────────────────────────────────────
class MCTSNode:
    """
    Represents a single node in the MCTS search tree.

    Attributes
    ----------
    state       : GameState — the game state at this node
    parent      : parent MCTSNode (None for root)
    action      : the action that led from parent to this node
    children    : list of expanded child nodes
    untried_actions : actions not yet expanded into children
    wins        : cumulative win score (from this node's perspective)
    visits      : number of times this node has been visited
    player_idx  : which player made the move to arrive at this node
                  (used for backpropagation)
    """

    def __init__(
        self,
        state: GameState,
        parent: Optional["MCTSNode"] = None,
        action: Optional[dict] = None,
    ):
        self.state = state
        self.parent = parent
        self.action = action                         # action that led here
        self.children: list[MCTSNode] = []
        self.wins: float = 0.0
        self.visits: int = 0
        self.player_idx: int = state.current_player_idx  # player to move
        self.untried_actions: list[dict] = state.get_legal_actions()
        # Shuffle so expansion order is random
        random.shuffle(self.untried_actions)

    # ── UCT score ──────────────────────────────
    def uct_score(self, c: float = UCT_C) -> float:
        """
        Upper Confidence Bound formula:
            UCT = (wins/visits) + C * sqrt(ln(parent.visits) / visits)

        The first term favours exploitation (high win-rate children).
        The second term favours exploration (under-visited children).
        """
        if self.visits == 0:
            return float("inf")    # Always explore unvisited nodes first
        exploit = self.wins / self.visits
        explore = c * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploit + explore

    # ── Tree policy helpers ─────────────────────
    def is_fully_expanded(self) -> bool:
        """True when all legal actions have been tried at least once."""
        return len(self.untried_actions) == 0

    def is_terminal(self) -> bool:
        """True when the game is over at this state."""
        return self.state.game_over

    def best_child(self, c: float = UCT_C) -> "MCTSNode":
        """Return child with highest UCT score (tree policy selection)."""
        return max(self.children, key=lambda n: n.uct_score(c))

    # ── Expansion ──────────────────────────────
    def expand(self) -> "MCTSNode":
        """
        Expand one untried action by:
          1. Popping a random untried action.
          2. Cloning the current state and applying the action.
          3. Creating a child node and adding it to children.
        """
        action = self.untried_actions.pop()
        child_state = self.state.clone()
        child_state.apply_action(action)
        # Handle gem discard if player went over 10
        _auto_discard(child_state)
        child = MCTSNode(child_state, parent=self, action=action)
        self.children.append(child)
        return child


# ─────────────────────────────────────────────
# Auto-discard helper
# ─────────────────────────────────────────────
def _auto_discard(state: GameState):
    """
    After taking gems, a player may have more than 10 gems.
    In simulation we auto-discard cheapest gems greedily
    (keeps gold and high-value gems).
    """
    player = state.players[1 - state.current_player_idx]  # player who just moved
    excess = player.total_gems() - 10
    if excess <= 0:
        return
    # Discard non-gold gems first, cheapest (most common) colors last
    discard = {}
    order = ["white", "blue", "green", "red", "black"]
    for g in order:
        if excess <= 0:
            break
        drop = min(player.gems.get(g, 0), excess)
        if drop > 0:
            discard[g] = drop
            excess -= drop
    state.apply_discard(player.player_id, discard)


# ─────────────────────────────────────────────
# Rollout (simulation) policy
# ─────────────────────────────────────────────
def _rollout_policy(state: GameState) -> Optional[dict]:
    """
    Greedy rollout policy — chooses an action without building a tree:
      Priority 1: Buy the highest-point card affordable.
      Priority 2: Buy the cheapest card affordable.
      Priority 3: Take gems that bring us closest to affording a target card.
      Priority 4: Random legal action.
    """
    actions = state.get_legal_actions()
    if not actions:
        return None

    player = state.current_player

    # Priority 1 & 2: buy actions sorted by points desc, then cost asc
    buy_actions = [a for a in actions if a["type"] == "buy"]
    if buy_actions:
        def buy_key(a):
            card = state._find_buyable_card(player, a["card_id"])
            if card is None:
                return (0, 999)
            total_cost = sum(card["cost"].values())
            return (-card["points"], total_cost)
        buy_actions.sort(key=buy_key)
        return buy_actions[0]

    # Priority 3: take gems heuristic — target the card closest to affordable
    take_actions = [a for a in actions if a["type"] == "take_gems"]
    if take_actions:
        # find the board card with minimum remaining cost
        bonus = player.gem_bonus()
        best_card = None
        best_remaining = float("inf")
        for level in [1, 2, 3]:
            for card in state.board[level]:
                if card:
                    remaining = sum(
                        max(0, card["cost"].get(g, 0) - bonus.get(g, 0) - player.gems.get(g, 0))
                        for g in ["white", "blue", "green", "red", "black"]
                    )
                    if remaining < best_remaining:
                        best_remaining = remaining
                        best_card = card
        if best_card:
            # take gems that are most needed
            needed = {
                g: max(0, best_card["cost"].get(g, 0)
                       - bonus.get(g, 0)
                       - player.gems.get(g, 0))
                for g in ["white", "blue", "green", "red", "black"]
            }
            # filter to actions that collect needed gems
            def take_score(a):
                gems = a.get("gems", {})
                return sum(min(gems.get(g, 0), needed.get(g, 0)) for g in gems)
            take_actions.sort(key=take_score, reverse=True)
            return take_actions[0]

    # Priority 4: random
    return random.choice(actions)


def _simulate(state: GameState, max_depth: int = 50) -> float:
    """
    Run a random rollout from the given state using the greedy policy.
    Returns a score from the perspective of player index 1 (the AI).

    Score:
      1.0  — AI wins
      0.0  — AI loses
      0.5  — draw / inconclusive after max_depth
    """
    sim = state.clone()
    depth = 0
    ai_idx = 1  # AI is always player index 1

    while not sim.game_over and depth < max_depth:
        action = _rollout_policy(sim)
        if action is None:
            break
        sim.apply_action(action)
        _auto_discard(sim)
        depth += 1

    if sim.game_over:
        if sim.winner_id == ai_idx:
            return 1.0
        else:
            return 0.0

    # Heuristic terminal evaluation (game not finished in max_depth steps)
    ai = sim.players[ai_idx]
    opp = sim.players[1 - ai_idx]
    ai_score  = ai.score  + 0.1 * sum(ai.gem_bonus().values())
    opp_score = opp.score + 0.1 * sum(opp.gem_bonus().values())
    if ai_score > opp_score:
        return 0.75
    elif ai_score < opp_score:
        return 0.25
    return 0.5


# ─────────────────────────────────────────────
# Backpropagation
# ─────────────────────────────────────────────
def _backpropagate(node: MCTSNode, result: float):
    """
    Walk from the given node up to the root, updating visits and wins.
    The result (1=AI wins, 0=AI loses) is stored directly —
    since we always evaluate from AI's perspective (player 1).
    """
    current = node
    while current is not None:
        current.visits += 1
        # Nodes where AI (player 1) is moving get the raw win probability.
        # Nodes where the opponent is moving get the inverse.
        if current.player_idx == 1:
            current.wins += result
        else:
            current.wins += (1.0 - result)
        current = current.parent


# ─────────────────────────────────────────────
# Main MCTS search function
# ─────────────────────────────────────────────
def mcts_search(
    state: GameState,
    difficulty: str = "medium",
    callback=None,
) -> Optional[dict]:
    """
    Run MCTS from the given game state and return the best action.

    Parameters
    ----------
    state      : current game state (will be cloned internally)
    difficulty : 'easy' | 'medium' | 'hard'
    callback   : optional callable(iteration, total) for progress reporting

    Returns
    -------
    Best action dict, or None if no legal actions exist.
    """
    iterations = DIFFICULTY_ITERATIONS.get(difficulty, 1000)
    time_limit = HARD_TIME_LIMIT if difficulty == "hard" else float("inf")

    legal = state.get_legal_actions()
    if not legal:
        return None
    if len(legal) == 1:
        return legal[0]

    root = MCTSNode(state.clone())
    start_time = time.time()

    for i in range(iterations):
        # ── Time cap for Hard difficulty ──
        if time.time() - start_time > time_limit:
            break

        # ── 1. Selection: traverse tree using UCT ──
        node = root
        while node.is_fully_expanded() and not node.is_terminal():
            node = node.best_child(UCT_C)

        # ── 2. Expansion: add one child if non-terminal ──
        if not node.is_terminal() and not node.is_fully_expanded():
            node = node.expand()

        # ── 3. Simulation: rollout from expanded node ──
        result = _simulate(node.state)

        # ── 4. Backpropagation: update all ancestors ──
        _backpropagate(node, result)

        # ── Progress callback (e.g. every 100 iterations) ──
        if callback and (i + 1) % 100 == 0:
            callback(i + 1, iterations)

    # ── Select the best child of root (exploitation only, c=0) ──
    if not root.children:
        # No expansion happened (e.g. only 1 iteration), pick random
        return random.choice(legal)

    best = max(root.children, key=lambda n: n.visits)
    return best.action


# ─────────────────────────────────────────────
# Async wrapper for FastAPI
# ─────────────────────────────────────────────
async def mcts_search_async(
    state: GameState,
    difficulty: str = "medium",
) -> Optional[dict]:
    """
    Async-friendly wrapper. Runs MCTS in a thread pool executor
    so it doesn't block the event loop.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,  # use default ThreadPoolExecutor
        lambda: mcts_search(state, difficulty)
    )
    return result
