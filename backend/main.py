"""
main.py — FastAPI + WebSocket Hub for Splendor
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

try:
    from game_logic import GameState
    from mcts import mcts_search_async
    from database import init_db, record_game_start, record_game_end, get_history
except ImportError:
    from backend.game_logic import GameState
    from backend.mcts import mcts_search_async
    from backend.database import init_db, record_game_start, record_game_end, get_history

# ─────────────────────────────────────────────
app = FastAPI(title="Splendor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 靜態檔案（前端）
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

init_db()

# ─────────────────────────────────────────────
# 遊戲狀態儲存（in-memory）
# ─────────────────────────────────────────────
games: dict[str, GameState] = {}
connections: dict[str, list[WebSocket]] = {}  # game_id -> [ws, ...]


# ─────────────────────────────────────────────
# 輔助：廣播遊戲狀態
# ─────────────────────────────────────────────
async def broadcast(game_id: str, msg: dict):
    dead = []
    for ws in connections.get(game_id, []):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections[game_id].remove(ws)


# ─────────────────────────────────────────────
# AI 回合執行
# ─────────────────────────────────────────────
async def run_ai_turn(game_id: str):
    """在背景非同步執行 AI 決策，不阻塞 WebSocket"""
    state = games.get(game_id)
    if not state or state.game_over:
        return
    if state.mode != "pve":
        return
    if state.current_player_idx != 1:
        return  # 不是 AI 的回合

    # 廣播思考中
    await broadcast(game_id, {"type": "ai_thinking", "thinking": True})

    try:
        action = await mcts_search_async(state, state.difficulty)
        if action is None:
            return

        result = state.apply_action(action)
        # 超過10顆自動歸還
        player = state.players[1]  # AI is player 1
        excess = player.total_gems() - 10
        if excess > 0:
            discard = {}
            for g in ["white", "blue", "green", "red", "black"]:
                if excess <= 0:
                    break
                drop = min(player.gems.get(g, 0), excess)
                if drop > 0:
                    discard[g] = drop
                    excess -= drop
            state.apply_discard(1, discard)

        await broadcast(game_id, {
            "type": "ai_thinking",
            "thinking": False,
        })
        await broadcast(game_id, {
            "type": "state_update",
            "state": state.to_dict(),
            "last_action": action,
            "result": result,
        })

        if result.get("game_over"):
            record_game_end(
                game_id,
                winner_id=result["winner_id"],
                score_p0=state.players[0].score,
                score_p1=state.players[1].score,
                turns=state.turn,
            )

        # 繼續下一個 AI 回合（不太可能，但以防萬一）
        if not state.game_over and state.current_player_idx == 1:
            asyncio.create_task(run_ai_turn(game_id))

    except Exception as e:
        await broadcast(game_id, {"type": "error", "message": str(e)})


# ─────────────────────────────────────────────
# REST Endpoints
# ─────────────────────────────────────────────
class NewGameRequest(BaseModel):
    mode: str = "pve"           # "pvp" or "pve"
    difficulty: str = "medium"  # "easy" / "medium" / "hard"


@app.get("/")
async def root():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "Splendor API running"}


@app.post("/new-game")
async def new_game(req: NewGameRequest):
    game_id = str(uuid.uuid4())
    state = GameState(mode=req.mode, difficulty=req.difficulty)
    games[game_id] = state
    connections[game_id] = []
    record_game_start(game_id, req.mode, req.difficulty)
    return {"game_id": game_id, "state": state.to_dict()}


class ActionRequest(BaseModel):
    game_id: str
    action: dict
    player_id: Optional[int] = None


@app.post("/action")
async def player_action(req: ActionRequest):
    state = games.get(req.game_id)
    if not state:
        raise HTTPException(404, "遊戲不存在")
    if state.game_over:
        raise HTTPException(400, "遊戲已結束")

    # 驗證是正確的玩家
    if req.player_id is not None and req.player_id != state.current_player_idx:
        raise HTTPException(403, "不是你的回合")

    result = state.apply_action(req.action)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "動作不合法"))

    # 超出10顆：若前端未附 discard，先回傳需要 discard 的狀態
    player = state.players[req.player_id if req.player_id is not None else state.current_player_idx]
    # Note: after apply_action, current_player_idx already advanced
    just_moved_idx = 1 - state.current_player_idx
    just_moved = state.players[just_moved_idx]
    needs_discard = just_moved.total_gems() > 10

    await broadcast(req.game_id, {
        "type": "state_update",
        "state": state.to_dict(),
        "last_action": req.action,
        "result": result,
        "needs_discard": needs_discard,
        "discard_player": just_moved_idx if needs_discard else None,
    })

    if result.get("game_over"):
        record_game_end(
            req.game_id,
            winner_id=result["winner_id"],
            score_p0=state.players[0].score,
            score_p1=state.players[1].score,
            turns=state.turn,
        )

    # 觸發 AI 回合
    if not state.game_over and not needs_discard:
        if state.mode == "pve" and state.current_player_idx == 1:
            asyncio.create_task(run_ai_turn(req.game_id))

    return {"ok": True, "state": state.to_dict(), "result": result}


class DiscardRequest(BaseModel):
    game_id: str
    player_id: int
    gems: dict


@app.post("/discard")
async def discard_gems(req: DiscardRequest):
    state = games.get(req.game_id)
    if not state:
        raise HTTPException(404, "遊戲不存在")
    result = state.apply_discard(req.player_id, req.gems)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error"))

    await broadcast(req.game_id, {
        "type": "state_update",
        "state": state.to_dict(),
        "result": result,
    })

    # 觸發 AI 回合（discard 後）
    if not state.game_over:
        if state.mode == "pve" and state.current_player_idx == 1:
            asyncio.create_task(run_ai_turn(req.game_id))

    return {"ok": True, "state": state.to_dict()}


@app.get("/history")
async def history(limit: int = 20):
    return get_history(limit)


@app.get("/game/{game_id}")
async def get_game(game_id: str):
    state = games.get(game_id)
    if not state:
        raise HTTPException(404, "遊戲不存在")
    return state.to_dict()


# ─────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────
@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await websocket.accept()
    if game_id not in connections:
        connections[game_id] = []
    connections[game_id].append(websocket)

    state = games.get(game_id)
    if state:
        await websocket.send_json({
            "type": "state_update",
            "state": state.to_dict(),
        })
        # 若遊戲一開始就是 AI 回合（AI先手：不太可能，但安全起見）
        if not state.game_over and state.mode == "pve" and state.current_player_idx == 1:
            asyncio.create_task(run_ai_turn(game_id))
    else:
        await websocket.send_json({"type": "error", "message": "遊戲不存在"})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "action":
                s = games.get(game_id)
                if not s or s.game_over:
                    await websocket.send_json({"type": "error", "message": "遊戲不存在或已結束"})
                    continue
                err = s.validate_action(data.get("action", {}))
                if err:
                    await websocket.send_json({"type": "error", "message": err})
                    continue
                result = s.apply_action(data["action"])
                just_moved_idx = 1 - s.current_player_idx
                just_moved = s.players[just_moved_idx]
                needs_discard = just_moved.total_gems() > 10

                await broadcast(game_id, {
                    "type": "state_update",
                    "state": s.to_dict(),
                    "last_action": data["action"],
                    "result": result,
                    "needs_discard": needs_discard,
                    "discard_player": just_moved_idx if needs_discard else None,
                })
                if result.get("game_over"):
                    record_game_end(
                        game_id,
                        winner_id=result["winner_id"],
                        score_p0=s.players[0].score,
                        score_p1=s.players[1].score,
                        turns=s.turn,
                    )
                elif not needs_discard and s.mode == "pve" and s.current_player_idx == 1:
                    asyncio.create_task(run_ai_turn(game_id))

            elif msg_type == "discard":
                s = games.get(game_id)
                if not s:
                    continue
                result = s.apply_discard(data["player_id"], data["gems"])
                await broadcast(game_id, {
                    "type": "state_update",
                    "state": s.to_dict(),
                    "result": result,
                })
                if not s.game_over and s.mode == "pve" and s.current_player_idx == 1:
                    asyncio.create_task(run_ai_turn(game_id))

    except WebSocketDisconnect:
        connections[game_id].remove(websocket)
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        if websocket in connections.get(game_id, []):
            connections[game_id].remove(websocket)
