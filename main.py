import threading

import pygame
from ui import create_window
from ui import Renderer
from ui import InputHandler
from ui import FPS
from ui import Board, pixel_to_square
from ui.chess_logic import is_legal_move, in_check, pawn_moves, knight_moves, bishop_moves, rook_moves, queen_moves, king_moves, select_piece, get_all_legal_moves, draw_reason
from engine.ai import evaluate, AI, DIFFICULTY_DEPTH, clone_board

GAME_OVER_DISPLAY_MS = 5000



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

def run_engine_search(ai, search_board, piece_moves, depth, result):
    result["move"] = ai.choose_move(search_board, piece_moves, depth=depth)

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
    ai = None
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
                    ai = None
                    board = Board()
                    highlights = []
                    selected_square = None
                    promotion_square = None
                    promotion_colour = None
                    state = "playing"
                elif renderer.pve_rect.collidepoint(click):
                    mode = "pve"
                    state = "colour_select"

        elif state == "colour_select":
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
                        ai = AI()
                        board = Board()
                        highlights = []
                        selected_square = None
                        promotion_square = None
                        promotion_colour = None
                        engine_thread = None
                        engine_result = None
                        state = "playing"
                        break

        elif state == "playing":
            if mode == "pve" and board.turn != player_colour:
                if engine_thread is None:
                    search_board = clone_board(board)
                    engine_result = {}
                    engine_thread = threading.Thread(
                        target=run_engine_search,
                        args=(ai, search_board, piece_moves, depth, engine_result),
                        daemon=True,
                    )
                    engine_thread.start()
                elif not engine_thread.is_alive():
                    move = engine_result.get("move")
                    engine_thread = None
                    if move is not None:
                        engine_from, engine_to = move
                        promo_colour = make_move_and_check_promotion(board, engine_from, engine_to)
                        if promo_colour is not None:
                            row, col = engine_to
                            board.grid[row][col] = f"{promo_colour}_queen"

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
                            promo_colour = make_move_and_check_promotion(board, selected_square, square)
                            print(evaluate(board))

                            if promo_colour is not None:
                                promotion_square = square
                                promotion_colour = promo_colour
                                state = "promotion"
                            else:
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
            if engine_thread is not None:
                renderer.draw_thinking()

        elif state == "promotion":
            renderer.draw(board.grid, [])
            renderer.draw_promotion_picker(promotion_colour)

            if click:
                for kind, rect in renderer.promotion_rects.items():
                    if rect.collidepoint(click):
                        row, col = promotion_square
                        board.grid[row][col] = f"{promotion_colour}_{kind}"
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

    pygame.quit()

if __name__ == "__main__":
    main()
