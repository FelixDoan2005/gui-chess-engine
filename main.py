import threading

import chess
import chess.engine
import pygame
from ui.window import create_window
from ui.renderer import Renderer
from ui.input_handler import InputHandler
from ui.constants import FPS
from ui.chess_logic import Board, pixel_to_square
from ui.chess_logic import is_legal_move, in_check, pawn_moves, knight_moves, bishop_moves, rook_moves, queen_moves, king_moves, select_piece, get_all_legal_moves, draw_reason
from engine.ai import DIFFICULTY_DEPTH
from engine.uci import engine_command, stockfish_path, square_name, play_uci_move

GAME_OVER_DISPLAY_MS = 5000
MOVE_DELAY_MS = 600   # Engine vs Stockfish: a pause between moves, so you can follow the game
PROMOTION_LETTERS = {"queen": "q", "rook": "r", "bishop": "b", "knight": "n"}



def check_game_end(board, piece_moves):
    # Returns (title, reason) for the game-over popup, or None if play continues.
    if not get_all_legal_moves(board, piece_moves):
        if board.turn == "white":
            king_pos = board.white_king
            winner = "Black"
        else:
            king_pos = board.black_king
            winner = "White"
        if in_check(board.grid, board.turn, king_pos):
            return f"{winner} wins!", "by checkmate"
        return "Draw", "by stalemate"

    reason = draw_reason(board)
    if reason:
        return "Draw", f"by {reason}"
    return None

def make_move_and_check_promotion(board, from_sq, to_sq):
    board.move_piece(from_sq, to_sq)
    moved_piece = board.get_piece(*to_sq)
    row = to_sq[0]
    if moved_piece is not None and moved_piece.endswith("pawn") and row in (0, 7):
        return moved_piece.split("_")[0]
    return None

def run_engine_search(engine, move_list, limit, game_number, result):
    # the engine runs as its own program (engine/uci.py, or Stockfish): send it
    # the game so far and wait for its move, e.g. "e7e5"
    chess_board = chess.Board()
    for uci in move_list:
        chess_board.push_uci(uci)
    try:
        # a new game_number tells the engine a new game started ("ucinewgame"),
        # so it empties the table it keeps between moves
        played = engine.play(chess_board, limit, game=game_number)
        result["move"] = played.move.uci()
    except chess.engine.EngineError:
        result["move"] = None
    except chess.engine.EngineTerminatedError:
        result["move"] = None

def main():
    screen = create_window()
    clock = pygame.time.Clock()
    renderer = Renderer(screen)
    handler = InputHandler()

    piece_moves = {
        "pawn": pawn_moves,
        "knight": knight_moves,
        "bishop": bishop_moves,
        "rook": rook_moves,
        "queen": queen_moves,
        "king": king_moves,
    }

    state = "menu"
    board = None
    highlights = []
    selected_square = None
    promotion_square = None
    promotion_colour = None
    game_result = None
    game_over_time = None
    mode = None
    player_colour = None
    depth = None
    time_limit = None
    engine = None             # the engine program, started for the first game against it
    stockfish = None          # Stockfish, started for the first Engine vs Stockfish game
    stockfish_elo = None      # its Elo cap, None = full strength
    caption = ""              # Engine vs Stockfish: who is playing who, under the board
    last_move_time = 0        # when the last engine move was played
    move_list = []            # every move this game, e.g. ["e2e4", "e7e5"], for the engine
    game_number = 0           # goes up each game against the engine
    promotion_move = None     # a promotion waiting for its piece, e.g. "e7e8"
    engine_thread = None
    engine_result = None

    running = True
    while running:
        events = pygame.event.get()
        running = handler.handle(events)
        click = handler.get_mouse_click(events)

        if state == "menu":
            renderer.draw_menu()
            if click:
                if renderer.pvp_rect.collidepoint(click):
                    mode = "pvp"
                    player_colour = None
                    board = Board()
                    move_list = []
                    highlights = []
                    selected_square = None
                    promotion_square = None
                    promotion_colour = None
                    state = "playing"
                elif renderer.pve_rect.collidepoint(click):
                    mode = "pve"
                    state = "colour_select"
                elif renderer.evs_rect.collidepoint(click):
                    if stockfish_path() is None:
                        game_result = ("Stockfish not found", "set STOCKFISH_PATH (see README)")
                        game_over_time = pygame.time.get_ticks()
                        state = "message"
                    else:
                        mode = "evs"
                        state = "colour_select"

        elif state == "message":
            renderer.draw_menu()
            renderer.draw_game_over_popup(*game_result)
            if pygame.time.get_ticks() - game_over_time >= GAME_OVER_DISPLAY_MS:
                state = "menu"

        elif state == "colour_select":
            # Engine vs Stockfish: player_colour is the colour your engine plays
            if mode == "evs":
                renderer.draw_colour_select("Your Engine Plays", "White", "Black")
            else:
                renderer.draw_colour_select()
            if click:
                if renderer.white_rect.collidepoint(click):
                    player_colour = "white"
                    state = "difficulty_select"
                elif renderer.black_rect.collidepoint(click):
                    player_colour = "black"
                    state = "difficulty_select"

        elif state == "difficulty_select":
            renderer.draw_difficulty_select()
            if click:
                for level, rect in renderer.difficulty_rects.items():
                    if rect.collidepoint(click):
                        depth = DIFFICULTY_DEPTH[level]
                        if mode == "evs":
                            state = "stockfish_select"
                        else:
                            state = "time_select"
                        break

        elif state == "stockfish_select":
            renderer.draw_stockfish_select()
            if click:
                for elo, rect in renderer.stockfish_rects.items():
                    if rect.collidepoint(click):
                        stockfish_elo = elo
                        state = "time_select"
                        break

        elif state == "time_select":
            renderer.draw_time_select(include_unlimited=(mode != "evs"))
            if click:
                for limit, rect in renderer.time_rects.items():
                    # no "Unlimited" against Stockfish: it would think forever
                    if mode == "evs" and limit is None:
                        continue
                    if rect.collidepoint(click):
                        time_limit = limit
                        if engine is None:
                            engine = chess.engine.SimpleEngine.popen_uci(engine_command())

                        if mode == "evs":
                            if stockfish is None:
                                stockfish = chess.engine.SimpleEngine.popen_uci(stockfish_path())
                            if stockfish_elo is None:
                                stockfish.configure({"UCI_LimitStrength": False})
                                stockfish_label = "full strength"
                            else:
                                stockfish.configure({"UCI_LimitStrength": True, "UCI_Elo": stockfish_elo})
                                stockfish_label = f"{stockfish_elo}"
                            caption = f"Your engine (depth {depth}) vs Stockfish {stockfish_label}, {time_limit}s"
                            last_move_time = pygame.time.get_ticks()

                        game_number += 1
                        board = Board()
                        move_list = []
                        highlights = []
                        selected_square = None
                        promotion_square = None
                        promotion_colour = None
                        engine_thread = None
                        engine_result = None
                        state = "playing"
                        break

        elif state == "playing":
            # an engine moves: always in Engine vs Stockfish, otherwise on its colour
            engine_turn = False
            if mode == "pve" and board.turn != player_colour:
                engine_turn = True
            if mode == "evs":
                engine_turn = True

            if engine_turn:
                if engine_thread is None:
                    # Engine vs Stockfish: wait a moment after each move so you can follow
                    ready = True
                    if mode == "evs" and pygame.time.get_ticks() - last_move_time < MOVE_DELAY_MS:
                        ready = False

                    if ready:
                        if mode == "evs" and board.turn != player_colour:
                            thinker = stockfish
                            limit = chess.engine.Limit(time=time_limit)
                        else:
                            thinker = engine
                            limit = chess.engine.Limit(depth=depth, time=time_limit)
                        engine_result = {}
                        engine_thread = threading.Thread(
                            target=run_engine_search,
                            args=(thinker, list(move_list), limit, game_number, engine_result),
                            daemon=True,
                        )
                        engine_thread.start()
                elif not engine_thread.is_alive():
                    move = engine_result.get("move")
                    engine_thread = None
                    if move is None:
                        # the engine program stopped answering
                        game_result = ("Engine error", "the engine stopped responding")
                        game_over_time = pygame.time.get_ticks()
                        state = "game_over"
                    else:
                        play_uci_move(board, move)
                        move_list.append(move)
                        last_move_time = pygame.time.get_ticks()

                        result = check_game_end(board, piece_moves)
                        if result:
                            game_result = result
                            game_over_time = pygame.time.get_ticks()
                            state = "game_over"

                selected_square = None
                highlights = []
            elif click:
                square = pixel_to_square(*click)
                if square:
                    piece = board.get_piece(*square)

                    if piece is not None and piece.startswith(board.turn):
                        selected_square, highlights = select_piece(square, piece, board, piece_moves)
                    else:
                        if square in highlights:
                            uci = square_name(selected_square) + square_name(square)
                            promo_colour = make_move_and_check_promotion(board, selected_square, square)

                            if promo_colour is not None:
                                # added to move_list once the piece is picked
                                promotion_move = uci
                                promotion_square = square
                                promotion_colour = promo_colour
                                state = "promotion"
                            else:
                                move_list.append(uci)
                                result = check_game_end(board, piece_moves)
                                if result:
                                    game_result = result
                                    game_over_time = pygame.time.get_ticks()
                                    state = "game_over"

                            selected_square = None
                            highlights = []
                        else:
                            if piece is not None and piece.startswith(board.turn):
                                selected_square, highlights = select_piece(square, piece, board, piece_moves)
                            else:
                                selected_square = None
                                highlights = []

            renderer.draw(board.grid, highlights)
            if mode == "evs":
                renderer.draw_caption(caption)
            if engine_thread is not None:
                if mode == "evs" and board.turn != player_colour:
                    renderer.draw_thinking("Stockfish is thinking...")
                elif mode == "evs":
                    renderer.draw_thinking("Your engine is thinking...")
                else:
                    renderer.draw_thinking()

        elif state == "promotion":
            renderer.draw(board.grid, [])
            renderer.draw_promotion_picker(promotion_colour)

            if click:
                for kind, rect in renderer.promotion_rects.items():
                    if rect.collidepoint(click):
                        row, col = promotion_square
                        board.grid[row][col] = f"{promotion_colour}_{kind}"
                        move_list.append(promotion_move + PROMOTION_LETTERS[kind])
                        promotion_move = None
                        promotion_square = None
                        promotion_colour = None

                        result = check_game_end(board, piece_moves)
                        if result:
                            game_result = result
                            game_over_time = pygame.time.get_ticks()
                            state = "game_over"
                        else:
                            state = "playing"
                        break

        elif state == "game_over":
            renderer.draw(board.grid, [])
            renderer.draw_game_over_popup(*game_result)
            if pygame.time.get_ticks() - game_over_time >= GAME_OVER_DISPLAY_MS:
                state = "menu"

        pygame.display.flip()
        clock.tick(FPS)

    # stop the engine programs straight away, even if they're mid-search
    if engine is not None:
        engine.close()
    if stockfish is not None:
        stockfish.close()
    pygame.quit()

if __name__ == "__main__":
    main()
