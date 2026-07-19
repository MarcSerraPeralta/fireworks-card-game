import asyncio
from fastapi import FastAPI, WebSocket
from engine import Game, state_to_dict, dict_to_hint


class ConnectionManager:
    def __init__(self):
        # map player_ind to their websocket connection
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, player_ind: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[player_ind] = websocket

    def disconnect(self, player_ind: int):
        del self.active_connections[player_ind]

    async def broadcast_game_state(self, game: Game):
        for player_ind, websocket in self.active_connections.items():
            view = game.get_game_view_for(player_ind)
            await websocket.send_json(
                {"type": "STATE_UPDATE", "state": state_to_dict(view)}
            )


app = FastAPI()
manager = ConnectionManager()
game_started_event = asyncio.Event()
game: Game


@app.post("/start-game/{num_players}")
async def start_game(num_players: int):
    global game
    game = Game(num_players)
    game_started_event.set()
    return {"message": "Game started successfully"}


async def run_lobby(websocket: WebSocket):
    while not game_started_event.is_set():
        recv_task = asyncio.create_task(websocket.receive_json())
        wait_task = asyncio.create_task(game_started_event.wait())

        # Wait for either the player to send something OR the game to start
        done, _ = await asyncio.wait(
            [recv_task, wait_task], return_when=asyncio.FIRST_COMPLETED
        )

        if wait_task in done:
            _ = recv_task.cancel()
            return

        data = recv_task.result()
        if data.get("action") == "start_game":
            global game
            if len(manager.active_connections) >= 2:
                game = Game(len(manager.active_connections))
                game_started_event.set()
                return
            else:
                await websocket.send_json({"error": "Need at least 2 players."})

    return


async def run_game(websocket: WebSocket, player_id: int):
    while game_started_event.is_set():
        data = await websocket.receive_json()

        if data.get("action") == "quit_game":
            global game
            game_started_event.clear()
            return

        if player_id != game.state.player_turn:
            await websocket.send_json({"error": "It is not your turn."})
            continue

        card_ind: int = data.get("card_ind")
        player_ind: int = data.get("player_ind")
        hint_dict: dict[str, str | int] = data.get("hint")

        match data["action"]:
            case "play_card":
                game.play_card(card_ind)
            case "discard_card":
                game.discard_card(card_ind)
            case "give_hint":
                game.give_hint(player_ind, dict_to_hint(hint_dict))
            case "undo":
                game.undo()
            # case "add_note": ...
            case _:
                await websocket.send_json({"error": "Invalid action"})
                continue

        await manager.broadcast_game_state(game)


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    await manager.connect(player_id, websocket)
    try:
        while True:
            if not game_started_event.is_set():
                await run_lobby(websocket)
            else:
                await run_game(websocket, player_id)
    except Exception as e:
        print(f"Connection closed for {player_id}: {e}")
    finally:
        manager.disconnect(player_id)
