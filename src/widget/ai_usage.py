# -*- coding: utf-8 -*-
"""업무위젯 제목 줄의 AI 사용량 링 (Claude · agy) + Claude 승인 대기 점.

이 PC 에 Claude Code(~/.claude/.credentials.json) 나 agy 가 있을 때만 ⚙ 메뉴에 «AI 사용량» 이 보이고, 처음엔 꺼져 있다.
- Claude: 이 PC 의 Claude 로그인 토큰으로 Anthropic 사용량 주소(공식 문서에 없는 주소)를 3분마다 읽는다. 토큰은 Anthropic 말고 어디로도 보내지 않는다.
- agy: 5분마다 `agy -p /usage --output-format json` (슬래시 명령이라 모델을 부르지 않음). 모델을 부른 흔적이 보이면 자동 조회를 멈춘다.
- Codex: 이 PC 의 Codex 로그인(~/.codex/auth.json)으로 ChatGPT 사용량 주소(공식 문서에 없는 주소)를 5분마다 읽는다. 토큰은 OpenAI 말고 어디로도 보내지 않는다.
- 승인 대기: Claude Code 훅이 ~/.claude/widget_claude_state.json 에 적는 상태를 1초마다 읽는다 (훅 설정은 이 위젯이 하지 않는다).
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()
CLAUDE_CRED = HOME / ".claude" / ".credentials.json"
CLAUDE_STATE = HOME / ".claude" / "widget_claude_state.json"
CLAUDE_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_EVERY, CLAUDE_BACKOFF = 180, 600        # 초 (429 를 받으면 10분 쉰다)
AGY_EVERY = 300
CODEX_AUTH = HOME / ".codex" / "auth.json"
CODEX_URL = "https://chatgpt.com/backend-api/wham/usage"
CODEX_EVERY = 300
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
AGY_GROUPS = {"Gemini Models": "Gemini", "Claude and GPT models": "Claude·GPT"}
WORK_STALE, WAIT_STALE = 20 * 60, 2 * 60 * 60  # 훅 소식이 이만큼 없으면 그 상태는 끝난 것으로 본다

PROVIDERS = (("claude", "Claude"), ("codex", "Codex"), ("agy", "agy"))
BADGE = {"codex": "X", "agy": "A"}                # 작은 링 가운데 글자


# ── 조회 ──
def find_agy():
    p = shutil.which("agy")
    if p:
        return p
    c = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
    return str(c) if c.exists() else None


def available():
    """이 PC 에서 볼 수 있는 것 — {"claude": bool, "codex": bool, "agy": bool}"""
    return {"claude": CLAUDE_CRED.exists(), "codex": CODEX_AUTH.exists(), "agy": bool(find_agy())}


def _iso(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return None if d.year < 2000 else d          # agy 는 안 쓴 칸에 1970-01-01 을 준다
    except ValueError:
        return None


def remain_text(reset):
    """리셋까지 남은 시간 — «1:20» / «2일» / 지났거나 모르면 «»"""
    if reset is None:
        return ""
    s = (reset - datetime.now(timezone.utc)).total_seconds()
    if s <= 0:
        return ""
    if s >= 86400:
        return "%d일" % round(s / 86400)
    m = int(s // 60)
    return "%d:%02d" % (m // 60, m % 60)


def fetch_claude():
    try:
        tok = (json.loads(CLAUDE_CRED.read_text(encoding="utf-8")).get("claudeAiOauth") or {}).get("accessToken")
    except Exception:
        tok = None
    if not tok:
        return {"ok": False, "reason": "Claude 로그인 정보 없음"}
    req = urllib.request.Request(CLAUDE_URL, headers={"Authorization": "Bearer " + tok, "anthropic-beta": "oauth-2025-04-20",
                                                      "User-Agent": "work-widget/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"ok": False, "reason": "조회가 잠시 막힘 (10분 뒤 다시)", "backoff": True}
        if e.code in (401, 403):
            return {"ok": False, "reason": "로그인 만료 — Claude 를 한 번 켜 주세요"}
        return {"ok": False, "reason": "조회 실패 (HTTP %d)" % e.code}
    except Exception as e:
        return {"ok": False, "reason": "조회 실패 (%s)" % type(e).__name__}
    five, week = d.get("five_hour") or {}, d.get("seven_day") or {}
    return {"ok": True, "pct": round(float(five.get("utilization") or 0)), "reset": _iso(five.get("resets_at")),
            "week": round(float(week.get("utilization") or 0)), "week_reset": _iso(week.get("resets_at"))}


_agy_stopped = None


def fetch_agy():
    global _agy_stopped
    if _agy_stopped:
        return {"ok": False, "reason": _agy_stopped}
    exe = find_agy()
    if not exe:
        return {"ok": False, "reason": "agy 없음"}
    try:
        p = subprocess.run([exe, "-p", "/usage", "--output-format", "json"], capture_output=True, timeout=60,
                           cwd=tempfile.gettempdir(), creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "agy 응답 없음"}
    except OSError as e:
        return {"ok": False, "reason": "agy 실행 실패 (%s)" % type(e).__name__}
    t = p.stdout.decode("utf-8", "ignore")
    try:
        d = json.loads(t[t.index("{"):])
    except ValueError:
        return {"ok": False, "reason": "agy 로그인이 필요할 수 있어요"}
    if d.get("num_turns") or (d.get("usage") or {}).get("total_tokens"):      # 사용량 조회가 아니라 모델이 불렸다 — 할당량을 쓰므로 멈춘다
        _agy_stopped = "자동 조회 멈춤 (모델 호출 감지)"
        return {"ok": False, "reason": _agy_stopped}
    groups = []
    for g in ((d.get("command") or {}).get("data") or {}).get("groups") or []:
        b = {}
        for x in g.get("buckets") or []:
            if x.get("remaining_fraction") is None:
                continue
            b[x.get("window")] = (max(0, min(100, round((1 - float(x["remaining_fraction"])) * 100))), _iso(x.get("reset_time")))
        if b:
            groups.append({"name": AGY_GROUPS.get(g.get("name"), g.get("name") or "-"),
                           "b": {nm: b[w] for w, nm in (("5h", "5시간"), ("daily", "일간"), ("weekly", "주간")) if w in b}})
    if not groups:
        return {"ok": False, "reason": "agy 사용량 정보 없음"}
    top = max(groups, key=lambda g: (g["b"].get("5시간") or (0, None))[0])      # 링에는 5시간 사용량이 가장 많은 묶음
    pct, reset = top["b"].get("5시간") or (0, None)
    return {"ok": True, "pct": pct, "reset": reset, "groups": groups}


def _win_name(sec):
    sec = int(sec or 0)
    if 17000 <= sec <= 19000:
        return "5시간"
    if 600000 <= sec <= 610000:
        return "주간"
    if sec >= 86400:
        return "%d일" % round(sec / 86400)
    return "%d시간" % max(1, round(sec / 3600))


def fetch_codex():
    try:
        tok = json.loads(CODEX_AUTH.read_text(encoding="utf-8")).get("tokens") or {}
    except Exception:
        tok = {}
    if not tok.get("access_token"):
        return {"ok": False, "reason": "Codex 로그인 정보 없음"}
    req = urllib.request.Request(CODEX_URL, headers={"Authorization": "Bearer " + tok["access_token"],
                                                     "ChatGPT-Account-Id": tok.get("account_id") or "",
                                                     "User-Agent": "work-widget/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"ok": False, "reason": "조회가 잠시 막힘 (10분 뒤 다시)", "backoff": True}
        if e.code in (401, 403):
            return {"ok": False, "reason": "로그인 만료 — Codex 를 한 번 켜 주세요"}
        return {"ok": False, "reason": "조회 실패 (HTTP %d)" % e.code}
    except Exception as e:
        return {"ok": False, "reason": "조회 실패 (%s)" % type(e).__name__}
    rl = d.get("rate_limit") or {}
    b = {}
    for key in ("primary_window", "secondary_window"):
        w = rl.get(key)
        if isinstance(w, dict) and w.get("used_percent") is not None:
            at = w.get("reset_at")
            reset = datetime.fromtimestamp(int(at), timezone.utc) if at else None
            b[_win_name(w.get("limit_window_seconds"))] = (max(0, min(100, round(float(w["used_percent"])))), reset)
    if not b:
        return {"ok": False, "reason": "Codex 사용량 정보 없음"}
    pct, reset = next(iter(b.values()))                       # 링에는 짧은 쪽(첫째) 한도
    plan = {"free": "무료", "plus": "Plus", "pro": "Pro", "team": "Team", "business": "Business"}.get(d.get("plan_type"), d.get("plan_type") or "")
    return {"ok": True, "pct": pct, "reset": reset, "groups": [{"name": plan, "b": b}], "limit": bool(rl.get("limit_reached"))}


def claude_state():
    """Claude Code 상태 — "wait"(승인·답 기다림) / "work"(작업 중) / "idle". 여러 창이면 기다림 > 작업 > 쉼."""
    try:
        d = json.loads(CLAUDE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return "idle"
    now, best = time.time(), "idle"
    for v in (d.get("sessions") or {}).values():
        if not isinstance(v, dict):
            continue
        s, age = v.get("state"), now - float(v.get("ts") or 0)
        if s == "wait" and age < WAIT_STALE:
            return "wait"
        if s == "work" and age < WORK_STALE:
            best = "work"
    return best


ETA_SPAN = 40 * 60      # 속도는 최근 40분 안의 측정값으로 잰다
ETA_MIN_DT = 5 * 60     # 5분 넘게 떨어진 두 값이 있어야 잰다


def _same_reset(a, b):
    if a is None or b is None:
        return a is b
    return abs((a - b).total_seconds()) < 120


def eta_of(hist, pct, reset):
    """지금 속도로 100% 에 닿는 시각 (datetime) — 잴 수 없거나 줄고 있으면 None"""
    now = time.time()
    old = [h for h in hist if now - h[0] <= ETA_SPAN and _same_reset(h[2], reset)]
    if not old:
        return None
    t0, p0, _ = old[0]
    dt, dp = now - t0, pct - p0
    if dt < ETA_MIN_DT or dp <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=(100 - pct) * dt / dp)


def runs_out_first(v):
    """초기화보다 먼저 바닥나면 바닥 시각, 아니면 None"""
    e, r = v.get("eta"), v.get("reset")
    if e is None:
        return None
    return e if (r is None or e < r) else None


class Poller:
    """뒤에서 사용량을 읽어 self.data 에 둔다 (위젯 화면은 tk 쪽에서 1초마다 가져다 그린다)."""

    def __init__(self):
        self.data = {}
        self.hist = {}            # 이름 → [(읽은 때, %, 초기화 시각)] (바닥 예상 시각용)
        self.want = set()
        self.lock = threading.Lock()
        self.wake = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def set_want(self, names):
        new = set(names) - self.want
        self.want = set(names)
        if new:
            self.wake.set()

    def refresh(self):
        with self.lock:
            for v in self.data.values():
                v["_next"] = 0
        self.wake.set()

    def _run(self):
        nxt = {}
        while True:
            for name, fn, every in (("claude", fetch_claude, CLAUDE_EVERY), ("codex", fetch_codex, CODEX_EVERY), ("agy", fetch_agy, AGY_EVERY)):
                with self.lock:
                    forced = (self.data.get(name) or {}).get("_next") == 0
                if name not in self.want or (time.time() < nxt.get(name, 0) and not forced):
                    continue
                try:
                    res = fn()
                except Exception as e:
                    res = {"ok": False, "reason": "조회 오류 (%s)" % type(e).__name__}
                res["at"] = time.time()
                with self.lock:
                    old = self.data.get(name) or {}
                    if not res["ok"] and old.get("ok"):                   # 실패하면 마지막 값을 두고 이유만 붙인다
                        res = dict(old, note=res["reason"], at=old.get("at"), backoff=res.get("backoff"))
                    if res["ok"] and not res.get("note"):
                        h = [x for x in self.hist.get(name, []) if res["at"] - x[0] <= ETA_SPAN]
                        res["eta"] = eta_of(h, res["pct"], res.get("reset"))
                        h.append((res["at"], res["pct"], res.get("reset")))
                        self.hist[name] = h
                    self.data[name] = res
                nxt[name] = time.time() + (CLAUDE_BACKOFF if res.get("backoff") else every)
            self.wake.wait(15)
            self.wake.clear()


# ── 그리기 ──
STATE_RING = {"work": ("#f08c00", "#fbe2c2"),     # Claude 작업 중: 주황 링 (진한 색, 바탕 링 옅은 색)
              "wait": ("#1f6fd6", "#cfe0f8")}     # 승인 기다림: 파랑 링


def ring_colors(n, p, state):
    """(채운 부분 색, 바탕 링 색) — Claude 는 작업 중·승인 대기면 상태 색, 쉬는 중이면 사용량 색"""
    if n == "claude" and state in STATE_RING:
        return STATE_RING[state]
    return ring_color(p), "#e2ded4"


def week_color(p):
    """안쪽(주간) 링 색 — 작업 중 주황·승인 대기 파랑과 헷갈리지 않게 보라, 90% 넘으면 빨강"""
    return "#c82014" if p >= 90 else "#7b5cc4"


def ring_color(p):
    return "#c82014" if p >= 90 else "#d6336c" if p >= 70 else "#00754A"     # 70%+ 분홍 (작업 중 주황과 구분)


WAIT_ALERT = 60     # 승인 대기가 이만큼(초) 이어지면 한 번 알린다
BIG_H = 40          # 위쪽 줄(크게) 모드의 줄 높이 (px 배율 전)


def focus_claude():
    """Claude 데스크톱 앱 창을 앞으로 — 찾으면 True"""
    try:
        import ctypes
        from ctypes import wintypes as W
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        found = []

        def exe_of(h):
            pid = W.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(pid))
            hp = k.OpenProcess(0x1000, False, pid.value)            # PROCESS_QUERY_LIMITED_INFORMATION
            if not hp:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(520)
                n = W.DWORD(520)
                return buf.value if k.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n)) else ""
            finally:
                k.CloseHandle(hp)

        @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        def cb(h, _):
            if u.IsWindowVisible(h) and u.GetWindowTextLengthW(h) and not u.GetWindow(h, 4):   # GW_OWNER 없는 큰 창
                if os.path.basename(exe_of(h)).lower() == "claude.exe":
                    found.append(h)
                    return False
            return True

        u.EnumWindows(cb, 0)
        if not found:
            return False
        h = found[0]
        if u.IsIconic(h):
            u.ShowWindow(h, 9)                                      # SW_RESTORE
        u.SetForegroundWindow(h)
        return True
    except Exception:
        return False


def week_pct(n, v):
    """안쪽 링에 쓸 주간 사용량 % — 없으면 None (Codex 무료처럼 창이 하나뿐일 때)"""
    if n == "claude":
        return v.get("week")
    gs = v.get("groups") or []
    if not gs:
        return None
    g = max(gs, key=lambda g: (g["b"].get("5시간") or (0,))[0])     # 큰 링과 같은 묶음
    wk = g["b"].get("주간")
    return wk[0] if wk else None


class AiBar(tk.Frame):
    """AI 사용량 링들. big=False: 제목 줄에 붙는 작은 링 / big=True: 위젯 위쪽에 따로 한 줄, 큰 링 + 이름·남은 시간.
    px: 크기 배율 함수, font: (크기, 굵게) → 글꼴."""

    def __init__(self, master, bg, px, font, h, big=False):
        super().__init__(master, bg=bg)
        self.bg, self.px, self.font = bg, px, font
        self.small_h = max(h, px(18))
        self.big = big
        self.h = px(BIG_H) if big else self.small_h
        self.poller = Poller()
        self.show = []
        self.wait_on = True
        self.items = {}
        self.tip = None
        self.tip_name = None
        self.blink = False
        self.state = "idle"
        self.notify = None          # (제목, 내용) → 윈도우 알림. 위젯이 넣어 준다
        self.wait_since = None
        self.wait_told = False
        self.next_name = None
        self.after(300, self._loop)

    def set_big(self, big):
        if big != self.big:
            self.big = big
            self.h = self.px(BIG_H) if big else self.small_h
            self.configure_show(self.show, self.wait_on)

    def configure_show(self, names, wait_on):
        self.show = [n for n, _ in PROVIDERS if n in names]
        self.wait_on = wait_on
        self.poller.set_want(self.show)
        for w in self.winfo_children():
            w.destroy()
        self.items = {}
        px = self.px
        for n in self.show:
            if self.big:
                d = px(38) if n == "claude" else px(34)
                w = d + px(86)
                pad = (px(4), px(4))
            else:
                d = self.h if n == "claude" else self.h - px(4)
                w = d + (px(30) if n == "claude" else 0)
                pad = (px(3), 0)
            c = tk.Canvas(self, width=w, height=self.h, bg=self.bg, highlightthickness=0, cursor="hand2")
            c.pack(side="left", padx=pad)
            c.bind("<Enter>", lambda e, k=n: self._tip(k))
            c.bind("<Leave>", lambda e: self._untip())
            c.bind("<Button-1>", lambda e, k=n: self._click(k))
            self.items[n] = (c, d)
        self.draw()

    def _click(self, n):
        if n == "claude" and self.state == "wait" and focus_claude():
            return
        self.poller.refresh()

    def _loop(self):
        self.after(1000, self._loop)
        self.state = claude_state() if ("claude" in self.show and self.wait_on) else "idle"
        if self.state == "wait":
            if self.wait_since is None:
                self.wait_since = time.time()
            elif not self.wait_told and time.time() - self.wait_since >= WAIT_ALERT:
                self.wait_told = True
                if self.notify:
                    try:
                        self.notify("Claude 가 승인을 기다려요", "1분 넘게 기다리는 중이에요. 업무위젯의 Claude 링을 누르면 Claude 창이 앞으로 와요.")
                    except Exception:
                        pass
        else:
            self.wait_since, self.wait_told = None, False
        self.blink = not self.blink
        if self.winfo_ismapped():                  # 트레이·접힘 동안은 그리지 않는다
            self.draw()
        if self.tip_name:
            self._tip(self.tip_name, move=False)

    def draw(self):
        px = self.px
        with self.poller.lock:
            data = {k: dict(v) for k, v in self.poller.data.items()}
        if self.big:
            return self._draw_big(data)
        for n, (c, d) in self.items.items():
            c.delete("all")
            v = data.get(n) or {}
            ok = v.get("ok")
            p = v.get("pct", 0) if ok else 0
            y0 = (self.h - d) // 2
            box = (px(2), y0 + px(2), d - px(2), y0 + d - px(2))
            w = max(2, px(3))
            fg, track = ring_colors(n, p, self.state)
            c.create_oval(*box, outline=track, width=w)
            if ok and p > 0:
                c.create_arc(*box, start=90, extent=-max(1, min(359.9, p * 3.6)), style="arc", outline=fg, width=w)
            label = str(p) if ok else "–"
            if n != "claude":
                label = BADGE.get(n, "?")
            c.create_text(d / 2, y0 + d / 2, text=label, fill="#2b2b2b" if ok else "#a8a49b", font=self.font(6, n == "claude"))
            if n == "claude":
                c.create_text(d + px(3), self.h // 2, text=remain_text(v.get("reset")) if ok else "", anchor="w", fill="#6b6b6b", font=self.font(7))

    def pick_next(self, data):
        cl = data.get("claude") or {}
        if not cl.get("ok") or not (cl.get("pct", 0) >= 90 or cl.get("limit") or runs_out_first(cl) is not None):
            return None
        cand = [(v.get("pct", 100), n) for n, v in data.items()
                if n != "claude" and n in self.show and v.get("ok") and not v.get("limit") and v.get("pct", 100) < 90]
        return min(cand)[1] if cand else None

    def _draw_big(self, data):
        px = self.px
        self.next_name = self.pick_next(data)
        for n, (c, d) in self.items.items():
            c.delete("all")
            v = data.get(n) or {}
            ok = v.get("ok")
            p = v.get("pct", 0) if ok else 0
            y0 = (self.h - d) // 2
            w = max(3, px(4) if n == "claude" else px(3.5))
            m = w // 2 + 1
            box = (m, y0 + m, d - m, y0 + d - m)
            fg, track = ring_colors(n, p, self.state)
            c.create_oval(*box, outline=track, width=w)
            if ok and p > 0:
                c.create_arc(*box, start=90, extent=-max(1, min(359.9, p * 3.6)), style="arc", outline=fg, width=w)
            wp = week_pct(n, v) if ok else None
            if wp is not None:                                   # 안쪽 작은 링 = 주간 사용량
                w2 = max(2, px(2.5))
                m2 = m + w // 2 + px(1.5) + w2 // 2 + 1
                box2 = (m2, y0 + m2, d - m2, y0 + d - m2)
                c.create_oval(*box2, outline="#e8e4db", width=w2)
                if wp > 0:
                    c.create_arc(*box2, start=90, extent=-max(1, min(359.9, wp * 3.6)), style="arc", outline=week_color(wp), width=w2)
            c.create_text(d / 2, y0 + d / 2, text=str(p) if ok else "–", fill="#2b2b2b" if ok else "#a8a49b",
                          font=self.font(8, True))
            sub_fg = "#6b6b6b"
            if ok:
                r = remain_text(v.get("reset"))
                sub = "한도 다 씀" if v.get("limit") else ("%s 후 초기화" % r if r else "")
                eta = runs_out_first(v)
                if eta is not None and not v.get("limit"):
                    sub, sub_fg = "%s 뒤 바닥" % (remain_text(eta) or "곧"), "#c82014"
                if v.get("note"):
                    sub = "⚠ " + (sub or "다시 읽는 중")
            else:
                sub = "조회 안 됨" if v else "읽는 중…"
            tx = d + px(6)
            t = c.create_text(tx, self.h / 2 - px(7), text=dict(PROVIDERS)[n], anchor="w", fill="#4a4a4a", font=self.font(8, True))
            if n == self.next_name:
                x1 = c.bbox(t)[2]
                c.create_text(x1 + px(4), self.h / 2 - px(7), text="▶ 다음", anchor="w", fill="#00754A", font=self.font(8, True))
            c.create_text(tx, self.h / 2 + px(7), text=sub, anchor="w", fill=sub_fg, font=self.font(8))

    def tip_text(self, n):
        with self.poller.lock:
            v = dict(self.poller.data.get(n) or {})
        if not v:
            return "%s\n불러오는 중…" % dict(PROVIDERS)[n]
        if not v.get("ok"):
            return "%s\n%s" % (dict(PROVIDERS)[n], v.get("reason", "조회 실패"))
        lines = []
        if n == "claude":
            st = {"wait": "  · 승인 기다리는 중", "work": "  · 작업 중"}.get(self.state, "")
            lines.append("Claude" + st)
            r = remain_text(v.get("reset"))
            lines.append("5시간 %d%%%s" % (v["pct"], " · %s 후 초기화" % r if r else ""))
            r = remain_text(v.get("week_reset"))
            lines.append("주간 %d%%%s" % (v["week"], " · %s 후 초기화" % r if r else ""))
        else:
            lines.append(dict(PROVIDERS)[n] + ("  · 한도 다 씀" if v.get("limit") else ""))
            for g in v.get("groups") or []:
                parts = []
                for nm, (pc, rs) in g["b"].items():
                    r = remain_text(rs)
                    parts.append("%s %d%%%s" % (nm, pc, " (%s 후 초기화)" % r if r else ""))
                lines.append(("%s  " % g["name"] if g["name"] else "") + " · ".join(parts))
        eta = runs_out_first(v)
        if eta is not None:
            lines.append("이 속도면 %s 뒤 바닥 (초기화보다 먼저)" % (remain_text(eta) or "곧"))
        elif v.get("eta") is not None:
            lines.append("이 속도면 초기화까지 넉넉해요")
        if n == self.next_name:
            lines.append("▶ Claude 가 거의 다 차서 다음으로 쓰기 좋아요")
        if v.get("note"):
            lines.append("⚠ " + v["note"])
        if v.get("at"):
            act = "누르면 Claude 창 열기" if (n == "claude" and self.state == "wait") else "누르면 새로 읽기"
            lines.append("%s에 읽음 · %s" % (datetime.fromtimestamp(v["at"]).strftime("%H:%M"), act))
        return "\n".join(lines)

    def _tip(self, n, move=True):
        if n not in self.items:
            return self._untip()
        text = self.tip_text(n)
        if self.tip is None:
            self.tip = tk.Toplevel(self)
            self.tip.overrideredirect(True)
            self.tip.attributes("-topmost", True)
            self.tip_lb = tk.Label(self.tip, bg="#2b2b2b", fg="#ffffff", font=self.font(8), justify="left",
                                   padx=self.px(8), pady=self.px(5))
            self.tip_lb.pack()
        self.tip_lb.configure(text=text)
        self.tip_name = n
        if move:
            c = self.items[n][0]
            self.tip.update_idletasks()
            x = c.winfo_rootx() + c.winfo_width() // 2 - self.tip.winfo_reqwidth() // 2
            x = max(0, min(x, self.winfo_screenwidth() - self.tip.winfo_reqwidth()))
            y = c.winfo_rooty() + c.winfo_height() + self.px(4)
            if y + self.tip.winfo_reqheight() > self.winfo_screenheight():
                y = c.winfo_rooty() - self.tip.winfo_reqheight() - self.px(4)
            self.tip.geometry("+%d+%d" % (x, y))

    def _untip(self):
        self.tip_name = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None
