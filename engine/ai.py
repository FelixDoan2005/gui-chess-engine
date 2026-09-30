from ui.chess_logic import Board, get_all_legal_moves, select_piece, in_check, insufficient_material, pawn_attack_squares
from ui.chess_logic import KNIGHT_JUMPS, KING_STEPS, DIAGONAL_DIRECTIONS, STRAIGHT_DIRECTIONS

CHECKMATE_SCORE = 999999

# Difficulty level -> search depth. One level per depth for now; each
# level will also toggle a specific evaluation feature on/off later.
DIFFICULTY_DEPTH = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
}

# Piece-square tables: from https://chessprogramming.org/Simplified_Evaluation_Function
# posted by Tomasz Michniewski
PAWN_TABLE = [
    [0,   0,   0,   0,   0,   0,   0,   0],
    [50, 50,  50,  50,  50,  50,  50,  50],
    [10, 10,  20,  30,  30,  20,  10,  10],
    [5,   5,  10,  25,  25,  10,   5,   5],
    [0,   0,   0,  20,  20,   0,   0,   0],
    [5,  -5, -10,   0,   0, -10,  -5,   5],
    [5,  10,  10, -20, -20,  10,  10,   5],
    [0,   0,   0,   0,   0,   0,   0,   0],
]

KNIGHT_TABLE = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20,   0,   0,   0,   0, -20, -40],
    [-30,   0,  10,  15,  15,  10,   0, -30],
    [-30,   5,  15,  20,  20,  15,   5, -30],
    [-30,   0,  15,  20,  20,  15,   0, -30],
    [-30,   5,  10,  15,  15,  10,   5, -30],
    [-40, -20,   0,   5,   5,   0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]

BISHOP_TABLE = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,  10,  10,   5,   0, -10],
    [-10,   5,   5,  10,  10,   5,   5, -10],
    [-10,   0,  10,  10,  10,  10,   0, -10],
    [-10,  10,  10,  10,  10,  10,  10, -10],
    [-10,   5,   0,   0,   0,   0,   5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
]

ROOK_TABLE = [
    [0,   0,   0,   0,   0,   0,   0,   0],
    [5,  10,  10,  10,  10,  10,  10,   5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [-5,  0,   0,   0,   0,   0,   0,  -5],
    [0,   0,   0,   5,   5,   0,   0,   0],
]

QUEEN_TABLE = [
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,   5,   5,   5,   0, -10],
    [-5,    0,   5,   5,   5,   5,   0,  -5],
    [0,     0,   5,   5,   5,   5,   0,  -5],
    [-10,   5,   5,   5,   5,   5,   0, -10],
    [-10,   0,   5,   0,   0,   0,   0, -10],
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
]

KING_TABLE = [
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [20,   20,   0,   0,   0,   0,  20,  20],
    [20,   30,  10,   0,   0,  10,  30,  20],
]

# Blended in over KING_TABLE as pieces come off (see endgame_weight): with few
# pieces left the king is safe in the centre and needs to be active.
KING_ENDGAME_TABLE = [
    [-50, -40, -30, -20, -20, -30, -40, -50],
    [-30, -20, -10,   0,   0, -10, -20, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -30,   0,   0,   0,   0, -30, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50],
]

PIECE_SQUARE_TABLES = {
    "pawn": PAWN_TABLE,
    "knight": KNIGHT_TABLE,
    "bishop": BISHOP_TABLE,
    "rook": ROOK_TABLE,
    "queen": QUEEN_TABLE,
    "king": KING_TABLE,
}


def piece_square_value(kind, colour, row, col, weight=0.0):
    if colour == "white":
        table_row = row
    else:
        table_row = 7 - row

    if kind == "king":
        return blend(KING_TABLE[table_row][col], KING_ENDGAME_TABLE[table_row][col], weight)
    return PIECE_SQUARE_TABLES[kind][table_row][col]


PIECE_VALUES = {
    "pawn": 1,
    "bishop": 3,
    "knight": 3,
    "rook": 5,
    "queen": 9,
    "king": 100
}


def evaluate(board):
    grid = board.grid
    # Worked out once here and shared, instead of each heuristic scanning the
    # board and recomputing the same things.
    pieces = piece_coverage(grid)
    files = both_pawn_files(grid)
    weight = endgame_weight(board, pieces)

    score = 0
    for r, c, colour, kind, _ in pieces:
        value = PIECE_VALUES[kind]
        positional = piece_square_value(kind, colour, r, c, weight) / 100

        total_gain = value + positional

        if colour == "white":
            score += total_gain
        else:
            score -= total_gain

    return (score + mobility(board, weight, pieces) + pawn_structure(board, weight, files)
            + bishop_pair(board, weight) + mop_up(board) + rook_open_files(board)
            + knight_outposts(board, files) + bishop_pawn_pairs(board, weight, files)
            + king_pawn_shield(board, pieces) + king_attackers(board, weight, pieces)
            + hanging_pieces(board, weight, pieces) + centre_control(board, weight, pieces))


# Points per safe move, from Fruit 2.1 (eval.cpp KnightMob/BishopMob/RookMob/
# QueenMob, centipawns / 100). The queen gets least per move because it has the
# most moves; rooks and queens get more in the endgame, when lines are open.
MOBILITY_WEIGHTS = {
    "knight": 0.04,
    "bishop": 0.05,
    "rook": 0.02,
    "queen": 0.01,
}
MOBILITY_WEIGHTS_ENDGAME = {
    "knight": 0.04,
    "bishop": 0.05,
    "rook": 0.04,
    "queen": 0.02,
}

def moves_from(covered, grid, colour):
    # The squares a piece can actually move to: what it covers, minus squares
    # holding its own side's pieces (those it only defends).
    moves = []
    for row, col in covered:
        target = grid[row][col]
        if target is None or not target.startswith(colour):
            moves.append((row, col))
    return moves


def mobility(board, weight=None, pieces=None):
    if weight is None:
        weight = endgame_weight(board)
    if pieces is None:
        pieces = piece_coverage(board.grid)
    grid = board.grid

    # Squares each side's pieces shouldn't count: ones attacked by enemy pawns.
    unsafe = {"white": set(), "black": set()}
    for _, _, colour, kind, covered in pieces:
        if kind == "pawn":
            if colour == "white":
                unsafe["black"].update(covered)
            else:
                unsafe["white"].update(covered)

    per_move = {}
    for kind in MOBILITY_WEIGHTS:
        per_move[kind] = blend(MOBILITY_WEIGHTS[kind], MOBILITY_WEIGHTS_ENDGAME[kind], weight)

    score = 0
    for _, _, colour, kind, covered in pieces:
        if kind not in MOBILITY_WEIGHTS:
            continue

        safe_moves = 0
        for square in moves_from(covered, grid, colour):
            if square not in unsafe[colour]:
                safe_moves += 1
        value = safe_moves * per_move[kind]

        if colour == "white":
            score += value
        else:
            score -= value

    return score


# Pawn structure, from Fruit 2.1 (pawn.cpp, centipawns / 100). Fruit has a
# middlegame and an endgame value for each, blended by endgame_weight.
DOUBLED_PAWN_PENALTY = {"middlegame": 0.10, "endgame": 0.20}
ISOLATED_PAWN_PENALTY = {"middlegame": 0.10, "endgame": 0.20}
ISOLATED_OPEN_PAWN_PENALTY = {"middlegame": 0.20, "endgame": 0.20}  # no enemy pawn in front of it

# Passed pawns: min + (max - min) * scale / 256, where scale is Fruit's Bonus[]
# table indexed by squares advanced from the starting square (5 = one step
# from promoting). Nothing extra until the pawn reaches its 4th rank.
PASSED_PAWN_MIN = {"middlegame": 0.10, "endgame": 0.20}
PASSED_PAWN_MAX = {"middlegame": 0.70, "endgame": 1.40}
PASSED_PAWN_SCALE = [0, 0, 26, 77, 154, 256]


def pawn_files(grid, colour):
    column_with_pawns = {}
    for r in range(8):
        for c in range(8):
            piece = grid[r][c]
            if piece is None:
                continue
            piece_colour, kind = piece.split("_")
            if kind == "pawn" and piece_colour == colour:
                if c not in column_with_pawns:
                    column_with_pawns[c] = [r]
                else:
                    column_with_pawns[c].append(r)
    return column_with_pawns



def is_passed(row, col, colour, enemy_files):
    for check_col in (col - 1, col, col + 1):
        for enemy_row in enemy_files.get(check_col, []):
            if colour == "white" and enemy_row < row:
                return False
            if colour == "black" and enemy_row > row:
                return False
    return True


def enemy_pawn_in_front(row, col, colour, enemy_files):
    for enemy_row in enemy_files.get(col, []):
        if colour == "white" and enemy_row < row:
            return True
        if colour == "black" and enemy_row > row:
            return True
    return False


def both_pawn_files(grid):
    return {"white": pawn_files(grid, "white"), "black": pawn_files(grid, "black")}


def pawn_structure(board, weight=None, files=None):
    if weight is None:
        weight = endgame_weight(board)
    if files is None:
        files = both_pawn_files(board.grid)

    doubled = blend(DOUBLED_PAWN_PENALTY["middlegame"], DOUBLED_PAWN_PENALTY["endgame"], weight)
    isolated_penalty = blend(ISOLATED_PAWN_PENALTY["middlegame"], ISOLATED_PAWN_PENALTY["endgame"], weight)
    isolated_open = blend(ISOLATED_OPEN_PAWN_PENALTY["middlegame"], ISOLATED_OPEN_PAWN_PENALTY["endgame"], weight)
    passed_min = blend(PASSED_PAWN_MIN["middlegame"], PASSED_PAWN_MIN["endgame"], weight)
    passed_max = blend(PASSED_PAWN_MAX["middlegame"], PASSED_PAWN_MAX["endgame"], weight)

    score = 0

    for colour in ("white", "black"):
        if colour == "white":
            enemy = "black"
        else:
            enemy = "white"
        own_files = files[colour]
        enemy_files = files[enemy]

        side_score = 0

        for col, rows in own_files.items():
            if len(rows) > 1:
                side_score -= doubled * (len(rows) - 1)

            isolated = col - 1 not in own_files and col + 1 not in own_files

            for row in rows:
                if isolated:
                    if enemy_pawn_in_front(row, col, colour, enemy_files):
                        side_score -= isolated_penalty
                    else:
                        side_score -= isolated_open

                if is_passed(row, col, colour, enemy_files):
                    if colour == "white":
                        advanced = 6 - row   # white pawns start on row 6
                    else:
                        advanced = row - 1   # black pawns start on row 1
                    advanced = max(0, min(advanced, 5))
                    side_score += passed_min + (passed_max - passed_min) * PASSED_PAWN_SCALE[advanced] / 256

        if colour == "white":
            score += side_score
        else:
            score -= side_score

    return score


# Larry Kaufman's 2021 figures: +0.3 in the middlegame, +0.5 in the endgame
# (and +0.4 in between, which blending gives automatically).
BISHOP_PAIR_BONUS = {"middlegame": 0.3, "endgame": 0.5}

# Tapered evaluation, as in Fruit 2.1 (chessprogramming.org/Tapered_Eval).
# Phase weights: 24 in total at the start of the game, falling as pieces come
# off. Any value with a middlegame and an endgame version is blended by how far
# the game has moved towards the endgame, instead of switching at a cutoff.
PHASE_WEIGHTS = {"knight": 1, "bishop": 1, "rook": 2, "queen": 4}
TOTAL_PHASE = 24


def endgame_weight(board, pieces=None):
    # 0.0 with all pieces on the board, rising to 1.0 when only kings and
    # pawns are left.
    if pieces is None:
        pieces = piece_coverage(board.grid)
    remaining = 0
    for _, _, _, kind, _ in pieces:
        remaining += PHASE_WEIGHTS.get(kind, 0)
    return max(0, TOTAL_PHASE - remaining) / TOTAL_PHASE  # max() in case promotions add material


def blend(middlegame_value, endgame_value, weight):
    return middlegame_value + (endgame_value - middlegame_value) * weight


def bishop_pair(board, weight=None):
    if weight is None:
        weight = endgame_weight(board)
    white_bishops = 0
    black_bishops = 0
    for row in board.grid:
        for piece in row:
            if piece == "white_bishop":
                white_bishops += 1
            elif piece == "black_bishop":
                black_bishops += 1

    bonus = blend(BISHOP_PAIR_BONUS["middlegame"], BISHOP_PAIR_BONUS["endgame"], weight)

    score = 0
    if white_bishops >= 2:
        score += bonus
    if black_bishops >= 2:
        score -= bonus
    return score


# chessprogramming.org/Rook_on_Open_File: open-file bonuses range 8-20
# centipawns (20 from Toga); a semi-open file typically gets half. Fruit 2.1
# uses the same: RookOpenFile 20, RookSemiOpenFile 10.
ROOK_OPEN_FILE_BONUS = 0.20       # no pawns at all on the rook's column
ROOK_SEMI_OPEN_FILE_BONUS = 0.10  # only enemy pawns on the rook's column


def rook_open_files(board):
    white_pawn_cols = set()
    black_pawn_cols = set()
    rooks = []
    for r in range(8):
        for c in range(8):
            piece = board.grid[r][c]
            if piece == "white_pawn":
                white_pawn_cols.add(c)
            elif piece == "black_pawn":
                black_pawn_cols.add(c)
            elif piece in ("white_rook", "black_rook"):
                rooks.append((piece, c))

    score = 0
    for piece, col in rooks:
        if piece == "white_rook":
            own_pawns, enemy_pawns, sign = white_pawn_cols, black_pawn_cols, 1
        else:
            own_pawns, enemy_pawns, sign = black_pawn_cols, white_pawn_cols, -1

        if col in own_pawns:
            continue  # closed: blocked by its own pawn
        if col in enemy_pawns:
            score += sign * ROOK_SEMI_OPEN_FILE_BONUS
        else:
            score += sign * ROOK_OPEN_FILE_BONUS
    return score


def defended_by_own_pawn(grid, row, col, colour):
    if colour == "white":
        pawn_row = row + 1
    else:
        pawn_row = row - 1
    if not 0 <= pawn_row <= 7:
        return False
    for pawn_col in (col - 1, col + 1):
        if 0 <= pawn_col <= 7 and grid[pawn_row][pawn_col] == f"{colour}_pawn":
            return True
    return False


def attackable_by_enemy_pawn(row, col, colour, enemy_files):
    # True if an enemy pawn on a neighbouring column is still behind this
    # square (from the enemy's side), so it could advance and attack it.
    for pawn_col in (col - 1, col + 1):
        for pawn_row in enemy_files.get(pawn_col, []):
            if colour == "white" and pawn_row < row:
                return True
            if colour == "black" and pawn_row > row:
                return True
    return False


# chessprogramming.org/Outposts: a strong square in the centre or enemy half,
# defended by an own pawn and no longer attackable by enemy pawns. Toga gives
# a central knight outpost 10 centipawns.
KNIGHT_OUTPOST_BONUS = 0.10
OUTPOST_ROWS = {"white": (2, 3, 4), "black": (3, 4, 5)}


def knight_outposts(board, files=None):
    grid = board.grid
    if files is None:
        files = both_pawn_files(grid)
    enemy_files = {"white": files["black"], "black": files["white"]}
    score = 0
    for r in range(8):
        for c in range(8):
            piece = grid[r][c]
            if piece not in ("white_knight", "black_knight"):
                continue
            colour = piece.split("_")[0]
            if r not in OUTPOST_ROWS[colour]:
                continue
            if not defended_by_own_pawn(grid, r, c, colour):
                continue
            if attackable_by_enemy_pawn(r, c, colour, enemy_files[colour]):
                continue
            if colour == "white":
                score += KNIGHT_OUTPOST_BONUS
            else:
                score -= KNIGHT_OUTPOST_BONUS
    return score


# Late game (your idea): a bishop standing on a square its own pawn guards.
# The pawn defends the bishop and, being diagonally next to it, the bishop
# defends the pawn. Only counts if no enemy pawn can ever attack the bishop.
# That is a bishop outpost, so the value is Stockfish 11's (evaluate.cpp
# Outpost = S(30, 21), applied once for a bishop): the endgame 21, divided by
# its endgame pawn value 213, faded in by endgame_weight so it only counts in
# the late game. Being central is already rewarded by the bishop
# piece-square table.
BISHOP_PAWN_PAIR_BONUS = 21 / 213


def bishop_pawn_pairs(board, weight=None, files=None):
    if weight is None:
        weight = endgame_weight(board)
    grid = board.grid
    if files is None:
        files = both_pawn_files(grid)
    bonus = BISHOP_PAWN_PAIR_BONUS * weight
    enemy_files = {"white": files["black"], "black": files["white"]}
    score = 0
    for r in range(8):
        for c in range(8):
            piece = grid[r][c]
            if piece not in ("white_bishop", "black_bishop"):
                continue
            colour = piece.split("_")[0]
            if not defended_by_own_pawn(grid, r, c, colour):
                continue
            if attackable_by_enemy_pawn(r, c, colour, enemy_files[colour]):
                continue
            if colour == "white":
                score += bonus
            else:
                score -= bonus
    return score


# King safety is scaled by the opponent's material, as chessprogramming.org/
# King_Safety describes (TSCP does this), so it matters most while the enemy
# still has attackers and fades as they come off.
MAX_SIDE_PHASE = 12  # one side's PHASE_WEIGHTS at the start: 2N + 2B + 2R + Q


def side_phase(pieces, colour):
    total = 0
    for _, _, piece_colour, kind, _ in pieces:
        if piece_colour == colour:
            total += PHASE_WEIGHTS.get(kind, 0)
    return total


# Pawn shelter, from Fruit 2.1 (eval.cpp shelter_file / shelter_square). On the
# king's file (counted twice) and the files either side, find the nearest own
# pawn in front of the king: penalty = 36 - dist * dist centipawns, where dist
# is 6 for a pawn on its starting square (0), 5 one step up (11), 4 two steps
# up (20), and 0 when there's no pawn in front at all (36).
def shelter_file_penalty(grid, col, king_row, colour):
    if colour == "white":
        rows_in_front = range(king_row, -1, -1)
    else:
        rows_in_front = range(king_row, 8)

    dist = 0
    for row in rows_in_front:
        if grid[row][col] == f"{colour}_pawn":
            if colour == "white":
                dist = row
            else:
                dist = 7 - row
            break
    return 36 - dist * dist


def shelter_penalty(grid, king, colour):
    row, col = king
    penalty = 2 * shelter_file_penalty(grid, col, row, colour)
    for side_col in (col - 1, col + 1):
        if 0 <= side_col <= 7:
            penalty += shelter_file_penalty(grid, side_col, row, colour)
    return penalty / 100


def king_pawn_shield(board, pieces=None):
    grid = board.grid
    if pieces is None:
        pieces = piece_coverage(grid)
    white = shelter_penalty(grid, board.white_king, "white") * side_phase(pieces, "black") / MAX_SIDE_PHASE
    black = shelter_penalty(grid, board.black_king, "black") * side_phase(pieces, "white") / MAX_SIDE_PHASE
    return black - white


# King attack, from Fruit 2.1 (eval.cpp): every enemy piece aimed at the zone
# around your king adds its unit (knight 1, bishop 1, rook 2, queen 4). The
# total is multiplied by KingAttackOpening (20 centipawns) and a weight out of
# 256 that grows with the NUMBER of attackers -- one attacker alone counts 0.
# It's a middlegame-only value in Fruit, so it fades out by endgame_weight.
KING_ATTACK_UNIT = {"knight": 1, "bishop": 1, "rook": 2, "queen": 4}
KING_ATTACK_OPENING = 20
KING_ATTACK_WEIGHT = [0, 0, 128, 192, 224, 240, 248, 252, 254, 255, 256, 256, 256, 256, 256, 256]


def king_zone(king):
    row, col = king
    return {(row + dr, col + dc)
            for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            if 0 <= row + dr <= 7 and 0 <= col + dc <= 7}


def king_attackers(board, weight=None, pieces=None):
    if weight is None:
        weight = endgame_weight(board)
    grid = board.grid
    if pieces is None:
        pieces = piece_coverage(grid)

    zones = {"white": king_zone(board.white_king), "black": king_zone(board.black_king)}
    units = {"white": 0, "black": 0}      # attack units aimed at the other side's king
    attackers = {"white": 0, "black": 0}  # number of pieces aimed at the other side's king

    for _, _, colour, kind, covered in pieces:
        if kind not in KING_ATTACK_UNIT:
            continue
        if colour == "white":
            enemy = "black"
        else:
            enemy = "white"
        if zones[enemy].intersection(moves_from(covered, grid, colour)):
            units[colour] += KING_ATTACK_UNIT[kind]
            attackers[colour] += 1

    score = 0
    for colour in ("white", "black"):
        count = min(attackers[colour], len(KING_ATTACK_WEIGHT) - 1)
        attack = units[colour] * KING_ATTACK_OPENING * KING_ATTACK_WEIGHT[count] / 256 / 100
        attack = attack * (1 - weight)
        if colour == "white":
            score += attack
        else:
            score -= attack
    return score


SLIDE_DIRECTIONS = {
    "bishop": DIAGONAL_DIRECTIONS,
    "rook": STRAIGHT_DIRECTIONS,
    "queen": DIAGONAL_DIRECTIONS + STRAIGHT_DIRECTIONS,
}


def squares_covered_by(grid, r, c, colour, kind):
    # Squares one piece attacks, INCLUDING squares holding its own side's
    # pieces (i.e. what it defends). Sliding pieces stop at the first piece.
    if kind == "pawn":
        return pawn_attack_squares(r, c, colour)

    covered = []
    if kind in ("knight", "king"):
        if kind == "knight":
            steps = KNIGHT_JUMPS
        else:
            steps = KING_STEPS
        for dr, dc in steps:
            if 0 <= r + dr <= 7 and 0 <= c + dc <= 7:
                covered.append((r + dr, c + dc))
    else:
        for dr, dc in SLIDE_DIRECTIONS[kind]:
            nr, nc = r + dr, c + dc
            while 0 <= nr <= 7 and 0 <= nc <= 7:
                covered.append((nr, nc))
                if grid[nr][nc] is not None:
                    break
                nr, nc = nr + dr, nc + dc
    return covered


def piece_coverage(grid):
    # Every piece on the board, with the squares it attacks or defends:
    # (row, col, colour, kind, covered). evaluate() builds this once per
    # position and shares it with the heuristics that need it.
    pieces = []
    for r in range(8):
        for c in range(8):
            piece = grid[r][c]
            if piece is not None:
                colour, kind = piece.split("_")
                pieces.append((r, c, colour, kind, squares_covered_by(grid, r, c, colour, kind)))
    return pieces


# Per hanging piece, from Stockfish 11 (evaluate.cpp Hanging = S(69, 36)),
# converted to pawns with its pawn values (128 middlegame, 213 endgame).
# Stockfish also counts some pieces defended once but attacked twice; this only
# counts pieces that are attacked and not defended at all.
HANGING_PIECE_PENALTY = {"middlegame": 69 / 128, "endgame": 36 / 213}


def hanging_pieces(board, weight=None, pieces=None):
    if weight is None:
        weight = endgame_weight(board)
    if pieces is None:
        pieces = piece_coverage(board.grid)
    penalty = blend(HANGING_PIECE_PENALTY["middlegame"], HANGING_PIECE_PENALTY["endgame"], weight)

    covered = {"white": set(), "black": set()}  # every square each side attacks or defends
    for _, _, colour, _, squares in pieces:
        covered[colour].update(squares)

    score = 0
    for r, c, colour, kind, _ in pieces:
        if kind == "king":
            continue
        if colour == "white":
            enemy = "black"
        else:
            enemy = "white"
        if (r, c) in covered[enemy] and (r, c) not in covered[colour]:
            if colour == "white":
                score -= penalty
            else:
                score += penalty
    return score


# Lyudmil Tsvetkov, Little Chess Evaluation Compendium (2012): +10 centipawns
# for each centre square (d4, e4, d5, e5) that each piece or pawn controls, e.g.
# a knight on f3 covering d4 and e5 gets +20. About 25% lower in the endgame
# (the compendium says "at least" for pawns; applied to all pieces here).
CENTRE_SQUARES = [(3, 3), (3, 4), (4, 3), (4, 4)]   # d5, e5, d4, e4
CENTRE_CONTROL_BONUS = {"middlegame": 0.10, "endgame": 0.075}


def centre_control(board, weight=None, pieces=None):
    if weight is None:
        weight = endgame_weight(board)
    if pieces is None:
        pieces = piece_coverage(board.grid)
    per_square = blend(CENTRE_CONTROL_BONUS["middlegame"], CENTRE_CONTROL_BONUS["endgame"], weight)

    score = 0
    for _, _, colour, _, covered in pieces:
        controlled = 0
        for square in CENTRE_SQUARES:
            if square in covered:
                controlled += 1
        value = controlled * per_square
        if colour == "white":
            score += value
        else:
            score -= value
    return score


# Mop-up evaluation, from Chess 4.x (Slate & Atkin, 1977) via
# chessprogramming.org/Mop-up_Evaluation:
#   4.7 * losing king's distance from the centre + 1.6 * (14 - distance between kings)
# The source gives no units. Tested at /100 and /10 on 80 K+R/K+Q vs K games:
# /100 was too weak to pull the winning king away from the centre (the endgame
# king table outweighed it), so K+Q vs K mated only 14/40; /10 mated 78/80.
# The same page says mop-up is for when one side has "likely a rook or queen
# (or even two different colored bishops)": a rook's worth (5) covers all three.
MOPUP_MIN_ADVANTAGE = 5


def centre_distance(row, col):
    # 0 on the four centre squares, up to 6 in a corner.
    return max(3 - row, row - 4) + max(3 - col, col - 4)


def mop_up(board):
    white_material = 0
    black_material = 0
    for row in board.grid:
        for piece in row:
            if piece is None:
                continue
            colour, kind = piece.split("_")
            if kind == "pawn":
                return 0  # only for pawnless endgames
            if kind == "king":
                continue
            if colour == "white":
                white_material += PIECE_VALUES[kind]
            else:
                black_material += PIECE_VALUES[kind]

    if white_material - black_material >= MOPUP_MIN_ADVANTAGE:
        winning_king, losing_king, sign = board.white_king, board.black_king, 1
    elif black_material - white_material >= MOPUP_MIN_ADVANTAGE:
        winning_king, losing_king, sign = board.black_king, board.white_king, -1
    else:
        return 0

    king_distance = abs(winning_king[0] - losing_king[0]) + abs(winning_king[1] - losing_king[1])
    value = 4.7 * centre_distance(*losing_king) + 1.6 * (14 - king_distance)
    return sign * value / 10


def order_moves(board, moves):
    # Search the most forcing moves first: big captures, and promotions
    # (worth about a queen). On a tie, choose_move keeps the first move
    # it found, so this also makes it promote now rather than later.
    def move_value(move):
        from_sq, to_sq = move
        value = 0

        target = board.get_piece(*to_sq)
        if target is not None:
            value += PIECE_VALUES[target.split("_")[1]]

        moving = board.get_piece(*from_sq)
        if moving.endswith("pawn") and to_sq[0] in (0, 7):
            value += PIECE_VALUES["queen"]

        return value

    return sorted(moves, key=move_value, reverse=True)

def save_state(board):
    grid_copy = []
    for row in board.grid:
        grid_copy.append(row[:])

    return {
        "grid": grid_copy,
        "turn": board.turn,
        "en_passant_ts": board.en_passant_ts,
        "white_king": board.white_king,
        "black_king": board.black_king,
        "white_king_moved": board.white_king_moved,
        "white_rook_kingside_moved": board.white_rook_kingside_moved,
        "white_rook_queenside_moved": board.white_rook_queenside_moved,
        "black_king_moved": board.black_king_moved,
        "black_rook_kingside_moved": board.black_rook_kingside_moved,
        "black_rook_queenside_moved": board.black_rook_queenside_moved,
        "halfmove_clock": board.halfmove_clock,
        "history_len": len(board.history),
    }


def restore_state(board, state):
    board.grid = state["grid"]
    board.turn = state["turn"]
    board.en_passant_ts = state["en_passant_ts"]
    board.white_king = state["white_king"]
    board.black_king = state["black_king"]
    board.white_king_moved = state["white_king_moved"]
    board.white_rook_kingside_moved = state["white_rook_kingside_moved"]
    board.white_rook_queenside_moved = state["white_rook_queenside_moved"]
    board.black_king_moved = state["black_king_moved"]
    board.black_rook_kingside_moved = state["black_rook_kingside_moved"]
    board.black_rook_queenside_moved = state["black_rook_queenside_moved"]
    board.halfmove_clock = state["halfmove_clock"]
    # Undo the positions move_piece added to the history since save_state.
    while len(board.history) > state["history_len"]:
        key = board.history.pop()
        board.position_counts[key] -= 1


def clone_board(board):
    copy = Board()
    restore_state(copy, save_state(board))
    copy.history = list(board.history)
    copy.position_counts = dict(board.position_counts)
    return copy


def is_draw_in_search(board):
    # Stricter than the real rules on purpose: a position that has occurred
    # even once before is scored as a draw, so the search sees repetition
    # coming within a few plies instead of waiting for a third occurrence.
    if board.position_counts[board.history[-1]] >= 2:
        return True
    if board.halfmove_clock >= 100:
        return True
    return insufficient_material(board.grid)


def make_move(board, from_sq, to_sq):
    board.move_piece(from_sq, to_sq)
    row, col = to_sq
    piece = board.grid[row][col]
    if piece.endswith("pawn") and row in (0, 7):
        board.grid[row][col] = piece.split("_")[0] + "_queen"


def negamax(board, piece_moves, depth, alpha, beta):
    if is_draw_in_search(board):
        return 0

    if depth == 0:
        if board.turn == "white":
            return evaluate(board)
        else:
            return -evaluate(board)
    
    moves = get_all_legal_moves(board, piece_moves)

    if len(moves) == 0:
        if board.turn == "white":
            king_pos = board.white_king
        else:
            king_pos = board.black_king
        if in_check(board.grid, board.turn, king_pos):
            return -CHECKMATE_SCORE
        return 0
    for (from_sq, to_sq) in order_moves(board, moves):
        state = save_state(board)
        make_move(board, from_sq, to_sq)
        score = -negamax(board, piece_moves, depth - 1, -beta, -alpha)
        restore_state(board, state)

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


class AI:
    def choose_move(self, board, piece_moves, depth):
        moves = get_all_legal_moves(board, piece_moves)
        alpha = -float('inf')
        beta = float('inf')
        best_move = None
        for (from_sq, to_sq) in order_moves(board, moves):
            state = save_state(board)
            make_move(board, from_sq, to_sq)
            score = -negamax(board, piece_moves, depth - 1, -beta, -alpha)
            restore_state(board, state)
            if score > alpha:
                alpha = score
                best_move = (from_sq, to_sq)
        return best_move


