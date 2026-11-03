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
    # game clock: seconds left on each side, None = no clock
    white_clock: float | None = None
    black_clock: float | None = None


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

    if request.white_clock is None or request.black_clock is None:
        seconds = min(request.seconds, MAX_SECONDS)
    else:
        if board.turn == chess.WHITE:
            clock_left = request.white_clock
        else:
            clock_left = request.black_clock
        # about 1/30 of the time left, like engine/uci.py, but never over MAX_SECONDS
        seconds = min(max(clock_left / 30, 0.05), MAX_SECONDS)
    played = felis.play(board, chess.engine.Limit(time=seconds))
    return {"move": played.move.uci()}
