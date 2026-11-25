# -*- coding: utf-8 -*-
"""업무위젯 포스트잇 메모.

위젯 아래 «메모 줄»에 메모마다 칩이 있고, 칩을 누르면 노란 포스트잇 창이 열리고 다시 누르면 닫힌다 (펼침 칸처럼).
포스트잇 안은 메모장(여러 줄 글) 또는 체크리스트로 고를 수 있고, ⏰ 로 시각을 정하면 그때 윈도우 알림을 띄우고 창을 연다.
메모는 위젯 상태 파일(이 PC)에만 저장한다.
"""
import ctypes
import time
import tkinter as tk
import tkinter.font as tkfont
import uuid
from datetime import datetime, timedelta
from tkinter import messagebox

YEL = "#fff3c4"       # 포스트잇 바탕
YEL_D = "#f7e39a"     # 머리줄·열린 칩
EDGE = "#e2cd73"
INK = "#2b2b2b"
HINT = "#a39a73"
DONE = "#a8a49b"
ALARM_EVERY = 1000   # 알림 시각을 몇 ms 마다 볼지 (시각은 분 단위라 1초면 늦어도 1초)
CHIP_MAX = 4          # 메모 줄에 칩을 몇 개까지 (나머지는 «외 N개 ▾»)
FS_MIN, FS_MAX, FS_DEF = 8, 50, 10   # 메모 글씨 크기 (pt)
ALPHA_MIN = 0.3       # 이보다 더 투명하면 글을 읽을 수 없다

# 포스트잇 색: 바탕 · 머리줄(열린 칩) · 테두리 · 입력칸
PALETTE = {
    "yellow": {"name": "노랑", "bg": YEL, "head": YEL_D, "edge": EDGE, "field": "#fff8dc"},
    "pink": {"name": "분홍", "bg": "#ffd9e2", "head": "#f7b9c9", "edge": "#e39bb0", "field": "#ffeaf0"},
    "green": {"name": "연두", "bg": "#d8f2c8", "head": "#b9e2a2", "edge": "#92c97a", "field": "#ebf9e3"},
    "blue": {"name": "하늘", "bg": "#d3e8fb", "head": "#aed0f2", "edge": "#84b3e0", "field": "#e8f3fd"},
    "purple": {"name": "보라", "bg": "#e6dcf8", "head": "#cdbcf0", "edge": "#aa95dc", "field": "#f2ecfc"},
    "orange": {"name": "주황", "bg": "#ffe0bf", "head": "#fbc690", "edge": "#e5a45f", "field": "#fff0de"},
    "white": {"name": "흰색", "bg": "#ffffff", "head": "#ececec", "edge": "#cfcfcf", "field": "#f7f7f7"},
    "gray": {"name": "회색", "bg": "#e3e3e3", "head": "#c9c9c9", "edge": "#a8a8a8", "field": "#f0f0f0"},
}


def pal(m):
    return PALETTE.get(m.get("color")) or PALETTE["yellow"]


# ── 한글 입력기(IME) 조합 창 글씨 크기 ──
# Tk 는 «아직 입력 중인 글자»를 칸 안이 아니라 윈도우 입력기의 작은 창에 그린다. 그 창의 글씨를 칸의 글씨 크기에 맞춘다.
class _LOGFONTW(ctypes.Structure):
    _fields_ = [("lfHeight", ctypes.c_long), ("lfWidth", ctypes.c_long), ("lfEscapement", ctypes.c_long),
                ("lfOrientation", ctypes.c_long), ("lfWeight", ctypes.c_long), ("lfItalic", ctypes.c_ubyte),
                ("lfUnderline", ctypes.c_ubyte), ("lfStrikeOut", ctypes.c_ubyte), ("lfCharSet", ctypes.c_ubyte),
                ("lfOutPrecision", ctypes.c_ubyte), ("lfClipPrecision", ctypes.c_ubyte), ("lfQuality", ctypes.c_ubyte),
                ("lfPitchAndFamily", ctypes.c_ubyte), ("lfFaceName", ctypes.c_wchar * 32)]


def ime_font(w):
    """칸 w 의 글꼴·크기를 입력기 조합 창에 알린다. 성공하면 True (안 되는 PC에서는 조용히 넘어간다)"""
    try:
        f = tkfont.Font(root=w, font=w.cget("font")).actual()
        lf = _LOGFONTW()
        lf.lfHeight = -max(8, int(round(abs(int(f["size"])) * w.winfo_fpixels("1i") / 72.0))) if int(f["size"]) > 0 else int(f["size"])
        lf.lfWeight = 700 if f.get("weight") == "bold" else 400
        lf.lfCharSet = 1                                  # DEFAULT_CHARSET
        lf.lfFaceName = str(f["family"])[:31]
        imm = ctypes.windll.imm32
        imm.ImmGetContext.restype = ctypes.c_void_p
        imm.ImmGetContext.argtypes = [ctypes.c_void_p]
        imm.ImmSetCompositionFontW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_LOGFONTW)]
        imm.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        hwnd = w.winfo_id()
        himc = imm.ImmGetContext(hwnd)
        if not himc:
            return False
        try:
            return bool(imm.ImmSetCompositionFontW(himc, ctypes.byref(lf)))
        finally:
            imm.ImmReleaseContext(hwnd, himc)
    except Exception:
        return False


# ── 둥근 모서리: 테두리 없는 창을 둥근 사각형 모양으로 오려 낸다 (윈도우 창 영역) ──
def round_corners(win, radius):
    """win(테두리 없는 Toplevel)의 모서리를 radius(px) 만큼 둥글게. 창 크기가 바뀔 때마다 다시 부른다. 안 되는 PC에서는 조용히 넘어간다."""
    try:
        u, g = ctypes.windll.user32, ctypes.windll.gdi32
        u.GetAncestor.restype = ctypes.c_void_p
        u.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        g.CreateRoundRectRgn.restype = ctypes.c_void_p
        u.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        hwnd = u.GetAncestor(win.winfo_id(), 2)              # GA_ROOT: Tk 가 감싼 바깥 창
        w, h = win.winfo_width(), win.winfo_height()
        if not hwnd or w < 20 or h < 20 or getattr(win, "_rounded", None) == (w, h):     # 같은 크기면 다시 하지 않는다 (신호가 되풀이되지 않게)
            return False
        win._rounded = (w, h)
        rgn = g.CreateRoundRectRgn(0, 0, w + 1, h + 1, 2 * radius, 2 * radius)
        return bool(u.SetWindowRgn(hwnd, rgn, True))         # 영역은 이 뒤로 윈도우가 관리한다
    except Exception:
        return False


def make_round(win, radius):
    win.bind("<Configure>", lambda e: round_corners(win, radius) if e.widget is win else None, add="+")
    win.after(60, lambda: win.winfo_exists() and round_corners(win, radius))


def memo_fs(m):
    try:
        return max(FS_MIN, min(FS_MAX, int(m.get("fs") or FS_DEF)))
    except Exception:
        return FS_DEF


def memo_alpha(m):
    try:
        return max(ALPHA_MIN, min(1.0, float(m.get("alpha", 1.0))))
    except Exception:
        return 1.0


def new_memo(text="", kind="text"):
    return {"id": uuid.uuid4().hex[:10], "title": "", "kind": kind, "text": text, "items": [],
            "alarm": None, "fired": False, "open": False, "x": None, "y": None,
            "color": "yellow", "alpha": 1.0, "w": None, "h": None, "fs": FS_DEF}


# ── 알림 시각 ──
def parse_alarm(s, now=None):
    """«15:30» «1530» «내일 9:00» «11/26 15:30» → datetime. 못 읽으면 None. 날짜 없이 시각만 적었는데 이미 지났으면 내일."""
    now = now or datetime.now()
    s = (s or "").strip().replace("：", ":")
    day = None
    if s.startswith("내일"):
        day, s = (now + timedelta(days=1)).date(), s[2:].strip()
    elif s.startswith("오늘"):
        day, s = now.date(), s[2:].strip()
    parts = s.split()
    if len(parts) == 2:
        try:
            m, d = parts[0].replace("-", "/").replace(".", "/").strip("/").split("/")[-2:]
            day = datetime(now.year, int(m), int(d)).date()
            if day < now.date() - timedelta(days=1):
                day = day.replace(year=now.year + 1)
        except Exception:
            return None
        s = parts[1]
    elif len(parts) != 1:
        return None
    try:
        if ":" in s:
            h, mi = s.split(":")
        elif s.isdigit() and len(s) in (3, 4):
            h, mi = s[:-2], s[-2:]
        elif s.isdigit():
            h, mi = s, "0"
        else:
            return None
        h, mi = int(h), int(mi)
        if not (0 <= h < 24 and 0 <= mi < 60):
            return None
    except Exception:
        return None
    if day is None:
        dt = datetime.combine(now.date(), datetime.min.time()).replace(hour=h, minute=mi)
        return dt if dt > now else dt + timedelta(days=1)
    return datetime.combine(day, datetime.min.time()).replace(hour=h, minute=mi)


def alarm_dt(m):
    try:
        return datetime.fromisoformat(m["alarm"]) if m.get("alarm") else None
    except Exception:
        return None


def alarm_label(dt, now=None):
    now = now or datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    if dt.date() == (now + timedelta(days=1)).date():
        return "내일 " + dt.strftime("%H:%M")
    return "%d/%d %s" % (dt.month, dt.day, dt.strftime("%H:%M"))


def remain_label(dt, now=None):
    """«N분 후» «1시간 30분 후» «2일 후» — 알림까지 남은 시간 (올림, 1분 안이면 «곧»)"""
    now = now or datetime.now()
    mins = -(-int((dt - now).total_seconds()) // 60)          # 올림
    if mins <= 0:
        return "곧"
    if mins < 60:
        return "%d분 후" % mins
    if mins < 1440:
        h, mi = divmod(mins, 60)
        return "%d시간 %s후" % (h, "%d분 " % mi if mi else "")
    return "%d일 후" % (mins // 1440)


def alarm_text(dt, now=None):
    return "  ⏰ %s(%s)에 알려드려요.(누르면 바꾸기)" % (alarm_label(dt, now), remain_label(dt, now))


def memo_name(m, n=8):
    t = (m.get("title") or "").strip()
    if not t:
        if m.get("kind") == "check":
            t = next((i["t"] for i in m.get("items") or [] if i.get("t")), "")
        else:
            t = next((l for l in (m.get("text") or "").splitlines() if l.strip()), "")
    t = t.strip() or "새 메모"
    return t if len(t) <= n else t[:n - 1] + "…"


# ── 위젯 아래 메모 줄 ──
class MemoStrip(tk.Frame):
    def __init__(self, master, bg, px, font, memos, save, notify, topmost):
        super().__init__(master, bg=bg)
        self.bg, self.px, self.font = bg, px, font
        self.memos = [m for m in memos if isinstance(m, dict) and m.get("id")]
        self._save, self.notify, self.topmost = save, notify, topmost
        self.wins = {}
        self.save_job = None
        self.active = True
        tk.Label(self, text="📝", bg=bg, font=font(9)).pack(side="left", padx=(px(2), px(2)))
        self.chips = tk.Frame(self, bg=bg)
        self.chips.pack(side="left", fill="x", expand=True)
        add = tk.Label(self, text="＋ 새 메모", bg=bg, fg="#00754A", font=font(8, True), cursor="hand2", padx=px(4))
        add.pack(side="right")
        add.bind("<Button-1>", lambda e: self.new())
        self.refresh()
        self.after(ALARM_EVERY, self._alarm_loop)

    # 저장 (글자를 칠 때마다가 아니라 잠깐 멈추면)
    def changed(self, now=False):
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        if now:
            self.flush()
        else:
            self.save_job = self.after(700, self.flush)

    def flush(self):
        self.save_job = None
        try:
            self._save(self.memos)
        except Exception:
            pass

    def find(self, mid):
        return next((m for m in self.memos if m["id"] == mid), None)

    def refresh(self):
        for w in self.chips.winfo_children():
            w.destroy()
        px = self.px
        if not self.memos:
            tk.Label(self.chips, text="메모가 없어요 — ＋ 새 메모", bg=self.bg, fg=HINT, font=self.font(8)).pack(side="left")
            return
        for m in self.memos[:CHIP_MAX]:
            self._chip(m)
        rest = self.memos[CHIP_MAX:]
        if rest:
            more = tk.Label(self.chips, text="외 %d개 ▾" % len(rest), bg=self.bg, fg="#6b6b6b", font=self.font(8), cursor="hand2", padx=px(3))
            more.pack(side="left", padx=(px(2), 0))
            more.bind("<Button-1>", lambda e: self._more_menu(e, rest))

    def _chip(self, m):
        px = self.px
        t = memo_name(m, 7)
        if m.get("kind") == "check" and m.get("items"):
            t += " %d/%d" % (sum(1 for i in m["items"] if i.get("done")), len(m["items"]))
        if alarm_dt(m) and not m.get("fired"):
            t = "⏰" + t
        opened = m["id"] in self.wins
        p = pal(m)
        c = tk.Label(self.chips, text=t, bg=p["head"] if opened else p["bg"], fg=INK, font=self.font(8, opened), cursor="hand2",
                     padx=px(5), pady=px(1), highlightthickness=1, highlightbackground=p["edge"])
        c.pack(side="left", padx=(0, px(3)))
        c.bind("<Button-1>", lambda e, k=m["id"]: self.toggle(k))

    def _more_menu(self, e, rest):
        mn = tk.Menu(self, tearoff=0, font=self.font(9))
        for m in rest:
            mn.add_command(label=("⏰ " if alarm_dt(m) and not m.get("fired") else "") + memo_name(m, 20),
                           command=lambda k=m["id"]: self.open(k))
        mn.tk_popup(e.x_root, e.y_root)

    # 열기·닫기·새로·지우기
    def new(self):
        m = new_memo()
        self.memos.insert(0, m)
        self.open(m["id"])
        self.changed(now=True)

    def toggle(self, mid):
        if mid in self.wins:
            self.close(mid)
        else:
            self.open(mid)

    def open(self, mid, flash=False):
        m = self.find(mid)
        if m is None:
            return
        w = self.wins.get(mid)
        if w is None:
            w = self.wins[mid] = PostIt(self, m, len(self.wins))
        else:
            w.lift()
        m["open"] = True
        if flash:
            w.flash()
        self.refresh()
        self.changed()

    def close(self, mid):
        w = self.wins.pop(mid, None)
        if w is not None:
            w.save_pos()
            w.destroy()
        m = self.find(mid)
        if m:
            m["open"] = False
        self.refresh()
        self.changed(now=True)

    def delete(self, mid, parent=None):
        m = self.find(mid)
        if m is None:
            return
        if not messagebox.askyesno("메모 지우기", "«%s» 메모를 지울까요?\n지우면 되살릴 수 없어요." % memo_name(m, 20), parent=parent or self):
            return
        w = self.wins.pop(mid, None)
        if w is not None:
            w.destroy()
        self.memos = [x for x in self.memos if x["id"] != mid]
        self.refresh()
        self.changed(now=True)

    def reopen(self):
        """위젯을 켤 때: 열어 둔 채로 끈 메모는 다시 연다"""
        for m in self.memos:
            if m.get("open") and m["id"] not in self.wins:
                self.wins[m["id"]] = PostIt(self, m, len(self.wins))
        self.refresh()

    def set_active(self, on):
        """메모 줄을 끄면 포스트잇도 숨기고 알림도 쉰다"""
        self.active = on
        for w in self.wins.values():
            if on:
                w.deiconify()
            else:
                w.withdraw()

    # 알림
    def _alarm_loop(self):
        self.after(ALARM_EVERY, self._alarm_loop)
        if not self.active:
            return
        now = datetime.now()
        hit = False
        for w in list(self.wins.values()):                     # 열린 메모의 «N분 후» 를 맞춘다
            w.tick_alarm_text(now)
        for m in self.memos:
            dt = alarm_dt(m)
            if dt and not m.get("fired") and now >= dt:
                m["fired"] = True
                hit = True
                body = [l.strip() for l in (m.get("text") or "").strip().splitlines() if l.strip()]
                if m.get("kind") == "check":
                    body = ["☐ " + i["t"] for i in m.get("items") or [] if not i.get("done")]
                late = now - dt > timedelta(minutes=10)
                self.open(m["id"], flash=True)
                try:
                    self.alarm_popup(m, dt, late, body)
                except Exception:
                    try:                                    # 알림 창이 안 뜨면 예전처럼 트레이 풍선
                        self.notify("⏰ %s" % memo_name(m, 30), "\n".join(body[:3]) or "%s 메모 알림이에요." % dt.strftime("%H:%M"))
                    except Exception:
                        pass
        if hit:
            self.changed(now=True)

    def alarm_popup(self, m, dt, late, body):
        title = "⏰ " + memo_name(m, 30) + (" (지난 알림)" if late else "")
        notice_popup(self, self.px, self.font, title, "%s 에 맞춘 알림이에요" % alarm_label(dt), body, pal(m))


# ── 화면 가운데 «업무위젯 알림» 창 (윈도우 풍선 알림은 앱 이름이 Python 으로 나와서 쓰지 않는다) ──
_LIVE_NOTICES = []


def notice_popup(master, px, font, title, sub="", body=(), p=None, warn=False):
    p = p or PALETTE["yellow"]
    d = tk.Toplevel(master)
    d.overrideredirect(True)
    d.attributes("-topmost", True)
    edge = "#c82014" if warn else p["edge"]
    d.configure(bg=edge)
    inner = tk.Frame(d, bg=p["bg"])
    inner.pack(fill="both", expand=True, padx=2, pady=2)
    head = tk.Frame(inner, bg=p["head"])
    head.pack(fill="x")
    tk.Label(head, text="🔔 업무위젯 알림", bg=p["head"], fg=INK, font=font(9, True)).pack(side="left", padx=px(10), pady=px(6))
    x = tk.Label(head, text="✕", bg=p["head"], fg="#5c5c5c", font=font(9), cursor="hand2", padx=px(10))
    x.pack(side="right")
    x.bind("<Button-1>", lambda e: d.destroy())
    tk.Label(inner, text=title, bg=p["bg"], fg="#c82014" if warn else INK, font=font(13, True), wraplength=px(340),
             justify="left").pack(anchor="w", padx=px(16), pady=(px(14), px(2)))
    if sub:
        tk.Label(inner, text=sub, bg=p["bg"], fg="#c26a00", font=font(9)).pack(anchor="w", padx=px(16))
    body = list(body)
    if body:
        more = len(body) - 5
        txt = "\n".join(l if len(l) <= 40 else l[:39] + "…" for l in body[:5]) + ("\n… 외 %d줄" % more if more > 0 else "")
        tk.Label(inner, text=txt, bg=p["bg"], fg=INK, font=font(10), wraplength=px(340), justify="left"
                 ).pack(anchor="w", padx=px(16), pady=(px(8), 0))
    tk.Button(inner, text="확인", font=font(10, True), relief="groove", bg="#00754A", fg="#ffffff", padx=px(22),
              command=d.destroy).pack(pady=(px(14), px(14)))
    d.update_idletasks()
    w, h = max(px(320), d.winfo_reqwidth()), d.winfo_reqheight()
    sw, sh = d.winfo_screenwidth(), d.winfo_screenheight()
    live = [q for q in _LIVE_NOTICES if q.winfo_exists()]
    off = len(live) * px(28)                           # 여러 개가 한꺼번에 울리면 조금씩 비껴 쌓는다
    d.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2 + off), max(0, (sh - h) // 2 + off)))
    make_round(d, px(12))
    d.lift()
    _LIVE_NOTICES[:] = live + [d]
    try:
        d.bell()
    except Exception:
        pass
    return d


# ── 포스트잇 창 ──
class PostIt(tk.Toplevel):
    def __init__(self, strip, m, nth):
        super().__init__(strip)
        self.strip, self.m, self.px, self.font = strip, m, strip.px, strip.font
        px = self.px
        self.c = c = pal(m)
        self.min_w, self.min_h = px(190), px(120)
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", bool(strip.topmost()))
        except Exception:
            pass
        try:
            self.attributes("-alpha", memo_alpha(m))
        except Exception:
            pass
        self.configure(bg=c["edge"])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        try:
            W, H = int(m.get("w") or px(250)), int(m.get("h") or px(230))
        except Exception:
            W, H = px(250), px(230)
        W, H = max(self.min_w, min(W, sw)), max(self.min_h, min(H, sh - px(40)))
        root = strip.winfo_toplevel()
        x, y = m.get("x"), m.get("y")
        if x is None or y is None:
            step = W + px(8)                                   # 여러 개면 위젯 왼쪽으로 나란히
            x = root.winfo_rootx() - (nth + 1) * step
            if x < 0:
                x = root.winfo_rootx() + root.winfo_width() + px(8) + nth * step
            y = root.winfo_rooty()
        x, y = max(0, min(int(x), sw - W)), max(0, min(int(y), sh - H - px(40)))
        self.geometry("%dx%d+%d+%d" % (W, H, x, y))
        make_round(self, px(12))
        self.inner = inner = tk.Frame(self, bg=c["bg"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # 머리줄: 제목 · 메모장/체크 · 🎨 · ⏰ · 🗑 · ✕  (머리줄을 끌어 옮긴다)
        # 맨 위 빈 줄은 «잡는 곳»: 제목칸을 누르지 않고 여기를 끌어 옮긴다
        self.handle = tk.Frame(inner, bg=c["head"], height=px(12), cursor="fleur")
        self.handle.pack(fill="x")
        self.head = head = tk.Frame(inner, bg=c["head"])
        head.pack(fill="x")
        self.title_e = tk.Entry(head, relief="flat", bd=0, bg=c["head"], fg=INK, font=self.font(9, True), width=6,
                                insertbackground=INK)
        self.title_e.pack(side="left", fill="x", expand=True, padx=(px(6), px(2)), pady=px(4))
        self.title_e.insert(0, m.get("title") or "")
        self._hint(self.title_e, "제목", lambda t: self._set("title", t))
        self.btns = []
        for text, cmd, tip in (("✕", self.close, "닫기"), ("🗑", self.delete, "지우기"),
                               ("⏰", self.alarm_dialog, "알림 시각"), ("🎨", self.style_dialog, "색·투명도"),
                               ("", self.switch, "")):
            b = tk.Label(head, text=text, bg=c["head"], fg="#5c5c5c", font=self.font(9), cursor="hand2", padx=px(3))
            b.pack(side="right", padx=(0, px(5)) if text == "✕" else 0)    # ✕ 는 오른쪽 크기 조절 띠와 떨어뜨린다
            b.bind("<Button-1>", lambda e, c=cmd: c())
            self.btns.append(b)
        self.mode_b = self.btns[-1]
        self.mode_b.configure(font=self.font(8, True), fg="#00754A")
        for w in (self.handle, head):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<ButtonRelease-1>", lambda e: self.save_pos())

        self.alarm_lb = tk.Label(inner, bg=c["bg"], fg="#c26a00", font=self.font(8), anchor="w", cursor="hand2")
        self.alarm_lb.bind("<Button-1>", lambda e: self.alarm_dialog())
        self.body = tk.Frame(inner, bg=c["bg"])
        self.body.pack(fill="both", expand=True)
        self.show_alarm()
        self.build_body()

        # 크기 조절: 네 가장자리와 네 모서리를 끈다 (n 위 · s 아래 · w 왼쪽 · e 오른쪽, 위·왼쪽은 창 위치도 같이 옮긴다)
        k, t, s = px(10), px(4), px(5)               # 모서리 한 변 · 위쪽 띠 두께 · 옆·아래 띠 두께
        g = px(14)                                     # 오른쪽 아래 손잡이
        self.edges, self.edges_head = [], []
        specs = (                                      # (방향, 커서, 머리줄 색인가, place 인자)
            ("n", "size_ns", True, dict(x=k, y=0, height=t, relwidth=1.0, width=-2 * k)),
            ("s", "size_ns", False, dict(x=k, rely=1.0, anchor="sw", height=s, relwidth=1.0, width=-(k + g))),
            ("w", "size_we", False, dict(x=0, y=k, width=s, relheight=1.0, height=-(k + k))),
            ("e", "size_we", False, dict(relx=1.0, y=k, anchor="ne", width=s, relheight=1.0, height=-(k + g))),
            ("nw", "size_nw_se", True, dict(x=0, y=0, width=k, height=k)),
            ("ne", "size_ne_sw", True, dict(relx=1.0, y=0, anchor="ne", width=k, height=k)),
            ("sw", "size_ne_sw", False, dict(x=0, rely=1.0, anchor="sw", width=k, height=k)),
        )
        for mode, cur, on_head, kw in specs:
            f = tk.Frame(self, bg=c["head"] if on_head else c["bg"], cursor=cur)
            f.place(**kw)
            (self.edges_head if on_head else self.edges).append(f)
            self._rs_bind(f, mode)
        self.grip = gr = tk.Label(self, text="◢", bg=c["bg"], fg=c["edge"], font=self.font(8), cursor="size_nw_se",
                                  bd=0, padx=0, pady=0, anchor="se")
        gr.place(relx=1.0, rely=1.0, x=-px(5), y=-px(5), anchor="se", width=g, height=g)     # 둥근 모서리에 잘리지 않게 안쪽으로
        self._rs_bind(gr, "se")

    # 글자 받기: 테두리 없는 창은 누를 때 한 번 앞으로 가져와야 키보드가 들어온다 (포커스 이벤트 안에서는 옮기지 않는다)
    def _grab(self, w):
        w.bind("<Button-1>", lambda e: self._focus(w), add="+")
        w.bind("<FocusIn>", lambda e: ime_font(w), add="+")             # 입력 중인 글자 창 크기를 칸 글씨에 맞춘다
        w.bind("<KeyPress>", lambda e: self._ime_once(w), add="+")

    def _ime_once(self, w):
        try:
            key = (w.winfo_id(), str(w.cget("font")))
        except Exception:
            return
        if getattr(self, "_ime_key", None) != key:                       # 같은 칸·같은 글씨면 한 번만
            self._ime_key = key
            ime_font(w)

    def _focus(self, w):
        if self.focus_get() is not w:
            try:
                self.focus_force()
                w.focus_set()
            except Exception:
                pass

    def _hint(self, e, hint, on_change):
        """빈 칸이면 흐린 안내 글자"""
        def show():
            if not e.get():
                e.insert(0, hint)
                e.configure(fg=HINT)

        def fin(ev):
            if e.cget("fg") == HINT:
                e.delete(0, "end")
                e.configure(fg=INK)

        def fout(ev):
            if e.cget("fg") != HINT:
                on_change(e.get().strip())
            show()

        e.bind("<FocusIn>", fin)
        e.bind("<FocusOut>", fout)
        e.bind("<KeyRelease>", lambda ev: on_change(e.get().strip()) if e.cget("fg") != HINT else None)
        e.bind("<Return>", lambda ev: self.focus_set())
        self._grab(e)
        show()

    def _set(self, key, val):
        if self.m.get(key) != val:
            self.m[key] = val
            self.strip.changed()
            if key in ("title",):
                self.strip.refresh()

    # 본문: 메모장 / 체크리스트
    def build_body(self):
        for w in self.body.winfo_children():
            w.destroy()
        px = self.px
        c = self.c
        self.__dict__.pop("text_w", None)      # 부서진 글칸을 가리키지 않게
        if self.m.get("kind") == "check":
            self.mode_b.configure(text="메모장")
            box = tk.Text(self.body, bg=c["bg"], relief="flat", bd=0, cursor="arrow", wrap="none", height=1,
                          highlightthickness=0, padx=px(4), pady=px(2))
            box.pack(fill="both", expand=True)
            box.bind("<MouseWheel>", lambda e: box.yview_scroll(-1 if e.delta > 0 else 1, "units"))
            box.bind("<Control-MouseWheel>", self._fs_wheel)
            for i, it in enumerate(self.m.get("items") or []):
                box.window_create("end", window=self._row(box, i, it))
                box.insert("end", "\n")
            box.configure(state="disabled")
            self.add_e = e = tk.Entry(self.body, relief="flat", bd=0, bg=c["field"], fg=INK, font=self.font(memo_fs(self.m)), insertbackground=INK)
            e.pack(fill="x", padx=px(6), pady=(0, px(8)), ipady=px(3))
            self._hint(e, "＋ 항목 추가 (적고 Enter)", lambda t: None)
            e.bind("<Return>", lambda ev: self.add_item())
            self.after(50, lambda: box.winfo_exists() and box.see("end"))
        else:
            self.mode_b.configure(text="체크리스트")
            t = tk.Text(self.body, bg=c["bg"], relief="flat", bd=0, wrap="word", font=self.font(memo_fs(self.m)), undo=True,
                        highlightthickness=0, padx=px(7), pady=px(5), insertbackground=INK)
            t.pack(fill="both", expand=True)
            t.insert("1.0", self.m.get("text") or "")
            t.edit_reset()
            t.bind("<KeyRelease>", lambda ev: self._set("text", t.get("1.0", "end-1c")))
            t.bind("<FocusOut>", lambda ev: (self._set("text", t.get("1.0", "end-1c")), self.strip.changed(now=True)))
            t.bind("<Control-MouseWheel>", self._fs_wheel)
            self._grab(t)
            self.text_w = t

    # 글씨 크기: 🎨 창의 슬라이더 · 글 위에서 Ctrl+마우스 휠
    def _wrap(self):
        w = self.winfo_width()
        if w < 100:
            w = int(self.m.get("w") or self.px(250))
        return max(self.px(100), w - self.px(90))

    def _fs_wheel(self, e):
        self.set_fs(memo_fs(self.m) + (1 if e.delta > 0 else -1))
        return "break"

    def set_fs(self, v):
        v = max(FS_MIN, min(FS_MAX, int(v)))
        if v == memo_fs(self.m) and self.m.get("fs") == v:
            return
        self.m["fs"] = v
        self.strip.changed()
        if self.m.get("kind") != "check" and hasattr(self, "text_w"):
            self.text_w.configure(font=self.font(v))            # 글칸은 다시 만들지 않는다 (커서·되돌리기 유지)
            ime_font(self.text_w)
        else:
            self.build_body()
        sc = getattr(self, "_fs_scale", None)
        try:
            if sc is not None and sc.winfo_exists() and int(sc.get()) != v:
                sc.set(v)
        except Exception:
            pass

    def _row(self, box, i, it):
        px = self.px
        bg = self.c["bg"]
        f = tk.Frame(box, bg=bg)
        v = tk.BooleanVar(value=bool(it.get("done")))
        cb = tk.Checkbutton(f, variable=v, bg=bg, activebackground=bg, bd=0, highlightthickness=0, cursor="hand2",
                            command=lambda: self.check(i, v.get()))
        cb.pack(side="left")
        lb = tk.Label(f, text=it.get("t", ""), bg=bg, fg=DONE if it.get("done") else INK, font=self.font(memo_fs(self.m)), anchor="w",
                      cursor="hand2", wraplength=self._wrap(), justify="left")
        lb.pack(side="left")
        lb.bind("<Button-1>", lambda e: (v.set(not v.get()), self.check(i, v.get())))
        x = tk.Label(f, text="✕", bg=bg, fg=self.c["edge"], font=self.font(7), cursor="hand2", padx=px(3))
        x.pack(side="left", padx=(px(4), 0))
        x.bind("<Button-1>", lambda e: self.del_item(i))
        return f

    def check(self, i, done):
        self.m["items"][i]["done"] = bool(done)
        self.strip.changed()
        self.strip.refresh()
        self.build_body()

    def add_item(self):
        e = self.add_e
        t = e.get().strip() if e.cget("fg") != HINT else ""
        if not t:
            return "break"
        self.m.setdefault("items", []).append({"t": t, "done": False})
        self.strip.changed()
        self.strip.refresh()
        self.build_body()
        self.after(30, lambda: self._focus(self.add_e) or self.add_e.delete(0, "end") or self.add_e.configure(fg=INK))
        return "break"

    def del_item(self, i):
        del self.m["items"][i]
        self.strip.changed()
        self.strip.refresh()
        self.build_body()

    def switch(self):
        """메모장 ↔ 체크리스트 (줄 → 항목, 항목 → 줄)"""
        if self.m.get("kind") == "check":
            self.m["text"] = "\n".join(("✓ " if i.get("done") else "") + i["t"] for i in self.m.get("items") or [])
            self.m["items"], self.m["kind"] = [], "text"
        else:
            if hasattr(self, "text_w"):
                self.m["text"] = self.text_w.get("1.0", "end-1c")
            self.m["items"] = [{"t": l.strip(), "done": False} for l in (self.m.get("text") or "").splitlines() if l.strip()]
            self.m["text"], self.m["kind"] = "", "check"
        self.strip.changed(now=True)
        self.strip.refresh()
        self.build_body()

    # 알림
    def tick_alarm_text(self, now):
        dt = alarm_dt(self.m)
        if dt and not self.m.get("fired") and self.alarm_lb.winfo_manager():
            t = alarm_text(dt, now)
            if self.alarm_lb.cget("text") != t:
                self.alarm_lb.configure(text=t)

    def show_alarm(self):
        dt = alarm_dt(self.m)
        if dt and not self.m.get("fired"):
            self.alarm_lb.configure(text=alarm_text(dt))
            self.alarm_lb.pack(fill="x", before=self.body)
        else:
            self.alarm_lb.pack_forget()
        self.btns[2].configure(fg="#c26a00" if dt and not self.m.get("fired") else "#5c5c5c")

    def alarm_dialog(self):
        px = self.px
        d = tk.Toplevel(self)
        d.title("메모 알림")
        d.configure(bg=YEL)
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.transient(self)
        tk.Label(d, text="언제 알려 드릴까요?", bg=YEL, fg=INK, font=self.font(10, True)).pack(anchor="w", padx=px(12), pady=(px(10), px(2)))
        tk.Label(d, text="예) 15:30 · 내일 9:00 · 11/26 15:30", bg=YEL, fg="#6b6b6b", font=self.font(8)).pack(anchor="w", padx=px(12))
        e = tk.Entry(d, font=self.font(11), width=16, justify="center")
        e.pack(padx=px(12), pady=px(6))
        dt = alarm_dt(self.m)
        e.insert(0, alarm_label(dt) if dt and not self.m.get("fired") else (datetime.now() + timedelta(minutes=30)).strftime("%H:%M"))
        quick = tk.Frame(d, bg=YEL)
        quick.pack(padx=px(12))
        for lab, mins in (("10분 뒤", 10), ("30분 뒤", 30), ("1시간 뒤", 60)):
            tk.Button(quick, text=lab, font=self.font(8), relief="groove", bg="#fff8dc",
                      command=lambda n=mins: (e.delete(0, "end"), e.insert(0, (datetime.now() + timedelta(minutes=n)).strftime("%H:%M")))
                      ).pack(side="left", padx=px(2))
        err = tk.Label(d, text="", bg=YEL, fg="#c82014", font=self.font(8))
        err.pack()

        def ok(ev=None):
            t = parse_alarm(e.get())
            if t is None:
                err.configure(text="시각을 못 읽었어요. 15:30 처럼 적어 주세요.")
                return
            self.m["alarm"], self.m["fired"] = t.isoformat(timespec="minutes"), False
            self.strip.changed(now=True)
            self.strip.refresh()
            self.show_alarm()
            d.destroy()

        def off():
            self.m["alarm"], self.m["fired"] = None, False
            self.strip.changed(now=True)
            self.strip.refresh()
            self.show_alarm()
            d.destroy()

        bf = tk.Frame(d, bg=YEL)
        bf.pack(pady=(px(2), px(10)))
        tk.Button(bf, text="알림 맞추기", font=self.font(9, True), relief="groove", bg="#00754A", fg="#ffffff", padx=px(8), command=ok).pack(side="left", padx=px(3))
        if dt and not self.m.get("fired"):
            tk.Button(bf, text="알림 끄기", font=self.font(9), relief="groove", bg="#fff8dc", padx=px(6), command=off).pack(side="left", padx=px(3))
        tk.Button(bf, text="취소", font=self.font(9), relief="groove", bg="#fff8dc", padx=px(6), command=d.destroy).pack(side="left", padx=px(3))
        e.bind("<Return>", ok)
        d.update_idletasks()
        d.geometry("+%d+%d" % (self.winfo_rootx() + px(10), self.winfo_rooty() + px(30)))
        d.focus_force()
        e.focus_set()
        e.select_range(0, "end")

    def flash(self, n=8):
        if not self.winfo_exists():
            return
        c = "#f0b429" if n > 0 and n % 2 else self.c["head"]
        self.head.configure(bg=c)
        self.handle.configure(bg=c)
        for w in [self.title_e] + self.btns:
            w.configure(bg=c)
        if n > 0:
            self.after(350, lambda: self.flash(n - 1))

    # 크기 조절
    def _rs_bind(self, w, mode):
        w.bind("<ButtonPress-1>", lambda e: self._rs_start(e, mode))
        w.bind("<B1-Motion>", self._rs_move)
        w.bind("<ButtonRelease-1>", lambda e: self._rs_end())

    def _rs_start(self, e, mode):
        self._rs = (e.x_root, e.y_root, self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height(), mode)

    def _rs_move(self, e):
        px0, py0, x0, y0, w0, h0, mode = self._rs
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dx, dy = e.x_root - px0, e.y_root - py0
        x, y, w, h = x0, y0, w0, h0
        if "e" in mode:
            w = max(self.min_w, min(w0 + dx, sw - x0))
        if "w" in mode:                                  # 왼쪽 끝을 끈다: 오른쪽 끝은 그대로
            w = max(self.min_w, min(w0 - dx, x0 + w0))
            x = x0 + w0 - w
        if "s" in mode:
            h = max(self.min_h, min(h0 + dy, sh - y0))
        if "n" in mode:                                  # 위쪽 끝을 끈다: 아래 끝은 그대로
            h = max(self.min_h, min(h0 - dy, y0 + h0))
            y = y0 + h0 - h
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def _rs_end(self):
        self.m["w"], self.m["h"] = self.winfo_width(), self.winfo_height()
        self.save_pos()
        if self.m.get("kind") == "check":
            self.build_body()

    # 색·투명도
    def apply_theme(self):
        c = self.c = pal(self.m)
        self.configure(bg=c["edge"])
        self.inner.configure(bg=c["bg"])
        self.head.configure(bg=c["head"])
        self.handle.configure(bg=c["head"])
        self.title_e.configure(bg=c["head"])
        for b in self.btns:
            b.configure(bg=c["head"])
        self.alarm_lb.configure(bg=c["bg"])
        self.body.configure(bg=c["bg"])
        for w in self.edges:
            w.configure(bg=c["bg"])
        for w in self.edges_head:
            w.configure(bg=c["head"])
        self.grip.configure(bg=c["bg"], fg=c["edge"])
        if hasattr(self, "text_w"):
            self.m["text"] = self.text_w.get("1.0", "end-1c")
        self.build_body()
        self.strip.refresh()

    def style_dialog(self):
        old = getattr(self, "_style_d", None)
        if old is not None and old.winfo_exists():
            old.lift()
            return
        px = self.px
        NB = "#f6f6f6"
        d = self._style_d = tk.Toplevel(self)
        d.title("메모 꾸미기")
        d.configure(bg=NB)
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.transient(self)
        tk.Label(d, text="배경색", bg=NB, fg=INK, font=self.font(9, True)).pack(anchor="w", padx=px(12), pady=(px(10), px(4)))
        row = tk.Frame(d, bg=NB)
        row.pack(padx=px(10))
        sw = {}

        def mark():
            for k, w in sw.items():
                w.configure(highlightbackground=INK if k == (self.m.get("color") or "yellow") else NB)

        def pick(k):
            self.m["color"] = k
            self.strip.changed(now=True)
            self.apply_theme()
            mark()

        for k, p in PALETTE.items():
            w = tk.Label(row, text="", bg=p["bg"], width=3, height=1, cursor="hand2", relief="solid", bd=1,
                         highlightthickness=2, highlightbackground=NB)
            w.pack(side="left", padx=px(2), pady=px(2))
            w.bind("<Button-1>", lambda e, kk=k: pick(kk))
            sw[k] = w
        mark()
        tk.Label(d, text="투명도  (오른쪽일수록 비쳐 보여요)", bg=NB, fg=INK, font=self.font(9, True)).pack(anchor="w", padx=px(12), pady=(px(8), 0))
        sc = tk.Scale(d, from_=0, to=int(round((1 - ALPHA_MIN) * 100)), orient="horizontal", length=px(220), bg=NB,
                      highlightthickness=0, troughcolor="#dcdcdc", showvalue=True, resolution=5, font=self.font(8))
        sc.set(int(round((1 - memo_alpha(self.m)) * 100)))
        sc.pack(padx=px(12))

        def set_alpha(v):
            a = round(1 - float(v) / 100, 2)
            self.m["alpha"] = a
            try:
                self.attributes("-alpha", a)
            except Exception:
                pass
            self.strip.changed()

        sc.configure(command=set_alpha)
        tk.Label(d, text="글씨 크기  (글 위에서 Ctrl+마우스 휠로도 바꿔요)", bg=NB, fg=INK, font=self.font(9, True)).pack(anchor="w", padx=px(12), pady=(px(8), 0))
        fs = self._fs_scale = tk.Scale(d, from_=FS_MIN, to=FS_MAX, orient="horizontal", length=px(220), bg=NB, highlightthickness=0,
                                       troughcolor="#dcdcdc", showvalue=True, resolution=1, font=self.font(8))
        fs.set(memo_fs(self.m))
        fs.pack(padx=px(12))
        fs.configure(command=lambda v: self.set_fs(int(float(v))))
        tk.Button(d, text="닫기", font=self.font(9), relief="groove", padx=px(10), command=d.destroy).pack(pady=(px(4), px(10)))
        d.update_idletasks()
        d.geometry("+%d+%d" % (self.winfo_rootx() + px(10), self.winfo_rooty() + px(30)))

    # 옮기기·닫기·지우기
    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.winfo_x(), e.y_root - self.winfo_y()

    def _drag(self, e):
        self.geometry("+%d+%d" % (e.x_root - self._dx, e.y_root - self._dy))

    def save_pos(self):
        try:
            self.m["x"], self.m["y"] = self.winfo_x(), self.winfo_y()
            self.strip.changed()
        except Exception:
            pass

    def close(self):
        if hasattr(self, "text_w"):
            self._set("text", self.text_w.get("1.0", "end-1c"))
        self.strip.close(self.m["id"])

    def delete(self):
        self.strip.delete(self.m["id"], parent=self)
