import tempfile
import os
os.environ.setdefault('PUSHUUU_HOME', tempfile.mkdtemp())  # never touch real launcher data
import os
import random, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pushuuu_games import SnakeGame, PongGame

# ---------------- Snake ----------------
g = SnakeGame(rng=random.Random(1))
assert len(g.snake) == 3 and g.dir == (1, 0) and g.food not in g.snake and g.alive
head = g.snake[0]; assert g.step() == "move" and g.snake[0] == (head[0] + 1, head[1]) and len(g.snake) == 3

# eating grows + scores + new food never lands on the snake
g = SnakeGame(rng=random.Random(2)); hx, hy = g.snake[0]; g.food = (hx + 1, hy)
assert g.step() == "eat" and len(g.snake) == 4 and g.score == 10 and g.food not in g.snake

# 180-degree turn is ignored; fast double-tap is buffered in order
g = SnakeGame(rng=random.Random(3))
g.turn("left"); assert not g.queue                       # reverse into own neck: ignored
g.turn("up"); g.turn("left"); g.turn("down")             # queue holds 2 max
assert list(g.queue) == [(0, -1), (-1, 0)]
g.step(); assert g.dir == (0, -1); g.step(); assert g.dir == (-1, 0)

# walls kill
g = SnakeGame(cols=6, rows=5, rng=random.Random(4)); g.food = (0, 0)
for _ in range(10):
    if g.step() == "dead": break
assert not g.alive and g.step() == "idle"

# self-collision kills: grow long, then turn back into the body
g = SnakeGame(cols=20, rows=20, rng=random.Random(5))
hx, hy = g.snake[0]
for i in range(3):
    g.food = (g.snake[0][0] + 1, g.snake[0][1]); assert g.step() == "eat"      # length 6
g.turn("up"); g.step(); g.turn("left"); g.step(); g.turn("down"); r = g.step()
assert r == "dead" and not g.alive, r

# the tail cell is free to enter (it moves away), so chasing your own tail is legal
g = SnakeGame(cols=3, rows=3, rng=random.Random(6)); g.snake.clear()
g.snake.extend([(1, 0), (2, 0), (2, 1), (1, 1)]); g.dir = (1, 0)   # 2x2 loop; head (1,0) -> tail (1,1)
g.food = (0, 2); g.turn("down"); assert g.step() == "move" and g.alive   # moves into the vacated tail cell

# a full board is a win
g = SnakeGame(cols=4, rows=1, rng=random.Random(7)); assert g.food == (3, 0)
assert g.step() == "eat" and g.won and not g.alive and g.food is None

# speed ramps up to a floor
g = SnakeGame(rng=random.Random(8)); base = g.tick_ms
g.snake.extend([(0, 0)] * 10); assert g.tick_ms < base
g.snake.extend([(0, 0)] * 100); assert g.tick_ms == 55

# long random walk never crashes and food is always on a free cell
g = SnakeGame(rng=random.Random(9)); rnd = random.Random(10)
for _ in range(5000):
    if not g.alive: g.reset()
    g.turn(rnd.choice(["up", "down", "left", "right"])); g.step()
    assert g.food is None or g.food not in g.snake
    assert len(set(g.snake)) == len(g.snake), "snake overlapped itself while alive"

# ---------------- Pong ----------------
def run(game, seconds, player=None, dt=1 / 60):
    t, events = 0.0, []
    while t < seconds and not game.winner:
        if player: player(game)
        e = game.update(dt)
        if e: events.append(e)
        r = game.BALL / 2
        assert r - 1e-6 <= game.by <= game.H - r + 1e-6, f"ball left the field vertically: {game.by}"
        assert all(math.isfinite(v) for v in (game.bx, game.by, game.vx, game.vy, game.py, game.ay))
        t += dt
    return events, t

# an idle player loses, and the computer's win is detected
p = PongGame(random.Random(1)); ev, t = run(p, 900)
assert p.winner == "ai" and p.ai_score == 7 and p.player_score == 0 and ev[-1] == "lose", (p.winner, p.player_score, p.ai_score)

# a player who tracks the ball can beat the computer (so the game is winnable)
def tracker(g): g.set_input(1 if g.by > g.py + 6 else -1 if g.by < g.py - 6 else 0)
wins = 0
for seed in range(10):
    p = PongGame(random.Random(seed)); run(p, 900, tracker); wins += p.winner == "player"
print("tracking player won", wins, "of 10 matches")
assert wins >= 5

# paddle hit reflects the ball and speeds it up
p = PongGame(random.Random(3)); p.freeze = 0
p.bx, p.by, p.vx, p.vy, p.py = 42, 200, -300.0, 0.0, 200.0
before = math.hypot(p.vx, p.vy)
assert p.update(0.016) == "hit" and p.vx > 0 and math.hypot(p.vx, p.vy) > before
# hitting with the paddle edge sends the ball at a steeper angle than the centre
p.bx, p.by, p.vx, p.vy, p.py = 42, 200 + 36, -300.0, 0.0, 200.0; p.update(0.016); steep = abs(p.vy)
p.bx, p.by, p.vx, p.vy, p.py = 42, 200, -300.0, 0.0, 200.0; p.update(0.016); assert steep > abs(p.vy)
# serve freeze: ball doesn't move straight after a point
p = PongGame(random.Random(4)); x0 = p.bx; p.update(0.016); assert p.bx == x0 and p.freeze < 0.9
# huge dt (window dragged, laptop slept) can't teleport the ball through a paddle
p = PongGame(random.Random(5)); p.freeze = 0; p.bx, p.by, p.vx, p.vy, p.py = 120, 200, -680.0, 0.0, 200.0
assert p.update(5.0) in ("hit", None) and p.bx > 0
# mouse control clamps to the field
p.set_player_y(-50); assert p.py == p.PAD_H / 2
p.set_player_y(9999); assert p.py == p.H - p.PAD_H / 2
p.reset(); assert p.player_score == p.ai_score == 0 and p.winner is None
print("GAMES TESTS PASSED")
