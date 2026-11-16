"""The rules of chess and the bots for «Schach» (schach.py) – pure Python, no state outside a Position.

Board: a 10 × 12 mailbox (120 cells; the frame of 2 rows / 1 column around the 8 × 8 board makes «off the board»
cheap to test). a8 = 21, h8 = 28, a1 = 91, h1 = 98. White pieces are upper case (PNBRQK), black lower case,
'.' an empty square, ' ' off the board. White pawns move towards smaller numbers (-10).

Rules: all legal moves incl. check, castling (not out of, through or into check), en passant, promotion (Q, R, B, N);
the end: checkmate, stalemate, threefold repetition, the 50-move rule (automatic), insufficient material
(K–K, K+B–K, K+N–K, K+B(s)–K+B(s) with all bishops on one colour).
Notation: moves are (from, to, promo) with promo '' or one of 'qrbn'; uci() / san() for the move list.

Bots: easy – a random legal move, captures preferred; normal – 2 plies minimax on material + mobility;
hard – iterative deepening alpha-beta (depth 3, 4 when the time allows) with move ordering (best move of the last
depth, MVV-LVA captures, promotions), piece-square tables and a short capture search (quiescence), within ~1.6 s.
"""
from __future__ import annotations

import random
import time

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
FILES = "abcdefgh"
N, S, E, W = -10, 10, 1, -1
KNIGHT = (-21, -19, -12, -8, 8, 12, 19, 21)
BISHOP = (-11, -9, 9, 11)
ROOK = (-10, -1, 1, 10)
KING = BISHOP + ROOK
SLIDES = {"b": BISHOP, "r": ROOK, "q": KING}
VALUE = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 0}
MATE = 100000

# piece-square tables (white's view, a8 first) – the well-known «simplified evaluation» values
PST64 = {
    "p": [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10, 5, 5, 10, 25, 25, 10, 5, 5,
          0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5, 5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    "n": [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40, -30, 0, 10, 15, 15, 10, 0, -30,
          -30, 5, 15, 20, 20, 15, 5, -30, -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30,
          -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
    "b": [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 10, 10, 5, 0, -10,
          -10, 5, 5, 10, 10, 5, 5, -10, -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10,
          -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
    "r": [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
    "q": [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 5, 5, 5, 0, -10,
          -5, 0, 5, 5, 5, 5, 0, -5, 0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10,
          -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
    "k": [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
          -30, -40, -40, -50, -50, -40, -40, -30, -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10,
          20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
}


def sq(f: int, r: int) -> int:
    """File 0..7 (a..h), rank 0..7 (1..8) → mailbox index."""
    return 21 + f + 10 * (7 - r)


def name(s: int) -> str:
    return FILES[s % 10 - 1] + str(8 - (s // 10 - 2))


def parse_sq(t: str) -> int:
    if not isinstance(t, str) or len(t) != 2 or t[0] not in FILES or t[1] not in "12345678":
        raise ValueError("bad square")
    return sq(FILES.index(t[0]), int(t[1]) - 1)


def _pst120() -> dict:
    out = {}
    for p, tab in PST64.items():
        w, b = [0] * 120, [0] * 120
        for i in range(64):
            row, f = divmod(i, 8)
            s = 21 + f + 10 * row
            w[s] = VALUE[p] + tab[i]
            b[s] = -(VALUE[p] + tab[(7 - row) * 8 + f])
        out[p.upper()], out[p] = w, b
    return out


PST = _pst120()
CORNERS = {"K": (98, 96, 97, 95), "Q": (91, 94, 93, 95), "k": (28, 26, 27, 25), "q": (21, 24, 23, 25)}  # rook from/to, king to, king from
ROOK_HOME = {98: "K", 91: "Q", 28: "k", 21: "q"}


class Position:
    __slots__ = ("b", "white", "castle", "ep", "half", "full", "score")

    def __init__(self, b, white, castle, ep, half, full, score=None):
        self.b, self.white, self.castle, self.ep, self.half, self.full = b, white, castle, ep, half, full
        self.score = score if score is not None else sum(PST[c][i] for i, c in enumerate(b) if c not in " .")

    # ---------- FEN
    @classmethod
    def from_fen(cls, fen: str = START_FEN) -> "Position":
        parts = fen.split()
        rows = parts[0].split("/")
        if len(rows) != 8:
            raise ValueError("bad FEN")
        b = [" "] * 120
        for r, row in enumerate(rows):
            f = 0
            for ch in row:
                if ch.isdigit():
                    for _ in range(int(ch)):
                        b[21 + f + 10 * r] = "."
                        f += 1
                else:
                    if ch.lower() not in "pnbrqk":
                        raise ValueError("bad FEN")
                    b[21 + f + 10 * r] = ch
                    f += 1
            if f != 8:
                raise ValueError("bad FEN")
        white = (parts[1] if len(parts) > 1 else "w") == "w"
        castle = "" if len(parts) < 3 or parts[2] == "-" else parts[2]
        ep = 0 if len(parts) < 4 or parts[3] == "-" else parse_sq(parts[3])
        half = int(parts[4]) if len(parts) > 4 else 0
        full = int(parts[5]) if len(parts) > 5 else 1
        return cls(b, white, castle, ep, half, full)

    def placement(self) -> str:
        rows = []
        for r in range(8):
            row, empty = "", 0
            for f in range(8):
                c = self.b[21 + f + 10 * r]
                if c == ".":
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += c
            rows.append(row + (str(empty) if empty else ""))
        return "/".join(rows)

    def fen(self) -> str:
        return f"{self.placement()} {'w' if self.white else 'b'} {self.castle or '-'} {name(self.ep) if self.ep else '-'} {self.half} {self.full}"

    def key(self) -> str:
        """The position for threefold repetition: pieces, side, castling rights, en passant only if it can be taken."""
        ep = "-"
        if self.ep and any(m[1] == self.ep and self.b[m[0]] in "Pp" for m in self.legal()):
            ep = name(self.ep)
        return f"{self.placement()} {'w' if self.white else 'b'} {self.castle or '-'} {ep}"

    # ---------- attacks
    def attacked(self, s: int, by_white: bool) -> bool:
        b = self.b
        if by_white:
            if b[s + 9] == "P" or b[s + 11] == "P":
                return True
            P, Nn, Bb, Rr, Qq, Kk = "P", "N", "B", "R", "Q", "K"
        else:
            if b[s - 9] == "p" or b[s - 11] == "p":
                return True
            P, Nn, Bb, Rr, Qq, Kk = "p", "n", "b", "r", "q", "k"
        for d in KNIGHT:
            if b[s + d] == Nn:
                return True
        for d in KING:
            if b[s + d] == Kk:
                return True
        for d in BISHOP:
            t = s + d
            while b[t] == ".":
                t += d
            if b[t] == Bb or b[t] == Qq:
                return True
        for d in ROOK:
            t = s + d
            while b[t] == ".":
                t += d
            if b[t] == Rr or b[t] == Qq:
                return True
        return False

    def king(self, white: bool) -> int:
        return self.b.index("K" if white else "k")

    def in_check(self, white: bool | None = None) -> bool:
        w = self.white if white is None else white
        return self.attacked(self.king(w), not w)

    # ---------- moves
    def pseudo(self, captures_only: bool = False) -> list[tuple]:
        b, out, white = self.b, [], self.white
        own = str.isupper if white else str.islower
        for s in range(21, 99):
            c = b[s]
            if c in " ." or not own(c):
                continue
            p = c.lower()
            if p == "p":
                fwd, start, last = (N, 8, 2) if white else (S, 3, 9)
                t = s + fwd
                promo = t // 10 == last
                if b[t] == "." and (not captures_only or promo):
                    if promo:
                        out += [(s, t, x) for x in "qrbn"]
                    else:
                        out.append((s, t, ""))
                        if s // 10 == start and b[t + fwd] == ".":
                            out.append((s, t + fwd, ""))
                for t in (s + fwd - 1, s + fwd + 1):
                    x = b[t]
                    if (x not in " ." and not own(x)) or t == self.ep:
                        if promo:
                            out += [(s, t, y) for y in "qrbn"]
                        else:
                            out.append((s, t, ""))
            elif p == "n" or p == "k":
                for d in (KNIGHT if p == "n" else KING):
                    t = s + d
                    x = b[t]
                    if x == ".":
                        if not captures_only:
                            out.append((s, t, ""))
                    elif x != " " and not own(x):
                        out.append((s, t, ""))
            else:
                for d in SLIDES[p]:
                    t = s + d
                    while True:
                        x = b[t]
                        if x == ".":
                            if not captures_only:
                                out.append((s, t, ""))
                        elif x == " " or own(x):
                            break
                        else:
                            out.append((s, t, ""))
                            break
                        t += d
        if not captures_only:                                      # castling: not out of, through or into check
            for side in (("K", "Q") if white else ("k", "q")):
                if side in self.castle:
                    rf, rt, kt, kf = CORNERS[side]
                    king = "K" if white else "k"
                    if b[kf] != king or b[rf] != ("R" if white else "r"):
                        continue
                    lo, hi = min(rf, kf), max(rf, kf)
                    if any(b[i] != "." for i in range(lo + 1, hi)):
                        continue
                    if any(self.attacked(i, not white) for i in (kf, (kf + kt) // 2, kt)):
                        continue
                    out.append((kf, kt, ""))
        return out

    def make(self, m: tuple) -> "Position":
        frm, to, promo = m
        b = self.b[:]
        c = b[frm]
        cap = b[to]
        score = self.score - PST[c][frm]
        if cap != ".":
            score -= PST[cap][to]
        p = c.lower()
        ep = 0
        if p == "p":
            if to == self.ep:                                      # en passant: the pawn behind
                behind = to + (S if self.white else N)
                score -= PST[b[behind]][behind]
                b[behind] = "."
            if abs(to - frm) == 20:
                ep = (to + frm) // 2
            if promo:
                c = promo.upper() if self.white else promo
        elif p == "k" and abs(to - frm) == 2:                      # castling: the rook jumps over
            side = ("K" if to > frm else "Q") if self.white else ("k" if to > frm else "q")
            rf, rt, _, _ = CORNERS[side]
            r = b[rf]
            score += PST[r][rt] - PST[r][rf]
            b[rt], b[rf] = r, "."
        b[to], b[frm] = c, "."
        score += PST[c][to]
        castle = self.castle
        if castle:
            if p == "k":
                castle = castle.replace("K", "").replace("Q", "") if self.white else castle.replace("k", "").replace("q", "")
            for s_ in (frm, to):
                if s_ in ROOK_HOME:
                    castle = castle.replace(ROOK_HOME[s_], "")
        half = 0 if p == "p" or cap != "." else self.half + 1
        return Position(b, not self.white, castle, ep, half, self.full + (0 if self.white else 1), score)

    def legal(self) -> list[tuple]:
        out = []
        for m in self.pseudo():
            n = self.make(m)
            if not n.attacked(n.king(self.white), n.white):
                out.append(m)
        return out

    def is_capture(self, m: tuple) -> bool:
        return self.b[m[1]] != "." or (m[1] == self.ep and self.b[m[0]] in "Pp")

    # ---------- the end
    def insufficient(self) -> bool:
        pieces = [(i, c) for i, c in enumerate(self.b) if c not in " .Kk"]
        if not pieces:
            return True
        if any(c in "PpRrQq" for _, c in pieces):
            return False
        if len(pieces) == 1:
            return True                                            # K+N or K+B against K
        if all(c in "Bb" for _, c in pieces):                     # only bishops, all on one colour
            colours = {((i % 10) + (i // 10)) % 2 for i, _ in pieces}
            return len(colours) == 1
        return False

    def has_mating_material(self, white: bool) -> bool:
        """Could this side ever mate (for a flag fall: without it the game is a draw)?"""
        mine = [c for c in self.b if c not in " .Kk" and c.isupper() == white]
        if any(c.lower() in "pqr" for c in mine):
            return True
        return len(mine) >= 2 or (len(mine) == 1 and any(c not in " .Kk" and c.isupper() != white for c in self.b))

    # ---------- notation
    def uci(self, m: tuple) -> str:
        return name(m[0]) + name(m[1]) + (m[2] or "")

    def san(self, m: tuple, legal: list | None = None) -> str:
        frm, to, promo = m
        c = self.b[frm]
        p = c.lower()
        legal = legal if legal is not None else self.legal()
        if p == "k" and abs(to - frm) == 2:
            s = "O-O" if to > frm else "O-O-O"
        else:
            cap = self.is_capture(m)
            if p == "p":
                s = (name(frm)[0] + "x" if cap else "") + name(to) + ("=" + promo.upper() if promo else "")
            else:
                others = [o for o in legal if o[1] == to and o[0] != frm and self.b[o[0]] == c]
                dis = ""
                if others:
                    if all(o[0] % 10 != frm % 10 for o in others):
                        dis = name(frm)[0]
                    elif all(o[0] // 10 != frm // 10 for o in others):
                        dis = name(frm)[1]
                    else:
                        dis = name(frm)
                s = p.upper() + dis + ("x" if cap else "") + name(to)
        n = self.make(m)
        if n.in_check():
            s += "#" if not n.legal() else "+"
        return s

    def parse_move(self, frm: str, to: str, promo: str | None = None) -> tuple:
        f, t = parse_sq(frm), parse_sq(to)
        return (f, t, (promo or "").lower()[:1])


# ================================================================ bots
def _mvv_lva(pos: Position, m: tuple) -> int:
    x = pos.b[m[1]]
    v = VALUE[x.lower()] if x != "." else (100 if m[1] == pos.ep and pos.b[m[0]] in "Pp" else 0)
    return v * 10 - VALUE[pos.b[m[0]].lower()] // 10 + (800 if m[2] == "q" else 0)


def _rel(pos: Position) -> int:
    return pos.score if pos.white else -pos.score


def bot_easy(pos: Position, rng: random.Random) -> tuple:
    moves = pos.legal()
    caps = [m for m in moves if pos.is_capture(m)]
    if caps and rng.random() < 0.75:
        return rng.choice(caps)
    return rng.choice(moves)


def _material(pos: Position) -> int:
    return sum(VALUE[c.lower()] * (1 if c.isupper() else -1) for c in pos.b if c not in " .")


def _mobility(pos: Position) -> int:
    """Pseudo-legal moves of white minus black (a cheap measure of activity)."""
    w = Position(pos.b, True, "", pos.ep, 0, 1, 0)
    k = Position(pos.b, False, "", pos.ep, 0, 1, 0)
    return len(w.pseudo()) - len(k.pseudo())


def bot_normal(pos: Position, rng: random.Random, keys: list | None = None) -> tuple:
    """2 plies: my move, the opponent's best answer – material and mobility (10 per move)."""
    me_white = pos.white
    sign = 1 if me_white else -1
    best, best_v = [], -10 ** 9
    for m in pos.legal():
        n = pos.make(m)
        replies = n.legal()
        if not replies:
            v = MATE if n.in_check() else 0
        elif keys and keys.count(n.key()) >= 2:
            v = 0
        else:
            v = 10 ** 9
            for r in replies:
                q = n.make(r)
                if q.in_check() and not q.legal():
                    e = -MATE
                else:
                    e = sign * (_material(q) + 10 * _mobility(q))
                if e < v:
                    v = e
        v += rng.random() * 6                                    # a little variety between equal moves
        if v > best_v:
            best, best_v = [m], v
    return best[0] if best else pos.legal()[0]


class _Timeout(Exception):
    pass


class Searcher:
    def __init__(self, limit: float = 1.6, max_depth: int = 4, now=time.monotonic):
        self.limit, self.max_depth, self.now = limit, max_depth, now
        self.nodes = 0

    def _tick(self):
        self.nodes += 1
        if self.nodes & 511 == 0 and self.now() > self.deadline:
            raise _Timeout

    def quiesce(self, pos: Position, alpha: int, beta: int, depth: int) -> int:
        self._tick()
        stand = _rel(pos)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        if depth <= 0:
            return stand
        moves = sorted(pos.pseudo(True), key=lambda m: -_mvv_lva(pos, m))
        for m in moves:
            n = pos.make(m)
            if n.attacked(n.king(pos.white), n.white):
                continue
            v = -self.quiesce(n, -beta, -alpha, depth - 1)
            if v >= beta:
                return v
            if v > alpha:
                alpha = v
        return alpha

    def search(self, pos: Position, depth: int, alpha: int, beta: int, ply: int) -> int:
        if depth <= 0:
            return self.quiesce(pos, alpha, beta, 4)
        self._tick()
        if pos.half >= 100:
            return 0
        moves = pos.pseudo()
        moves.sort(key=lambda m: -_mvv_lva(pos, m) if pos.is_capture(m) or m[2] else 0)
        any_legal = False
        best = -MATE * 2
        for m in moves:
            n = pos.make(m)
            if n.attacked(n.king(pos.white), n.white):
                continue
            any_legal = True
            v = -self.search(n, depth - 1, -beta, -alpha, ply + 1)
            if v > best:
                best = v
            if v > alpha:
                alpha = v
            if alpha >= beta:
                break
        if not any_legal:
            return -(MATE - ply) if pos.in_check() else 0
        return best

    def best(self, pos: Position, keys: list | None = None, rng: random.Random | None = None) -> tuple:
        self.deadline = self.now() + self.limit
        moves = pos.legal()
        if len(moves) == 1:
            return moves[0]
        if rng:
            rng.shuffle(moves)                                    # variety: equal moves are taken in a random order
        moves.sort(key=lambda m: -_mvv_lva(pos, m) if pos.is_capture(m) or m[2] else 0)
        rep = {m for m in moves if keys and keys.count(pos.make(m).key()) >= 2}   # a third repetition = a draw
        best_move = moves[0]
        for depth in range(1, self.max_depth + 1):
            try:
                scores = {}
                alpha = -MATE * 2
                found = moves[0]
                for m in moves:
                    n = pos.make(m)
                    v = 0 if m in rep else -self.search(n, depth - 1, -MATE * 2, -alpha, 1)
                    if v > alpha:                                 # strictly better: the others are only bounds
                        alpha, found = v, m
                        scores[m] = v
                    else:
                        scores[m] = min(v, alpha) - 1
            except _Timeout:
                break
            moves.sort(key=lambda m: -scores[m])
            best_move = found
            if scores[best_move] >= MATE - 100:                   # a mate found: no need to look deeper
                break
            if depth >= 3 and self.now() > self.deadline - self.limit * 0.55:
                break                                             # the next depth would not finish in time
        return best_move

    def evaluate(self, pos: Position, depth: int = 2) -> int:
        """Score for the side to move (used to answer a draw offer)."""
        self.deadline = self.now() + self.limit
        try:
            return self.search(pos, depth, -MATE * 2, MATE * 2, 0)
        except _Timeout:
            return _rel(pos)


def bot_move(pos: Position, level: str, rng: random.Random | None = None, keys: list | None = None, limit: float = 1.6) -> tuple:
    rng = rng or random.SystemRandom()
    if level == "easy":
        return bot_easy(pos, rng)
    if level == "normal":
        return bot_normal(pos, rng, keys)
    return Searcher(limit=limit).best(pos, keys, rng)
