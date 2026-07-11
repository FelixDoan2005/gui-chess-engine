import pygame
from ui import create_window
from ui import Renderer
from ui import InputHandler
from ui import FPS
from ui import Board, pixel_to_square
from ui.chess_logic import is_legal_move, in_check, pawn_moves, knight_moves, bishop_moves, rook_moves, queen_moves, king_moves
from engine.ai import evaluate

CHECKMATE_DISPLAY_MS = 5000

def select_piece(square, piece, board, piece_moves):
    row, col = square
    colour = piece.split("_")[0]
    current_piece = piece.split("_")[1]
    if current_piece == "king":
        highlights = piece_moves[current_piece](row, col, board.grid, colour, board)
    elif current_piece == "pawn":
        highlights = piece_moves[current_piece](row, col, board.grid, colour, board.en_passant_ts)
    else:
        highlights = piece_moves[current_piece](row, col, board.grid, colour)
    king_pos = board.white_king if colour == "white" else board.black_king
    legal_highlights = [move for move in highlights if is_legal_move(board.grid, colour, square, move, king_pos)]
    return square, legal_highlights

def get_all_legal_moves(board, piece_moves):
    total = []
    for row in range(8):
        for col in range(8):
            piece = board.grid[row][col]
            if piece is not None and piece.startswith(board.turn):
                _, legal_moves = select_piece((row, col), piece, board, piece_moves)
                total += legal_moves
    return total

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

                            king_pos = board.white_king if board.turn == "white" else board.black_king
                            total_legal_moves = get_all_legal_moves(board, piece_moves)

                            if not total_legal_moves and in_check(board.grid, board.turn, king_pos):
                                winner = "black" if board.turn == "white" else "white"
                                checkmate_time = pygame.time.get_ticks()
                                state = "checkmate"
                            elif not total_legal_moves:
                                winner = "stalemate"
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
