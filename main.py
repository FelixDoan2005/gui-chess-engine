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
from engine.uci import engine_command, stockfish_path, square_name, square_from_name, play_uci_move

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

def timeout_result(move_list, flagged):
    # running out of time loses, unless the other side can't possibly checkmate
    # (e.g. a lone king), then it's a draw
    chess_board = chess.Board()
    for uci in move_list:
        chess_board.push_uci(uci)
    if flagged == "white":
        other = chess.BLACK
        winner = "Black"
    else:
        other = chess.WHITE
        winner = "White"
    if chess_board.has_insufficient_material(other):
        return "Draw", "by timeout vs insufficient material"
    return f"{winner} wins!", "on time"

def press_clock(clocks, side, clock_start, move_list):
    # takes the time used off the side that just moved, returns when the next clock starts
    # white's first move is free: the clocks only start after it
    now = pygame.time.get_ticks()
    if len(move_list) > 1:
        clocks[side] -= (now - clock_start) / 1000
    return now

def premove_position(grid, premoves):
    position = []
    for row in grid:
        position.append(row[:])
    for from_sq, to_sq in premoves:
        fr, fc = from_sq
        tr, tc = to_sq
        piece = position[fr][fc]
        if piece is None:
            continue
        position[fr][fc] = None
        colour, kind = piece.split("_")
        if kind == "pawn" and (tr == 0 or tr == 7):
            position[tr][tc] = f"{colour}_queen"
        else:
            position[tr][tc] = piece
        if kind == "king" and fc == 4 and tc == 6:
            position[tr][5] = position[tr][7]
            position[tr][7] = None
        if kind == "king" and fc == 4 and tc == 2:
            position[tr][3] = position[tr][0]
            position[tr][0] = None
    return position

def premove_targets(square, piece):
    row, col = square
    colour, kind = piece.split("_")
    targets = []

    def add(r, c):
        if 0 <= r < 8 and 0 <= c < 8:
            targets.append((r, c))

    if kind == "pawn":
        if colour == "white":
            forward = -1
            start_row = 6
        else:
            forward = 1
            start_row = 1
        add(row + forward, col)
        if row == start_row:
            add(row + 2 * forward, col)
        add(row + forward, col - 1)
        add(row + forward, col + 1)
    elif kind == "knight":
        for dr, dc in [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]:
            add(row + dr, col + dc)
    elif kind == "king":
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr != 0 or dc != 0:
                    add(row + dr, col + dc)
        if colour == "white":
            home_row = 7
        else:
            home_row = 0
        if row == home_row and col == 4:
            add(row, 6)
            add(row, 2)
    else:
        directions = []
        if kind == "bishop" or kind == "queen":
            directions.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])
        if kind == "rook" or kind == "queen":
            directions.extend([(1, 0), (-1, 0), (0, 1), (0, -1)])
        for dr, dc in directions:
            r = row + dr
            c = col + dc
            while 0 <= r < 8 and 0 <= c < 8:
                add(r, c)
                r += dr
                c += dc
    return targets

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
    custom_text = ""          # the custom time per move being typed, e.g. "20"
    custom_error = ""         # shown when what was typed isn't a number
    last_move = None          # (from square, to square) of the last move, drawn glowing green
    engine_thread = None
    engine_result = None
    clock_minutes = None      # game clock in minutes each, None = no clock
    clocks = None             # seconds left, e.g. {"white": 300.0, "black": 300.0}
    clock_side = "white"      # whose clock is running
    clock_start = 0           # when it started running
    premoves = []

    running = True
    while running:
        events = pygame.event.get()
        running = handler.handle(events)
        click = handler.get_mouse_click(events)
        right_click = handler.get_right_click(events)

        if state != "menu" and state != "message" and click and renderer.menu_rect.collidepoint(click):
            if engine_thread is not None:
                if engine is not None:
                    engine.close()
                    engine = None
                if stockfish is not None:
                    stockfish.close()
                    stockfish = None
                engine_thread = None
            state = "menu"
            click = None

        if state == "menu":
            renderer.draw_menu()
            if click:
                if renderer.pvp_rect.collidepoint(click):
                    mode = "pvp"
                    player_colour = None
                    state = "clock_select"
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
            # Engine vs Stockfish: player_colour is the colour Felis plays
            if mode == "evs":
                renderer.draw_colour_select("Felis Plays", "White", "Black")
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
                        # "max": no depth limit, the engine searches as deep as the time allows
                        if level == "max":
                            depth = None
                        else:
                            depth = DIFFICULTY_DEPTH[level]
                        if mode == "evs":
                            state = "stockfish_select"
                        else:
                            state = "clock_select"
                        break

        elif state == "stockfish_select":
            renderer.draw_stockfish_select()
            if click:
                for elo, rect in renderer.stockfish_rects.items():
                    if rect.collidepoint(click):
                        stockfish_elo = elo
                        state = "clock_select"
                        break

        elif state == "clock_select":
            # ratings were only tested at max difficulty
            show_ratings = False
            if mode != "pvp" and depth is None:
                show_ratings = True
            renderer.draw_clock_select(show_ratings=show_ratings)
            if click:
                for minutes, rect in renderer.clock_rects.items():
                    if rect.collidepoint(click):
                        clock_minutes = minutes
                        # no clock against an engine: pick the seconds per move instead
                        if minutes is None and mode != "pvp":
                            state = "time_select"
                        else:
                            state = "start_game"
                        break

        elif state == "time_select":
            # no "Unlimited" against Stockfish or on max difficulty: they'd think forever
            unlimited_allowed = True
            if mode == "evs" or depth is None:
                unlimited_allowed = False
            # ratings were only tested at max difficulty
            show_ratings = False
            if depth is None:
                show_ratings = True
            renderer.draw_time_select(include_unlimited=unlimited_allowed, show_ratings=show_ratings)
            if click:
                for limit, rect in renderer.time_rects.items():
                    if limit is None and not unlimited_allowed:
                        continue
                    if rect.collidepoint(click):
                        if limit == "custom":
                            custom_text = ""
                            custom_error = ""
                            state = "custom_time"
                        else:
                            time_limit = limit
                            state = "start_game"
                        break

        elif state == "custom_time":
            # type the seconds: Enter starts the game, Esc goes back
            renderer.draw_custom_time(custom_text, custom_error)
            for event in events:
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key == pygame.K_ESCAPE:
                    state = "time_select"
                elif event.key == pygame.K_BACKSPACE:
                    custom_text = custom_text[:-1]
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    try:
                        seconds = float(custom_text)
                    except ValueError:
                        seconds = 0
                    if seconds > 0:
                        time_limit = seconds
                        state = "start_game"
                    else:
                        custom_error = "Type a number of seconds, e.g. 20"
                elif event.unicode in "0123456789." and event.unicode != "" and len(custom_text) < 6:
                    custom_text += event.unicode
                    custom_error = ""

        elif state == "start_game":
            # start the engine programs if needed, and a fresh board
            if engine is None and mode != "pvp":
                engine = chess.engine.SimpleEngine.popen_uci(engine_command())

            if clock_minutes is None:
                clocks = None
            else:
                clocks = {"white": clock_minutes * 60, "black": clock_minutes * 60}
                clock_side = "white"
                clock_start = pygame.time.get_ticks()

            if mode == "evs":
                if stockfish is None:
                    stockfish = chess.engine.SimpleEngine.popen_uci(stockfish_path())
                if stockfish_elo is None:
                    stockfish.configure({"UCI_LimitStrength": False})
                    stockfish_label = "full strength"
                else:
                    stockfish.configure({"UCI_LimitStrength": True, "UCI_Elo": stockfish_elo})
                    stockfish_label = f"{stockfish_elo}"
                if depth is None:
                    engine_label = "max"
                else:
                    engine_label = f"depth {depth}"
                if clock_minutes is None:
                    time_label = f"{time_limit:g}s"
                else:
                    time_label = f"{clock_minutes} min"
                caption = f"Felis ({engine_label}) vs Stockfish {stockfish_label}, {time_label}"
                last_move_time = pygame.time.get_ticks()

            game_number += 1
            board = Board()
            move_list = []
            last_move = None
            highlights = []
            selected_square = None
            promotion_square = None
            promotion_colour = None
            engine_thread = None
            engine_result = None
            premoves = []
            state = "playing"

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
                            search_depth = None
                        else:
                            thinker = engine
                            search_depth = depth
                        if clocks is None:
                            limit = chess.engine.Limit(depth=search_depth, time=time_limit)
                        else:
                            # the pause between moves doesn't count on the clock
                            if mode == "evs":
                                clock_start = pygame.time.get_ticks()
                            # the engine gets both clocks and decides its own time
                            limit = chess.engine.Limit(depth=search_depth, white_clock=clocks["white"], black_clock=clocks["black"])
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
                        last_move = (square_from_name(move[0:2]), square_from_name(move[2:4]))
                        move_list.append(move)
                        last_move_time = pygame.time.get_ticks()
                        if clocks is not None:
                            clock_start = press_clock(clocks, clock_side, clock_start, move_list)
                            clock_side = board.turn
                        selected_square = None
                        highlights = []

                        result = check_game_end(board, piece_moves)
                        if result:
                            game_result = result
                            game_over_time = pygame.time.get_ticks()
                            state = "game_over"
                        elif len(premoves) > 0:
                            from_sq, to_sq = premoves.pop(0)
                            piece = board.get_piece(*from_sq)
                            legal = []
                            if piece is not None and piece.startswith(board.turn):
                                _, legal = select_piece(from_sq, piece, board, piece_moves)
                            if to_sq in legal:
                                uci = square_name(from_sq) + square_name(to_sq)
                                last_move = (from_sq, to_sq)
                                promo_colour = make_move_and_check_promotion(board, from_sq, to_sq)
                                if promo_colour is not None:
                                    board.grid[to_sq[0]][to_sq[1]] = f"{promo_colour}_queen"
                                    uci += "q"
                                move_list.append(uci)
                                if clocks is not None:
                                    clock_start = press_clock(clocks, clock_side, clock_start, move_list)
                                    clock_side = board.turn
                                result = check_game_end(board, piece_moves)
                                if result:
                                    game_result = result
                                    game_over_time = pygame.time.get_ticks()
                                    state = "game_over"
                            else:
                                premoves = []

                if mode == "evs":
                    selected_square = None
                    highlights = []
                elif right_click:
                    premoves = []
                    selected_square = None
                    highlights = []
                elif click and state == "playing" and engine_thread is not None:
                    square = pixel_to_square(*click)
                    if square:
                        position = premove_position(board.grid, premoves)
                        piece = position[square[0]][square[1]]
                        if selected_square is not None and square in highlights:
                            premoves.append((selected_square, square))
                            selected_square = None
                            highlights = []
                        elif piece is not None and piece.startswith(player_colour):
                            selected_square = square
                            highlights = premove_targets(square, piece)
                        else:
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
                            last_move = (selected_square, square)
                            promo_colour = make_move_and_check_promotion(board, selected_square, square)

                            if promo_colour is not None:
                                # added to move_list once the piece is picked
                                promotion_move = uci
                                promotion_square = square
                                promotion_colour = promo_colour
                                state = "promotion"
                            else:
                                move_list.append(uci)
                                if clocks is not None:
                                    clock_start = press_clock(clocks, clock_side, clock_start, move_list)
                                    clock_side = board.turn
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

            renderer.draw(premove_position(board.grid, premoves), highlights, last_move, premoves)
            if mode == "evs":
                renderer.draw_caption(caption)
            if engine_thread is not None:
                if mode == "evs" and board.turn != player_colour:
                    renderer.draw_thinking("Stockfish is thinking...")
                elif mode == "evs":
                    renderer.draw_thinking("Felis is thinking...")
                else:
                    renderer.draw_thinking()

        elif state == "promotion":
            renderer.draw(board.grid, [], last_move)
            renderer.draw_promotion_picker(promotion_colour)

            if click:
                for kind, rect in renderer.promotion_rects.items():
                    if rect.collidepoint(click):
                        row, col = promotion_square
                        board.grid[row][col] = f"{promotion_colour}_{kind}"
                        move_list.append(promotion_move + PROMOTION_LETTERS[kind])
                        if clocks is not None:
                            clock_start = press_clock(clocks, clock_side, clock_start, move_list)
                            clock_side = board.turn
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
            renderer.draw(board.grid, [], last_move)
            renderer.draw_game_over_popup(*game_result)
            if pygame.time.get_ticks() - game_over_time >= GAME_OVER_DISPLAY_MS:
                state = "menu"

        # game clock: the side to move loses when theirs runs out
        # it starts after white's first move, and in Engine vs Stockfish
        # it waits during the pause between moves
        clock_ticking = False
        if clocks is not None and (state == "playing" or state == "promotion") and len(move_list) > 0:
            if mode != "evs" or engine_thread is not None:
                clock_ticking = True

        if clock_ticking:
            time_left = clocks[clock_side] - (pygame.time.get_ticks() - clock_start) / 1000
            if time_left <= 0:
                clocks[clock_side] = 0
                game_result = timeout_result(move_list, clock_side)
                game_over_time = pygame.time.get_ticks()
                state = "game_over"

        if clocks is not None and (state == "playing" or state == "promotion" or state == "game_over"):
            white_left = clocks["white"]
            black_left = clocks["black"]
            running_clock = None
            if state != "game_over" and len(move_list) > 0:
                running_clock = clock_side
            if clock_ticking:
                elapsed = (pygame.time.get_ticks() - clock_start) / 1000
                if clock_side == "white":
                    white_left -= elapsed
                else:
                    black_left -= elapsed
            renderer.draw_clocks(white_left, black_left, running_clock)

        if state != "menu" and state != "message":
            renderer.draw_menu_button()

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
