import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import chess
import chess.engine
from pydantic import BaseModel
from engine.uci import engine_command

MAX_SECONDS = 5  # 5 so server doesnt get blocked from long thinking.
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WEB_DIR)

felis = chess.engine.SimpleEngine.popen_uci(engine_command())


# runs when the server starts and stops: close Felis on the way out,
# otherwise --reload gets stuck waiting for it
@asynccontextmanager
async def lifespan(app):
    yield
    felis.quit()


app = FastAPI(lifespan=lifespan)

# the piece pictures, the same ones the pygame GUI uses
app.mount("/pieces", StaticFiles(directory=os.path.join(ROOT, "assets", "images", "pieces")), name="pieces")


# when the browser visits "/", send it the chessboard page
@app.get("/")
def home():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


class MoveRequest(BaseModel):
    moves: list[str]
    seconds: float = 1


@app.post("/move")
def move(request: MoveRequest):
    board = chess.Board()
    for uci in request.moves:
        try:
            board.push_uci(uci)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"illegal move!: {uci}")

    if board.is_game_over():
        return {"move": None}

    seconds = min(request.seconds, MAX_SECONDS)
    played = felis.play(board, chess.engine.Limit(time=seconds))
    return {"move": played.move.uci()}
