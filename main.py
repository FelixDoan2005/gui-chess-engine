import pygame
from ui import create_window
from ui import Renderer
from ui import InputHandler
from ui import FPS
from ui import Board, pixel_to_square
from ui.chess_logic import pawn_moves, knight_moves, bishop_moves, rook_moves, queen_moves, king_moves, in_check

def select_piece(square, piece, board, piece_moves):
    row, col = square
    colour = piece.split("_")[0]
    current_piece = piece.split("_")[1]
    highlights = piece_moves[current_piece](row, col, board.grid, colour)
    return square, highlights

def main():
    screen = create_window()
    clock = pygame.time.Clock()
    board = Board()
    renderer = Renderer(screen)
    handler = InputHandler()
    highlights = []
    selected_square = None

    piece_moves = {
        "pawn": pawn_moves,
        "knight" : knight_moves,
        "bishop" : bishop_moves,
        "rook" : rook_moves,
        "queen" : queen_moves,
        "king" : king_moves,
    }

    running = True
    while running:
        events = pygame.event.get()
        running = handler.handle(events)

        click = handler.get_mouse_click(events)
        if click:
            square = pixel_to_square(*click)
            if square:
                piece = board.get_piece(*square)

                if selected_square is None:
                    # first click — select a piece
                    if piece is not None and piece.startswith(board.turn):
                        selected_square, highlights = select_piece(square, piece, board, piece_moves)
                else:
                    # second click — move if the square is a legal move
                    if square in highlights:
                        board.move_piece(selected_square, square)
                        moving_colour = board.turn
                        if moving_colour == "white":
                            king_pos = board.white_king
                        else:
                            king_pos = board.black_king
                        selected_square = None

                        if in_check(board.grid, moving_colour, king_pos):
                            print(f"{moving_colour} is in check!")
                            #note now need to make all legal moves whilst in check

                        highlights = []
                    else:
                        if piece is not None and piece.startswith(board.turn):
                            selected_square, highlights = select_piece(square, piece, board, piece_moves)
                        else:
                            selected_square = None
                            highlights = []

        renderer.draw(board.grid, highlights)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()