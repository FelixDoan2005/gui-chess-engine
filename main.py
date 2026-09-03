import pygame
from ui import create_window
from ui import Renderer
from ui import InputHandler
from ui import FPS
from ui import Board, pixel_to_square
from ui.chess_logic import is_legal_move, in_check, pawn_moves, knight_moves, bishop_moves, rook_moves, queen_moves, king_moves, select_piece, get_all_legal_moves
from engine.ai import evaluate

CHECKMATE_DISPLAY_MS = 5000



def check_game_end(board, piece_moves):
    king_pos = board.white_king if board.turn == "white" else board.black_king
    total_legal_moves = get_all_legal_moves(board, piece_moves)

    if total_legal_moves:
        return None
    if in_check(board.grid, board.turn, king_pos):
        return "black" if board.turn == "white" else "white"
    return "stalemate"

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
    winner = None
    checkmate_time = None

    running = True
    while running:
        events = pygame.event.get()
        running = handler.handle(events)
        click = handler.get_mouse_click(events)

        if state == "menu":
            renderer.draw_menu()
            if click:
                if renderer.pvp_rect.collidepoint(click):
                    board = Board()
                    highlights = []
                    selected_square = None
                    promotion_square = None
                    promotion_colour = None
                    state = "playing"

        elif state == "playing":
            if click:
                square = pixel_to_square(*click)
                if square:
                    piece = board.get_piece(*square)

                    if piece is not None and piece.startswith(board.turn):
                        selected_square, highlights = select_piece(square, piece, board, piece_moves)
                    else:
                        if square in highlights:
                            board.move_piece(selected_square, square)
                            print(evaluate(board))

                            moved_piece = board.get_piece(*square)
                            row = square[0]

                            if moved_piece is not None and moved_piece.endswith("pawn") and row in (0, 7):
                                promotion_square = square
                                promotion_colour = moved_piece.split("_")[0]
                                state = "promotion"
                            else:
                                result = check_game_end(board, piece_moves)
                                if result:
                                    winner = result
                                    checkmate_time = pygame.time.get_ticks()
                                    state = "checkmate"

                            selected_square = None
                            highlights = []
                        else:
                            if piece is not None and piece.startswith(board.turn):
                                selected_square, highlights = select_piece(square, piece, board, piece_moves)
                            else:
                                selected_square = None
                                highlights = []

            renderer.draw(board.grid, highlights)

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
                            winner = result
                            checkmate_time = pygame.time.get_ticks()
                            state = "checkmate"
                        else:
                            state = "playing"
                        break

        elif state == "checkmate":
            renderer.draw(board.grid, [])
            if winner == "stalemate":
                renderer.draw_checkmate_popup("Stalemate")
            else:
                renderer.draw_checkmate_popup(winner)
            if pygame.time.get_ticks() - checkmate_time >= CHECKMATE_DISPLAY_MS:
                state = "menu"

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
