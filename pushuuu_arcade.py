#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pushuuu Launcher - Arcade tab: Snake and Pong to play while downloads run.

Game rules live in pushuuu_games.py; this file draws them and handles input.
The game pauses by itself when you leave the tab or click elsewhere.
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from pushuuu_games import PongGame, SnakeGame
from pushuuu_ui import (ACCENT, ACCENT_DD, AMBER, BG0, BG1, BG2, CYAN, DANGER, FG, FONTS, LINE, MUTED, VIOLET,
                        mix, px, round_rect)

KEYMAP = {"up": "up", "w": "up", "down": "down", "s": "down",
          "left": "left", "a": "left", "right": "right", "d": "right"}
HINTS = {"snake": "Arrow keys or WASD to steer  ·  SPACE pause  ·  R restart  ·  eat the red blocks, don't hit yourself",
         "pong": "W/S, arrow keys or the mouse to move  ·  SPACE pause  ·  first to 7 wins"}


class ArcadePage(tk.Frame):
    COLS, ROWS = 32, 20          # 32 x 20 cells of 20px = the same 640x400 field Pong uses

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG0)
        self.app = app
        self.mode = tk.StringVar(value="snake")
        self.state = "ready"                     # ready | playing | paused | over
        self.snake, self.pong = SnakeGame(self.COLS, self.ROWS), PongGame()
        self.keys: set = set()
        self.job = None
        self._last = 0.0
        self.cw, self.ch = px(640), px(400)
        self.k = self.cw / 640.0
        self.columnconfigure(0, weight=1)

        head = tk.Frame(self, bg=BG0)
        head.grid(row=0, column=0, sticky="ew", padx=px(36), pady=(px(28), px(6)))
        head.columnconfigure(0, weight=1)
        tk.Label(head, text="ARCADE", bg=BG0, fg=FG, font=FONTS["h1"]).grid(row=0, column=0, sticky="w")
        tk.Label(head, text="Waiting on a download? Beat your high score.", bg=BG0, fg=MUTED,
                 font=FONTS["ui"]).grid(row=1, column=0, sticky="w")
        pills = tk.Frame(head, bg=BG0)
        pills.grid(row=0, column=1, rowspan=2, sticky="e")
        for value, text in (("snake", "Snake"), ("pong", "Pong")):
            ttk.Radiobutton(pills, text=text, value=value, variable=self.mode, style="Pill.Toolbutton",
                            command=self._switch).pack(side="left", padx=3)

        stats = tk.Frame(self, bg=BG0)
        stats.grid(row=1, column=0, sticky="ew", padx=px(36), pady=(px(10), 0))
        self.score_var, self.best_var, self.hint_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        tk.Label(stats, textvariable=self.score_var, bg=BG0, fg=ACCENT, font=FONTS["h2"]).pack(side="left")
        tk.Label(stats, textvariable=self.best_var, bg=BG0, fg=MUTED, font=FONTS["ui_b"]).pack(side="left",
                                                                                              padx=px(26))

        self.canvas = tk.Canvas(self, width=self.cw, height=self.ch, bg=BG1, highlightthickness=1,
                                highlightbackground=LINE, highlightcolor=ACCENT, takefocus=True)
        self.canvas.grid(row=2, column=0, sticky="w", padx=px(36), pady=px(12))
        tk.Label(self, textvariable=self.hint_var, bg=BG0, fg=MUTED, font=FONTS["small"]
                 ).grid(row=3, column=0, sticky="w", padx=px(36))

        c = self.canvas
        c.bind("<KeyPress>", self._key_down)
        c.bind("<KeyRelease>", self._key_up)
        c.bind("<Button-1>", self._click)
        c.bind("<Motion>", self._motion)
        c.bind("<FocusOut>", lambda e: self._pause_if_playing())
        self.hint_var.set(HINTS["snake"])
        self._render()

    # ---- lifecycle ------------------------------------------------------------- #
    def on_show(self):
        self.canvas.focus_set()
        self._render()

    def on_hide(self):
        self._pause_if_playing()

    def _cancel(self):
        if self.job is not None:
            self.after_cancel(self.job)
            self.job = None

    def _set_state(self, state: str):
        self.state = state
        self._cancel()
        if state == "playing":
            self._last = time.perf_counter()
            self._schedule()
        self._render()

    def _pause_if_playing(self):
        if self.state == "playing":
            self._set_state("paused")

    def _current(self):
        return self.snake if self.mode.get() == "snake" else self.pong

    def _start(self):
        if self.state in ("ready", "over"):
            self._current().reset()
        self.keys.clear()
        self._set_state("playing")

    def _switch(self):
        self._cancel()
        self.state = "ready"
        self.keys.clear()
        self.snake.reset()
        self.pong.reset()
        self.hint_var.set(HINTS[self.mode.get()])
        self._render()
        self.canvas.focus_set()

    def _schedule(self):
        delay = self.snake.tick_ms if self.mode.get() == "snake" else 16
        self.job = self.after(delay, self._tick)

    def _tick(self):
        self.job = None
        if self.state != "playing":
            return
        if self.mode.get() == "snake":
            self.snake.step()
            if not self.snake.alive:
                return self._finish()
        else:
            now = time.perf_counter()
            dt, self._last = now - self._last, now
            self.pong.set_input(("down" in self.keys) - ("up" in self.keys))
            self.pong.update(dt)
            if self.pong.winner:
                return self._finish()
        self._render()
        self._schedule()

    def _finish(self):
        hs = self.app.cfg["highscores"]
        if self.mode.get() == "snake":
            hs["snake"] = max(hs.get("snake", 0), self.snake.score)
        elif self.pong.winner == "player":
            hs["pong"] = hs.get("pong", 0) + 1
        self.app.save_highscores()
        self._set_state("over")

    # ---- input ------------------------------------------------------------------- #
    def _key_down(self, e):
        key = e.keysym.lower()
        if key == "space":
            if self.state in ("ready", "over"):
                self._start()
            elif self.state == "playing":
                self._set_state("paused")
            else:
                self._set_state("playing")
            return
        if key == "escape":
            return self._pause_if_playing()
        if key == "r":
            self.state = "ready"
            return self._start()
        d = KEYMAP.get(key)
        if not d:
            return
        if self.state == "ready":
            self._start()                            # the first arrow press also starts the game
        if self.mode.get() == "snake":
            if self.state == "playing":
                self.snake.turn(d)
        elif d in ("up", "down"):
            self.keys.add(d)

    def _key_up(self, e):
        d = KEYMAP.get(e.keysym.lower())
        self.keys.discard(d)

    def _click(self, e):
        self.canvas.focus_set()
        if self.state in ("ready", "over"):
            self._start()
        elif self.state == "paused":
            self._set_state("playing")

    def _motion(self, e):
        if self.mode.get() == "pong" and self.state == "playing" and not self.keys:
            self.pong.set_player_y(e.y / self.k)

    # ---- drawing ------------------------------------------------------------------ #
    def _render(self):
        self.canvas.delete("all")
        if self.mode.get() == "snake":
            self._draw_snake()
        else:
            self._draw_pong()
        self._overlay()
        hs = self.app.cfg["highscores"]
        if self.mode.get() == "snake":
            self.score_var.set(f"SCORE  {self.snake.score}")
            self.best_var.set(f"BEST  {hs.get('snake', 0)}")
        else:
            self.score_var.set(f"YOU {self.pong.player_score}  -  {self.pong.ai_score} CPU")
            self.best_var.set(f"MATCHES WON  {hs.get('pong', 0)}")

    def _draw_snake(self):
        c, g = self.canvas, self.snake
        cell = self.cw / self.COLS
        grid = mix(BG1, LINE, 0.55)
        for x in range(1, self.COLS):
            c.create_line(x * cell, 0, x * cell, self.ch, fill=grid)
        for y in range(1, self.ROWS):
            c.create_line(0, y * cell, self.cw, y * cell, fill=grid)
        if g.food:
            cx, cy = (g.food[0] + 0.5) * cell, (g.food[1] + 0.5) * cell
            for rr, t in ((0.66, 0.14), (0.50, 0.30), (0.34, 1.0)):
                r = rr * cell
                c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=mix(BG1, DANGER, t), outline="")
        n, pad = len(g.snake), cell * 0.07
        for i in reversed(range(n)):                 # tail first, so the head is drawn on top
            x, y = g.snake[i]
            col = mix(ACCENT, ACCENT_DD, 0.75 * i / max(1, n - 1))
            if not g.alive:
                col = mix(col, DANGER, 0.55)
            round_rect(c, x * cell + pad, y * cell + pad, (x + 1) * cell - pad, (y + 1) * cell - pad,
                       cell * 0.28, fill=col, outline="")
        hx, hy = g.snake[0]
        dx, dy = g.dir
        cx, cy, f, s, e = (hx + 0.5) * cell, (hy + 0.5) * cell, cell * 0.2, cell * 0.2, cell * 0.09
        for sign in (1, -1):                         # two eyes, pushed toward the direction of travel
            ex, ey = cx + dx * f - dy * s * sign, cy + dy * f + dx * s * sign
            c.create_oval(ex - e, ey - e, ex + e, ey + e, fill=BG0, outline="")

    def _draw_pong(self):
        c, g, k = self.canvas, self.pong, self.k
        for y in range(0, g.H, 24):
            c.create_rectangle((g.W / 2 - 2) * k, y * k, (g.W / 2 + 2) * k, (y + 12) * k,
                               fill=mix(BG1, LINE, 0.9), outline="")
        c.create_text(g.W * 0.25 * k, 74 * k, text=str(g.player_score), font=FONTS["score"],
                      fill=mix(BG1, ACCENT, 0.3))
        c.create_text(g.W * 0.75 * k, 74 * k, text=str(g.ai_score), font=FONTS["score"],
                      fill=mix(BG1, VIOLET, 0.3))
        for x, y, col in ((g.MARGIN, g.py, ACCENT), (g.W - g.MARGIN - g.PAD_W, g.ay, VIOLET)):
            half = g.PAD_H / 2
            round_rect(c, (x - 4) * k, (y - half - 4) * k, (x + g.PAD_W + 4) * k, (y + half + 4) * k, 9 * k,
                       fill=mix(BG1, col, 0.18), outline="")
            round_rect(c, x * k, (y - half) * k, (x + g.PAD_W) * k, (y + half) * k, 5 * k, fill=col, outline="")
        r = g.BALL / 2
        for rr, fill in ((r * 2.3, mix(BG1, CYAN, 0.14)), (r * 1.6, mix(BG1, CYAN, 0.32)), (r, FG)):
            c.create_oval((g.bx - rr) * k, (g.by - rr) * k, (g.bx + rr) * k, (g.by + rr) * k, fill=fill, outline="")

    def _overlay(self):
        if self.state == "playing":
            return
        snake = self.mode.get() == "snake"
        colour = ACCENT
        if self.state == "ready":
            title, sub = ("SNAKE" if snake else "PONG"), "Press SPACE or click to start"
        elif self.state == "paused":
            title, sub = "PAUSED", "SPACE or click to resume"
        elif snake:
            title = "PERFECT!" if self.snake.won else "GAME OVER"
            sub = f"Score {self.snake.score}  ·  SPACE to play again"
            colour = AMBER if self.snake.won else DANGER
        else:
            win = self.pong.winner == "player"
            title = "YOU WIN!" if win else "YOU LOSE"
            sub = f"{self.pong.player_score} - {self.pong.ai_score}  ·  SPACE to play again"
            colour = ACCENT if win else DANGER
        cx, cy, bw, bh = self.cw / 2, self.ch / 2, px(400), px(124)
        round_rect(self.canvas, cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, px(16), fill=BG2, outline=colour)
        self.canvas.create_text(cx, cy - px(16), text=title, fill=colour, font=FONTS["overlay"])
        self.canvas.create_text(cx, cy + px(28), text=sub, fill=MUTED, font=FONTS["ui"])
