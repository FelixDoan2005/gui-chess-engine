def evaluate(board):
    pieces = {
        "pawn": 1,
        "bishop": 3,
        "knight": 3,
        "rook": 5,
        "queen": 9,
        "king": 100
    }

    white_sum = 0
    black_sum = 0

    for r in range(8):
        for c in range(8):
            piece = board.grid[r][c]
            if piece is not None:
                if piece.startswith("white"):
                    white_sum += pieces[piece.split("_")[1]]
                else:
                    black_sum += pieces[piece.split("_")[1]]

    return(white_sum,black_sum)


class AI:
    def choose_move(self, board):
        pass
