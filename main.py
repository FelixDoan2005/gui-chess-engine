import pygame
from ui import create_window
from ui import Renderer
from ui import InputHandler
from ui import FPS
from ui import Board, pixel_to_square
from ui.chess_logic import is_legal_move, in_check, pawn_moves, knight_moves, bishop_moves, rook_moves, queen_moves, king_moves

def select_piece(square, piece, board, piece_moves):
    row, col = square
    colour = piece.split("_")[0]
    current_piece = piece.split("_")[1]
    if current_piece == "king":
        highlights = piece_moves[current_piece](row, col, board.grid, colour, board)
    elif current_piece == "pawn":
        highlights = piece_moves[current_piece](row, col, board.grid, colour    , board.en_passant_ts)
    else:
        highlights = piece_moves[current_piece](row, col, board.grid, colour)
    king_pos = board.white_king if colour == "white" else board.black_king
    legal_highlights = [move for move in highlights if is_legal_move(board.grid, colour, square, move, king_pos)]

    return square, legal_highlights

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

                if piece is not None and piece.startswith(board.turn):
                    selected_square, highlights = select_piece(square, piece, board, piece_moves)
                    
                else:
                    # second click — move if the square is a legal move
                    if square in highlights:
                        board.move_piece(selected_square, square)
                        
                        total_legal_moves = []
                        for row in range(8):
                            for col in range(8):
                                piece = board.grid[row][col]
                                if piece is not None and piece.startswith(board.turn):
                                    _, legal_moves = select_piece((row, col), piece, board, piece_moves)
                                    total_legal_moves += legal_moves
                        king_pos = board.white_king if board.turn == "white" else board.black_king
                        if not total_legal_moves and in_check(board.grid, board.turn, king_pos):
                            if board.turn == "white":
                                print("checkmate black wins")
                            else:
                                print("checkmate white wins")
                        elif not total_legal_moves:
                            print("stalemate")
                        selected_square = None
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