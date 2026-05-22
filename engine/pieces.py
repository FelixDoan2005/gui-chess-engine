class Piece:
    def __init__(self, color):
        self.color = color

    def legal_moves(self, board, row, col):
        raise NotImplementedError


class Pawn(Piece):
    pass


class Rook(Piece):
    pass


class Knight(Piece):
    pass


class Bishop(Piece):
    pass


class Queen(Piece):
    pass


class King(Piece):
    pass
