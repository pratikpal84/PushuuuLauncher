#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tiny arcade games for the launcher's "waiting room".

Pure game logic - no tkinter - so it can be tested without a display.
The drawing and keyboard handling live in pushuuu_arcade.py.
"""
from __future__ import annotations

import math
import random
from collections import deque

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# --------------------------------------------------------------------------- #
# Snake
# --------------------------------------------------------------------------- #
class SnakeGame:
    """Classic snake on a grid. Call step() every tick_ms milliseconds."""

    def __init__(self, cols: int = 32, rows: int = 20, rng: random.Random | None = None):
        self.cols, self.rows = cols, rows
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        cx, cy = self.cols // 2, self.rows // 2
        self.snake: deque[tuple[int, int]] = deque([(cx, cy), (cx - 1, cy), (cx - 2, cy)])  # head first
        self.dir = (1, 0)
        self.queue: deque[tuple[int, int]] = deque()   # buffered turns, so quick key taps aren't lost
        self.score = 0
        self.alive = True
        self.won = False
        self.food: tuple[int, int] | None = None
        self._place_food()

    def turn(self, name: str) -> None:
        d = DIRS[name]
        last = self.queue[-1] if self.queue else self.dir
        if d == last or (d[0] == -last[0] and d[1] == -last[1]):
            return  # same direction, or a 180-degree turn into yourself
        if len(self.queue) < 2:
            self.queue.append(d)

    def _place_food(self) -> None:
        taken = set(self.snake)
        free = [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in taken]
        if not free:                       # the board is full: perfect game
            self.food, self.won, self.alive = None, True, False
            return
        self.food = self.rng.choice(free)

    def step(self) -> str:
        """Advance one tick. Returns 'move', 'eat', 'dead' or 'idle'."""
        if not self.alive:
            return "idle"
        if self.queue:
            self.dir = self.queue.popleft()
        nx, ny = self.snake[0][0] + self.dir[0], self.snake[0][1] + self.dir[1]
        eating = (nx, ny) == self.food
        body = list(self.snake) if eating else list(self.snake)[:-1]   # the tail moves out of the way
        if not (0 <= nx < self.cols and 0 <= ny < self.rows) or (nx, ny) in body:
            self.alive = False
            return "dead"
        self.snake.appendleft((nx, ny))
        if eating:
            self.score += 10
            self._place_food()
            return "eat"
        self.snake.pop()
        return "move"

    @property
    def tick_ms(self) -> int:
        """Gets faster as the snake grows, down to a floor."""
        return max(55, 140 - (len(self.snake) - 3) * 3)


# --------------------------------------------------------------------------- #
# Pong
# --------------------------------------------------------------------------- #
class PongGame:
    """Player (left) vs computer (right) on a 640x400 virtual field. First to WIN_SCORE wins."""

    W, H = 640, 400
    PAD_W, PAD_H, BALL = 12, 76, 12
    MARGIN = 22
    PLAYER_SPEED, AI_SPEED = 430.0, 290.0       # the computer is deliberately slower than you
    START_SPEED, MAX_SPEED = 300.0, 680.0
    WIN_SCORE = 7
    MAX_DT = 0.03                               # small steps keep a fast ball from tunnelling through a paddle

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.player_score = self.ai_score = 0
        self.winner: str | None = None
        self.py = self.ay = self.H / 2
        self.input = 0
        self.freeze = 0.0
        self._serve(self.rng.choice((-1, 1)))

    def _serve(self, toward: int) -> None:
        self.bx, self.by = self.W / 2, self.H / 2
        angle = self.rng.uniform(-0.45, 0.45)
        self.vx = self.START_SPEED * math.cos(angle) * toward
        self.vy = self.START_SPEED * math.sin(angle)
        self.freeze = 0.9                       # short pause so you can see the ball before it moves

    def set_input(self, direction: int) -> None:
        self.input = int(_clamp(direction, -1, 1))

    def set_player_y(self, y: float) -> None:
        half = self.PAD_H / 2
        self.py = _clamp(y, half, self.H - half)

    def _bounce(self, paddle_y: float, direction: int, new_x: float) -> None:
        rel = _clamp((self.by - paddle_y) / (self.PAD_H / 2 + self.BALL / 2), -1.0, 1.0)
        speed = min(self.MAX_SPEED, math.hypot(self.vx, self.vy) * 1.07)
        angle = rel * math.radians(55)
        self.vx = direction * speed * math.cos(angle)
        self.vy = speed * math.sin(angle)
        self.bx = new_x

    def update(self, dt: float) -> str | None:
        """Advance by dt seconds. Returns 'hit', 'score', 'win', 'lose' or None."""
        if self.winner:
            return None
        dt = _clamp(dt, 0.0, self.MAX_DT)
        half, r = self.PAD_H / 2, self.BALL / 2

        self.py = _clamp(self.py + self.input * self.PLAYER_SPEED * dt, half, self.H - half)
        target = self.by if self.vx > 0 else self.H / 2      # computer only chases when the ball comes its way
        diff = target - self.ay
        if abs(diff) > 8:
            step = self.AI_SPEED * dt
            self.ay += _clamp(diff, -step, step)
        self.ay = _clamp(self.ay, half, self.H - half)

        if self.freeze > 0:
            self.freeze -= dt
            return None

        self.bx += self.vx * dt
        self.by += self.vy * dt
        if self.by < r:
            self.by, self.vy = r, abs(self.vy)
        elif self.by > self.H - r:
            self.by, self.vy = self.H - r, -abs(self.vy)

        p_right = self.MARGIN + self.PAD_W
        if (self.vx < 0 and self.bx - r <= p_right and self.bx + r >= self.MARGIN
                and abs(self.by - self.py) <= half + r):
            self._bounce(self.py, +1, p_right + r)
            return "hit"
        a_left = self.W - self.MARGIN - self.PAD_W
        if (self.vx > 0 and self.bx + r >= a_left and self.bx - r <= self.W - self.MARGIN
                and abs(self.by - self.ay) <= half + r):
            self._bounce(self.ay, -1, a_left - r)
            return "hit"

        if self.bx < -2 * r:
            self.ai_score += 1
            return self._after_point(toward=-1)
        if self.bx > self.W + 2 * r:
            self.player_score += 1
            return self._after_point(toward=+1)
        return None

    def _after_point(self, toward: int) -> str:
        if self.player_score >= self.WIN_SCORE:
            self.winner = "player"
            return "win"
        if self.ai_score >= self.WIN_SCORE:
            self.winner = "ai"
            return "lose"
        self._serve(toward)                     # the serve goes toward whoever just lost the point
        return "score"
