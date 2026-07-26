import asyncio
from fastapi import FastAPI, WebSocket
from engine import Game
from render import render_state_to_dict, dict_to_hint


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, player_name: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[player_name] = websocket

    def disconnect(self, player_name: str):
        _ = self.active_connections.pop(player_name, None)

    async def broadcast_game_state(self, game: Game):
        for player_ind, player_name in enumerate(game.state.player_names):
            websocket = self.active_connections.get(player_name)
            if websocket is None:
                continue

            view = game.get_game_view_for(player_ind)
            await websocket.send_json(
                {"type": "STATE_UPDATE", "state": render_state_to_dict(view)}
            )

    async def broadcast_mode(self, status: str):
        for websocket in self.active_connections.values():
            await websocket.send_json(
                {"type": "MODE_UPDATE", "status": status}
            )


app = FastAPI()
manager = ConnectionManager()
game_started_event = asyncio.Event()
game: Game


@app.post("/start-game")
async def start_game():
    global game
    game = Game(list(manager.active_connections.keys()))
    game_started_event.set()
    await manager.broadcast_mode("game")
    return {"message": "Game started successfully"}


async def run_lobby(websocket: WebSocket):
    global game
    await manager.broadcast_mode("lobby")

    while not game_started_event.is_set():
        recv_task = asyncio.create_task(websocket.receive_json())
        wait_task = asyncio.create_task(game_started_event.wait())

        done, _ = await asyncio.wait(
            [recv_task, wait_task], return_when=asyncio.FIRST_COMPLETED
        )

        if wait_task in done:
            _ = recv_task.cancel()
            return

        if recv_task in done:
            _ = wait_task.cancel()

        data = recv_task.result()
        if data.get("action") == "start_game":
            if len(manager.active_connections) >= 2:
                game = Game(list(manager.active_connections.keys()))
                game_started_event.set()
                await manager.broadcast_mode("game")
                return
            else:
                await websocket.send_json({"error": "Need at least 2 players."})

    return


async def run_game(websocket: WebSocket, player_name: str):
    global game
    player_ind = game.state.player_names.index(player_name)
    await manager.broadcast_game_state(game)

    while game_started_event.is_set():
        data = await websocket.receive_json()

        if data.get("action") == "quit_game":
            game_started_event.clear()
            await manager.broadcast_mode("lobby")
            return

        if data.get("action") == "undo":
            game.undo()
            await manager.broadcast_game_state(game)
            continue

        if player_ind != game.state.player_turn:
            await websocket.send_json({"error": "It is not your turn."})
            continue

        card_ind: int = data.get("card_ind")
        target_player_ind: int = data.get("player_ind")
        hint_dict: dict[str, str | int] = data.get("hint")

        match data["action"]:
            case "play_card":
                game.play_card(card_ind)
            case "discard_card":
                game.discard_card(card_ind)
            case "give_hint":
                game.give_hint(target_player_ind, dict_to_hint(hint_dict))
            case _:
                await websocket.send_json({"error": "Invalid action"})
                continue

        await manager.broadcast_game_state(game)


@app.websocket("/ws/{player_name}")
async def websocket_endpoint(websocket: WebSocket, player_name: str):
    await manager.connect(player_name, websocket)
    try:
        while True:
            if not game_started_event.is_set():
                await run_lobby(websocket)
            else:
                await run_game(websocket, player_name)
    except Exception as e:
        print(f"Connection closed for '{player_name}': {e}")
    finally:
        manager.disconnect(player_name)
