# -*- coding: utf-8 -*-
"""업무 위젯 — 시계 · 업무포털 · 나이스 · 내부기안 · 품의등록 단추 + 에듀파인 결재대기·통합관리 기관접수대기 건수 타일 (⚙ 에서 투명도·시계 카드, 마지막 위치 기억).

키트의 «바로가기위젯.pyw» 를 이 파일로 바꿔 끼워 쓴다 (설치 파일이 원본을 «바로가기위젯_원본.pyw» 로 보관한다).
한 개만 뜨기·바탕화면/시작프로그램 바로가기·설정 창의 «위젯 켜기»·화면 밖 되돌리기는 원본의 것을 그대로 가져다 쓴다.

단추는 키트 폴더의 open_portal.py · open_neis.py · open_gian.py · open_pumui.py 를 돌리고, 결재대기 칸은 check_sanctn.py(읽기만)를 30분마다 돌린다.
  업무포털 — 인증서 로그인 후 업무포털 메인 화면까지
  나이스   — 인증서 로그인 후 나이스 화면까지
  내부기안 — 에듀파인 공용서식 «표준 서식(결재4인,협조4인)» 빈 기안 창
  품의등록 — 에듀파인 학교회계 > 사업담당 > 품의/정산 > 품의등록 빈 화면
모두 신청·저장·결재·상신은 하지 않는다. 인증서 암호는 이 파일이 다루지 않는다 (키트가 자격 증명 관리자에서 읽는다).
"""
import importlib.machinery
import importlib.util
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

HERE0 = Path(__file__).resolve().parent
_orig = HERE0 / "바로가기위젯_원본.pyw"
if not _orig.exists():                       # 설치가 덜 됐거나 원본을 지운 경우 — 원본 없이는 뜨지 않는다
    raise SystemExit("바로가기위젯_원본.pyw 가 없습니다. 업무위젯 설치를 다시 실행하세요.")
_loader = importlib.machinery.SourceFileLoader("kit_widget_orig", str(_orig))
K = importlib.util.module_from_spec(importlib.util.spec_from_loader("kit_widget_orig", _loader))
_loader.exec_module(K)

KIT = K.HERE.parent
try:                                         # 자동 업데이트 (서명 확인) — 없거나 고장 나도 위젯은 그대로 뜬다
    _uspec = importlib.util.spec_from_file_location("work_widget_update", KIT / "work_widget_update.py")
    UPD = importlib.util.module_from_spec(_uspec)
    _uspec.loader.exec_module(UPD)
except Exception:
    UPD = None
UPDATE_EVERY_MS = 6 * 60 * 60 * 1000     # 6시간마다 새 버전 확인 (켜고 2분 뒤 첫 확인)
SIZE_W, SIZE_H = 424, 190
TILE, GAP, PAD = 60, 6, 12
PANEL, TILE_BG, EDGE, GREEN, WHITE = "#f4f6fa", "#ffffff", "#e3e7ee", "#16a34a", "#111827"   # 밝은 테마: 판 / 타일 / 테두리 / 강조(초록) / 글자
FONT = "Malgun Gothic"
KEY = "#010203"        # 이 색은 투명하게 빠진다 (둥근 모서리용)
ACCENT = {"portal": ("#2563eb", "#dbeafe", "#eff6ff"), "neis": ("#ea580c", "#ffedd5", "#fff7ed"),
          "gian": ("#7c3aed", "#ede9fe", "#f5f3ff"), "pumui": ("#0d9488", "#ccfbf1", "#f0fdfa")}      # (강조색, 아이콘 배경, 눌렀을 때 타일 바탕)

JOBS = {
    "portal": ("open_portal.py", "업무포털 메인 화면을 열었습니다", "✅ 업무포털 메인 화면을 열었습니다"),
    "neis":   ("open_neis.py", "나이스 화면을 열었습니다", "✅ 나이스 화면을 열었습니다 (로그인됨)"),
    "gian":   ("open_gian.py", "내부기안 창을 열었습니다", "✅ 내부기안 창을 열었습니다 (작성·저장·상신은 안 함)"),
    "pumui":  ("open_pumui.py", "품의등록 화면을 열었습니다", "✅ 품의등록 화면을 열었습니다 (입력·저장·결재요청은 안 함)"),
    "jeopsu": ("open_jeopsu.py", "기관접수대기 화면을 열었습니다", "✅ 기관접수대기 화면을 열었습니다 (접수·제출은 안 함)"),
}
BUTTONS = [("portal", "🏫", "1. 업무포털"), ("neis", "🗂", "2. 나이스"), ("gian", "📝", "3. 내부기안"), ("pumui", "🧾", "4. 품의등록")]
CLOCK_KEYS = ("mo", "dd", "wk", "hh", "mi", "ss")
CLOCK_LABEL = {"mo": "월", "dd": "일", "wk": "요일", "hh": "시", "mi": "분", "ss": "초"}
SANCTN_EVERY_MS =30 * 60 * 1000        # 에듀파인 결재대기 건수를 30분마다 읽는다 (읽기만 함)


def round_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


# ── 시스템 트레이 아이콘 (순수 윈도우 API — 추가 설치 없음) ──
import ctypes
import queue
from ctypes import wintypes as _wt

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_LRESULT = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(_LRESULT, _wt.HWND, _wt.UINT, _wt.WPARAM, _wt.LPARAM)


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", _wt.UINT), ("lpfnWndProc", _WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", _wt.HINSTANCE), ("hIcon", _wt.HICON), ("hCursor", _wt.HANDLE), ("hbrBackground", _wt.HBRUSH),
                ("lpszMenuName", _wt.LPCWSTR), ("lpszClassName", _wt.LPCWSTR)]


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", _wt.DWORD), ("hWnd", _wt.HWND), ("uID", _wt.UINT), ("uFlags", _wt.UINT), ("uCallbackMessage", _wt.UINT),
                ("hIcon", _wt.HICON), ("szTip", ctypes.c_wchar * 128), ("dwState", _wt.DWORD), ("dwStateMask", _wt.DWORD),
                ("szInfo", ctypes.c_wchar * 256), ("uVersion", _wt.UINT), ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", _wt.DWORD), ("guidItem", ctypes.c_ubyte * 16), ("hBalloonIcon", _wt.HICON)]


_user32.DefWindowProcW.argtypes = [_wt.HWND, _wt.UINT, _wt.WPARAM, _wt.LPARAM]
_user32.DefWindowProcW.restype = _LRESULT
_user32.CreateWindowExW.argtypes = [_wt.DWORD, _wt.LPCWSTR, _wt.LPCWSTR, _wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, _wt.HINSTANCE, ctypes.c_void_p]
_user32.CreateWindowExW.restype = _wt.HWND
_user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
_user32.GetMessageW.argtypes = [ctypes.POINTER(_wt.MSG), _wt.HWND, _wt.UINT, _wt.UINT]
_user32.CreatePopupMenu.restype = ctypes.c_void_p
_user32.AppendMenuW.argtypes = [ctypes.c_void_p, _wt.UINT, ctypes.c_size_t, _wt.LPCWSTR]
_user32.TrackPopupMenu.argtypes = [ctypes.c_void_p, _wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, _wt.HWND, ctypes.c_void_p]
_user32.DestroyMenu.argtypes = [ctypes.c_void_p]
_user32.LoadImageW.argtypes = [_wt.HINSTANCE, _wt.LPCWSTR, _wt.UINT, ctypes.c_int, ctypes.c_int, _wt.UINT]
_user32.LoadImageW.restype = _wt.HANDLE
_user32.PostMessageW.argtypes = [_wt.HWND, _wt.UINT, _wt.WPARAM, _wt.LPARAM]
_user32.SetForegroundWindow.argtypes = [_wt.HWND]
_kernel32.GetModuleHandleW.restype = _wt.HINSTANCE
_shell32.Shell_NotifyIconW.argtypes = [_wt.DWORD, ctypes.POINTER(_NOTIFYICONDATAW)]


class Tray:
    """시스템 트레이(작업표시줄 오른쪽 아래) 아이콘. 왼쪽 클릭=열기, 오른쪽 클릭=메뉴. 눌림은 queue 로 Tk 쪽에 넘긴다."""
    CB = 0x8000 + 1          # WM_APP+1
    UID = 1

    def __init__(self, ico_path, tip, get_auto):
        self.q = queue.Queue()
        self.tip = tip
        self.get_auto = get_auto       # 자동 실행이 켜져 있는지 (캐시된 값 — 다른 스레드에서 Tk 를 건드리지 않는다)
        self.added = False
        self.hwnd = None
        self.hicon = _user32.LoadImageW(None, str(ico_path), 1, 16, 16, 0x10) if Path(ico_path).exists() else None
        if not self.hicon:
            self.hicon = _user32.LoadImageW(None, "#32512", 1, 16, 16, 0x8000) or None   # 기본 아이콘
        self.taskbar_created = _user32.RegisterWindowMessageW("TaskbarCreated")
        self._proc = _WNDPROC(self._wndproc)       # 파이썬이 지우지 못하게 붙들어 둔다
        ready = threading.Event()
        threading.Thread(target=self._loop, args=(ready,), daemon=True).start()
        ready.wait(3)

    def _loop(self, ready):
        wc = _WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = _kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "UpmuWidgetTray"
        _user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = _user32.CreateWindowExW(0, "UpmuWidgetTray", "UpmuWidgetTray", 0, 0, 0, 0, 0,
                                            ctypes.c_void_p(-3), None, wc.hInstance, None)   # -3 = 메시지 전용 창
        ready.set()
        msg = _wt.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    def _data(self):
        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = self.UID
        nid.uFlags = 0x1 | 0x2 | 0x4          # MESSAGE | ICON | TIP
        nid.uCallbackMessage = self.CB
        nid.hIcon = self.hicon
        nid.szTip = self.tip[:120]
        return nid

    def add(self):
        if self.hwnd and not self.added:
            self.added = bool(_shell32.Shell_NotifyIconW(0, ctypes.byref(self._data())))   # NIM_ADD
        return self.added

    def remove(self):
        if self.hwnd and self.added:
            _shell32.Shell_NotifyIconW(2, ctypes.byref(self._data()))                     # NIM_DELETE
            self.added = False

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == self.CB:
                ev = lparam & 0xFFFF
                if ev in (0x202, 0x203):          # 왼쪽 단추 뗌 / 더블클릭 → 열기
                    self.q.put("show")
                elif ev == 0x205:                 # 오른쪽 단추 뗌 → 메뉴
                    self._menu(hwnd)
                return 0
            if msg == self.taskbar_created and self.added:     # 탐색기가 다시 떠도 아이콘을 되살린다
                self.added = False
                self.add()
                return 0
        except Exception:
            pass
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _menu(self, hwnd):
        m = _user32.CreatePopupMenu()
        _user32.AppendMenuW(m, 0, 1, "열기")
        _user32.AppendMenuW(m, 0x8 if self.get_auto() else 0, 2, "윈도우 시작할 때 자동 실행")   # 0x8 = 체크
        _user32.AppendMenuW(m, 0x800, 0, None)                                                   # 구분선
        _user32.AppendMenuW(m, 0, 3, "위젯 완전 종료")
        pt = _wt.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        _user32.SetForegroundWindow(hwnd)
        cmd = _user32.TrackPopupMenu(m, 0x100 | 0x80, pt.x, pt.y, 0, hwnd, None)    # RETURNCMD | NONOTIFY
        _user32.PostMessageW(hwnd, 0, 0, 0)
        _user32.DestroyMenu(m)
        if cmd:
            self.q.put({1: "show", 2: "auto", 3: "quit"}.get(cmd))


# ── 플립 시계 카드 (Pillow 가 있을 때만 — 없으면 그냥 숫자가 바뀐다) ──
try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    _FLIP_FONT = r"C:\Windows\Fonts\malgunbd.ttf"
    ImageFont.truetype(_FLIP_FONT, 10)
    HAVE_FLIP = True
except Exception:
    HAVE_FLIP = False


class FlipCard:
    """숫자 카드. 값이 바뀌면 윗조각이 접혀 내려오고 아랫조각이 펼쳐지는 모양으로 넘어간다."""
    W, H, SS = 46, 32, 4
    TOP, BOTTOM, LINE = "#f3f5f9", "#e8ecf3", "#c9d1dd"
    FRAMES = 6
    DELAY = 32

    def __init__(self, canvas, cx, cy, bg, color, top=None, bottom=None, line=None):
        self.c, self.bg, self.color = canvas, bg, color
        self.top, self.bottom, self.line = top or self.TOP, bottom or self.BOTTOM, line or self.LINE
        self.cache = {}
        self.cur = None
        self.busy = False
        self.photo = None
        self.item = canvas.create_image(cx, cy, image="")

    def _full(self, text):
        im = self.cache.get(text)
        if im is not None:
            return im
        W, H, S = self.W * self.SS, self.H * self.SS, self.SS
        base = Image.new("RGB", (W, H), self.top)
        ImageDraw.Draw(base).rectangle((0, H // 2, W, H), fill=self.bottom)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=7 * S, fill=255)
        card = Image.new("RGB", (W, H), self.bg)
        card.paste(base, (0, 0), mask)
        d = ImageDraw.Draw(card)
        d.text((W // 2, H // 2), text, font=ImageFont.truetype(_FLIP_FONT, 21 * S), fill=self.color, anchor="mm")
        d.line((0, H // 2, W, H // 2), fill=self.line, width=max(2, S // 2))
        im = card.resize((self.W, self.H), Image.LANCZOS)
        self.cache[text] = im
        return im

    def _show(self, im):
        self.photo = ImageTk.PhotoImage(im)
        self.c.itemconfigure(self.item, image=self.photo)

    def set(self, text):
        self.cur = text
        self._show(self._full(text))

    def flip(self, text):
        if text == self.cur:
            return
        if self.cur is None or self.busy:
            return self.set(text)
        old, new = self._full(self.cur), self._full(text)
        self.cur = text
        self.busy = True
        half = self.H // 2
        frames = []
        for step, s in enumerate((0.66, 0.33, 0.0, 0.33, 0.66, 1.0)):
            if step == 5:
                frames.append(new)
                continue
            im = Image.new("RGB", (self.W, self.H), self.bg)
            im.paste(new.crop((0, 0, self.W, half)), (0, 0))
            im.paste(old.crop((0, half, self.W, self.H)), (0, half))
            if 0 < s < 1 and step < 3:                      # 윗조각이 접힌다 (힌지는 가운데 줄)
                part = old.crop((0, 0, self.W, half)).resize((self.W, max(1, round(half * s))), Image.BILINEAR)
                im.paste(part, (0, half - part.height))
            elif 0 < s < 1:                                 # 아랫조각이 펼쳐진다
                part = new.crop((0, half, self.W, self.H)).resize((self.W, max(1, round(half * s))), Image.BILINEAR)
                im.paste(part, (0, half))
            frames.append(im)

        def run(i=0):
            try:
                self._show(frames[i])
            except Exception:
                self.busy = False
                return
            if i + 1 < len(frames):
                self.c.after(self.DELAY, run, i + 1)
            else:
                self.busy = False
        run()


class Widget:
    def __init__(self):
        st = K.load_state()
        self.root = tk.Tk()
        self.root.title("업무 위젯")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)
        self.opacity = min(1.0, max(0.3, float(st.get("opacity", 1.0))))
        self.root.attributes("-alpha", self.opacity)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = K.fit_on_screen(int(st.get("x", sw - SIZE_W - 40)), int(st.get("y", 40)), SIZE_W, SIZE_H)
        self.root.geometry("%dx%d+%d+%d" % (SIZE_W, SIZE_H, x, y))
        self.bgc = tk.Canvas(self.root, width=SIZE_W, height=SIZE_H, bg=KEY, highlightthickness=0)
        self.bgc.place(x=0, y=0)
        round_rect(self.bgc, 1, 1, SIZE_W - 2, SIZE_H - 2, 20, fill=PANEL, outline="#d9dee7", width=1)
        tk.Misc.lower(self.bgc)
        self.busy = None
        self.lock = threading.Lock()
        self.dragging = False
        self.ticks = 0
        self.root.report_callback_exception = lambda *a: K.log_line("ERROR  " + " ".join(str(v) for v in a[:2]))
        k = K._kernel32()
        self.ev_show = k.CreateEventW(None, False, False, K.SHOW_EVENT)      # 바로가기를 또 누르면 «앞으로 나와»
        self.ev_ack = k.CreateEventW(None, False, False, K.ACK_EVENT)

        # 위쪽 줄: 📍(항상 위) ⚙(환경설정) ✕(닫기)
        bar = tk.Frame(self.root, bg=PANEL)
        bar.pack(fill="x", padx=PAD - 4, pady=(8, 0))
        self.title_lb = tk.Label(bar, text="업무위젯", bg=PANEL, fg="#6b7280", font=(FONT, 9, "bold"))
        self.title_lb.pack(side="left", padx=(10, 0))
        for text, cmd, tip in (("✕", self.minimize, "시스템 트레이로 내리기 (완전 종료: 톱니바퀴 → 위젯 완전 종료)"),
                               ("⚙", self.show_options, "환경설정"),
                               ("📍", self.toggle_pin, "항상 위 켜기/끄기")):
            b = tk.Label(bar, text=text, bg=PANEL, fg="#4b5563", font=(FONT, 10), cursor="hand2", padx=5)
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            if text == "📍":
                self.pin_label = b
            if text == "⚙":
                self.gear = b
        self.pinned = True

        grid = tk.Frame(self.root, bg=PANEL)
        grid.pack(padx=PAD, pady=(2, 0))
        self.tiles = []
        self.clock = {}
        self.cards = {}
        # 윗줄: 월 일 요일 시 분 초 — 따로 된 줄(clock_row)에 둬서, 끈 카드는 빠지고 남은 카드끼리 붙는다
        self.clock_row = tk.Frame(grid, bg=PANEL)
        self.clock_row.grid(row=0, column=0, columnspan=6)
        self.bind_drag(self.clock_row)
        saved = st.get("clock_cards")
        self.clock_on = {k: (k in saved) if isinstance(saved, list) else True for k in CLOCK_KEYS}
        self.clock_vars = {}
        for i, key in enumerate(CLOCK_KEYS):
            c = self.make_tile(self.clock_row, 0, i)
            label = CLOCK_LABEL[key]
            c.create_text(TILE // 2, 47, text=label, fill=GREEN, font=(FONT, 7, "bold"))
            if key == "ss":
                c.itemconfigure("edge", fill="#f0fdf4", outline="#bbf7d0")
            if HAVE_FLIP:
                num = None
                self.cards[key] = FlipCard(c, TILE // 2, 24, "#f0fdf4" if key == "ss" else TILE_BG,
                                           GREEN if key == "ss" else WHITE,
                                           top="#dcfce7" if key == "ss" else None, bottom="#c7f0d5" if key == "ss" else None,
                                           line="#9fd8b4" if key == "ss" else None)
            else:
                num = c.create_text(TILE // 2, 26, text="--", fill=GREEN if key == "ss" else WHITE, font=(FONT, 18, "bold"))
            self.clock[key] = (c, num)
            self.clock_vars[key] = tk.BooleanVar(value=self.clock_on[key])
        # 아랫줄: 단추 4 + 결재대기 칸 + 기관접수대기 칸 (투명도는 ⚙ 메뉴)
        for i, (kind, icon, label) in enumerate(BUTTONS):
            c = self.make_tile(grid, 1, i, hand=True)
            acc, badge, tint = ACCENT[kind]
            c.create_oval(TILE // 2 - 14, 7, TILE // 2 + 14, 35, fill=badge, outline="")
            c.create_text(TILE // 2, 21, text=icon, fill=acc, font=("Segoe UI Emoji", 14))
            c.create_text(TILE // 2, 46, text=label, fill=WHITE, font=(FONT, 8, "bold"))
            c.bind("<Button-1>", lambda e, k=kind: self.click(k))
            c.bind("<Enter>", lambda e, w=c, a=acc, tt=tint: w.itemconfigure("edge", outline=a, fill=tt))
            c.bind("<Leave>", lambda e, w=c: w.itemconfigure("edge", outline=EDGE, fill=TILE_BG))
        sc = self.make_tile(grid, 1, 4, hand=True)
        self.sanctn_cv = sc
        self.sanctn_num = sc.create_text(TILE // 2, 17, text="--", fill="#9ca3af", font=(FONT, 17, "bold"))
        self.sanctn_lab = sc.create_text(TILE // 2, 44, text="에듀파인\n결재대기", fill=WHITE, font=(FONT, 8, "bold"), justify="center")
        sc.bind("<Button-1>", lambda e: self.refresh_sanctn(manual=True))
        sc.bind("<Enter>", lambda e: sc.itemconfigure("edge", outline=GREEN, fill="#f0fdf4"))
        sc.bind("<Leave>", lambda e: sc.itemconfigure("edge", outline=EDGE, fill=TILE_BG))
        self.sanctn_busy = False
        # 기관접수대기 칸 — 숫자는 30분마다 읽고(check_jeopsu.py), 누르면 그 화면을 연다(open_jeopsu.py)
        jc = self.make_tile(grid, 1, 5, hand=True)
        self.jeopsu_cv = jc
        self.jeopsu_num = jc.create_text(TILE // 2, 17, text="--", fill="#9ca3af", font=(FONT, 17, "bold"))
        jc.create_text(TILE // 2, 44, text="교데통\n기관접수", fill=WHITE, font=(FONT, 8, "bold"), justify="center")
        jc.bind("<Button-1>", lambda e: self.click("jeopsu"))
        jc.bind("<Enter>", lambda e: jc.itemconfigure("edge", outline="#0891b2", fill="#ecfeff"))
        jc.bind("<Leave>", lambda e: jc.itemconfigure("edge", outline=EDGE, fill=TILE_BG))
        self.jeopsu_busy = False
        self.opa_var = tk.IntVar(value=int(round(self.opacity * 10) * 10))

        self.status = tk.Label(self.root, text="", bg=PANEL, fg="#dc2626", font=(FONT, 8), anchor="w")
        self.status.pack(fill="x", padx=PAD + 2, pady=(6, 0))
        for w in (self.root, self.bgc, bar, self.title_lb, grid, self.status):
            self.bind_drag(w)

        self.mini = None
        self.auto_var = tk.BooleanVar(value=self.autostart_on())
        self.auto_cache = self.auto_var.get()
        self.tray = Tray(HERE0 / "업무위젯.ico", "업무위젯 (누르면 열려요)", lambda: self.auto_cache)
        self.m = tk.Menu(self.root, tearoff=0, font=(FONT, 10))
        self.m.add_command(label="환경설정 (지역·인증서·암호)", command=self.open_setup)
        self.m.add_checkbutton(label="윈도우 시작할 때 자동 실행", variable=self.auto_var, command=self.toggle_autostart)
        cm = tk.Menu(self.m, tearoff=0, font=(FONT, 10))
        for key in CLOCK_KEYS:
            cm.add_checkbutton(label=CLOCK_LABEL[key], variable=self.clock_vars[key], command=self.apply_clock)
        cm.add_separator()
        cm.add_command(label="모두 켜기", command=lambda: self.set_all_clock(True))
        cm.add_command(label="모두 끄기 (위젯이 작아져요)", command=lambda: self.set_all_clock(False))
        self.m.add_cascade(label="시계 카드 보이기", menu=cm)
        om = tk.Menu(self.m, tearoff=0, font=(FONT, 10))
        for pct in range(100, 20, -10):
            om.add_radiobutton(label="%d%%" % pct + ("  (흐리게)" if pct == 30 else ""), value=pct, variable=self.opa_var,
                               command=lambda: self.on_opacity(self.opa_var.get()))
        self.m.add_cascade(label="투명도", menu=om)
        self.m.add_command(label="업데이트 확인 (지금 v%s)" % (UPD.local_version(KIT) if UPD else "?"),
                           command=lambda: self.check_update(manual=True))
        self.upd_busy = False
        self.m.add_separator()
        self.m.add_command(label="시스템 트레이로 내리기", command=self.minimize)
        self.m.add_command(label="위젯 완전 종료", command=self.quit)
        self.root.bind("<Button-3>", lambda e: self.popup(e.x_root, e.y_root))
        self.apply_clock(save=False)

    # ── 시계 카드 켜기·끄기 (모두 끄면 윗줄이 빠지고 위젯 높이가 줄어든다) ──
    def set_all_clock(self, on):
        for v in self.clock_vars.values():
            v.set(on)
        self.apply_clock()

    def apply_clock(self, save=True):
        on = [k for k in CLOCK_KEYS if self.clock_vars[k].get()]
        for k in CLOCK_KEYS:
            cv = self.clock[k][0]
            if k in on:
                cv.grid()
            else:
                cv.grid_remove()
        if on:
            self.clock_row.grid()
        else:
            self.clock_row.grid_remove()
        h = SIZE_H if on else SIZE_H - (TILE + GAP)
        self.root.geometry("%dx%d" % (SIZE_W, h))
        self.bgc.configure(height=h)
        self.bgc.delete("all")
        round_rect(self.bgc, 1, 1, SIZE_W - 2, h - 2, 20, fill=PANEL, outline="#d9dee7", width=1)
        if save:
            try:
                K.save_state(clock_cards=on)
            except Exception:
                pass
            self.keep_visible()

    # ── 타일 ──
    def make_tile(self, parent, r, c, hand=False):
        cv = tk.Canvas(parent, width=TILE, height=TILE, bg=PANEL, highlightthickness=0, cursor="hand2" if hand else "")
        cv.grid(row=r, column=c, padx=GAP // 2, pady=GAP // 2)
        round_rect(cv, 2, 2, TILE - 2, TILE - 2, 13, fill=TILE_BG, outline=EDGE, width=1, tags="edge")
        if not hand:
            self.bind_drag(cv)
        self.tiles.append(cv)
        return cv

    # ── 끌기·위치 기억 ──
    def bind_drag(self, w):
        w.bind("<ButtonPress-1>", self.press, add="+")
        w.bind("<B1-Motion>", self.drag, add="+")
        w.bind("<ButtonRelease-1>", self.release, add="+")

    def press(self, e):
        self.dragging = True
        self.sx, self.sy = e.x_root, e.y_root
        self.wx, self.wy = self.root.winfo_x(), self.root.winfo_y()

    def drag(self, e):
        if self.dragging:
            self.root.geometry("+%d+%d" % (self.wx + e.x_root - self.sx, self.wy + e.y_root - self.sy))

    def release(self, e):
        if not self.dragging:
            return
        self.dragging = False
        self.keep_visible()
        self.save_pos()

    def save_pos(self):
        try:
            K.save_state(x=self.root.winfo_x(), y=self.root.winfo_y())
        except Exception:
            pass

    # ── 투명도 ──
    def on_opacity(self, v):
        self.opacity = min(1.0, max(0.3, float(v) / 100))
        self.root.attributes("-alpha", self.opacity)
        if hasattr(self, "_opa_save"):
            self.root.after_cancel(self._opa_save)
        self._opa_save = self.root.after(400, lambda: K.save_state(opacity=self.opacity))

    # ── 단추 ──
    def say(self, text, color="#dc2626"):
        self.status.configure(text=text, fg=color)

    def click(self, kind):
        if self.busy:
            self.say("지금 다른 작업이 진행 중입니다 (%s)" % self.busy, "#dc2626")
            return
        script, done, done_msg = JOBS[kind]
        if not (KIT / ".venv" / "Scripts" / "python.exe").exists() or not (KIT / script).exists():
            self.say("키트 파일을 찾지 못했습니다 (%s) — 업무위젯 설치를 다시 실행하세요" % script)
            return
        if not K.configured():
            self.say("먼저 오른쪽 클릭 → 인증서 설정", "#dc2626")
            return
        self.busy = "로그인 중"
        self.say("⏳ 로그인 중… (크롬 창이 뜹니다)", "#4b5563")
        threading.Thread(target=self.run_job, args=(script, done, done_msg), daemon=True).start()

    def run_job(self, script, done, done_msg):
        t0 = time.time()
        last = ""
        ok = False
        try:
            with self.lock:
                p = subprocess.Popen([str(K.PY), "-X", "utf8", str(KIT / script)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", env=K.ENV, cwd=str(KIT), creationflags=K.NO_WINDOW)
                tail = []
                for line in p.stdout:
                    line = line.strip()
                    tail.append(line)
                    if line.startswith("JEOPSU ") and line[7:].strip().isdigit():     # 기관접수대기 화면을 열며 읽은 건수
                        self.root.after(0, self.show_jeopsu, int(line[7:].strip()), "", False)
                    if done in line:
                        ok = True
                        self.root.after(0, self.say, done_msg, "#15803d")
                    elif line.startswith(("⏸", "❌")):
                        # 작은따옴표 안(인증서 이름 등)은 가린다
                        last = re.sub(r"'[^']*'", "'***'", re.sub(r"^[⏸❌]\s*", "", line))[:110]
                        self.root.after(0, self.say, "⚠️ " + last, "#dc2626")
                p.wait()
            if p.returncode != 0 and not ok:
                self.root.after(0, self.say, "❌ 열지 못했습니다: " + (last or "원인 출력 없음"), "#dc2626")
        except Exception as e:
            self.root.after(0, self.say, "❌ 실행하지 못했습니다: " + type(e).__name__, "#dc2626")
        finally:
            self.busy = None
            K.log_line("업무위젯 %s %.1fs %s" % (script, time.time() - t0, "ok" if ok else "FAIL " + last))

    # ── 에듀파인 결재대기 건수 (check_sanctn.py 가 업무포털 메인 숫자만 읽는다 · 30분마다 + 칸을 누르면 바로) ──
    def refresh_sanctn(self, manual=False):
        if self.sanctn_busy or self.busy:              # 로그인·화면 열기 작업 중에는 포털 탭을 새로고침하지 않는다
            if manual:
                self.say("다른 작업이 끝난 뒤 다시 눌러 주세요", "#dc2626")
            return
        script = KIT / "check_sanctn.py"
        if not (KIT / ".venv" / "Scripts" / "python.exe").exists() or not script.exists():
            if manual:
                self.say("키트에 check_sanctn.py 가 없습니다 — 업무위젯 설치를 다시 실행하세요")
            return
        if not K.configured():
            return
        self.sanctn_busy = True
        self.sanctn_cv.itemconfigure(self.sanctn_num, fill="#9ca3af")
        threading.Thread(target=self.run_sanctn, args=(script, manual), daemon=True).start()

    def run_sanctn(self, script, manual):
        reason, res = "", None
        try:
            p = subprocess.run([str(K.PY), "-X", "utf8", str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env=K.ENV, cwd=str(KIT), creationflags=K.NO_WINDOW, timeout=120)
            lines = [l.strip() for l in p.stdout.splitlines() if l.strip()]
            hit = next((l for l in lines if l.startswith("SANCTN ")), "")
            if p.returncode == 0 and hit:
                import json
                v = json.loads(hit[7:])
                res = (int(v["wait"]), int(v["urgent"]))
            else:
                bad = [l for l in lines if l.startswith("❌")]
                reason = re.sub(r"'[^']*'", "'***'", re.sub(r"^❌\s*", "", bad[-1] if bad else "원인 출력 없음"))[:100]
        except Exception as e:
            reason = "실행하지 못했습니다: " + type(e).__name__
        self.root.after(0, self.show_sanctn, res, reason, manual)

    def show_sanctn(self, res, reason, manual):
        self.sanctn_busy = False
        hm = datetime.now().strftime("%H:%M")
        if res:
            wait, urgent = res
            color = "#dc2626" if urgent else ("#d97706" if wait else GREEN)
            self.sanctn_cv.itemconfigure(self.sanctn_num, text=str(wait), fill=color)
            self.sanctn_cv.itemconfigure(self.sanctn_lab, text="에듀파인\n" + ("긴급 %d" % urgent if urgent else "결재대기"))
            if manual:
                self.say("✅ 결재대기 %d건 (%s)" % (wait, hm), "#15803d")
        else:
            self.sanctn_cv.itemconfigure(self.sanctn_num, text="--", fill="#9ca3af")
            self.sanctn_cv.itemconfigure(self.sanctn_lab, text="에듀파인\n결재대기")
            if manual:
                self.say("⚠️ " + reason, "#dc2626")

    def sanctn_loop(self):
        self.refresh_sanctn()
        self.root.after(SANCTN_EVERY_MS, self.sanctn_loop)

    # ── 교육행정데이터통합관리 기관접수대기 건수 (check_jeopsu.py 가 숫자만 읽는다 · 30분마다, 결재대기와 엇갈리게) ──
    def refresh_jeopsu(self):
        if self.jeopsu_busy or self.busy or self.sanctn_busy:     # 다른 작업 중이면 이번 차례는 건너뛴다
            return
        script = KIT / "check_jeopsu.py"
        if not (KIT / ".venv" / "Scripts" / "python.exe").exists() or not script.exists() or not K.configured():
            return
        self.jeopsu_busy = True
        self.jeopsu_cv.itemconfigure(self.jeopsu_num, fill="#9ca3af")
        threading.Thread(target=self.run_jeopsu, args=(script,), daemon=True).start()

    def run_jeopsu(self, script):
        reason, res = "", None
        try:
            p = subprocess.run([str(K.PY), "-X", "utf8", str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env=K.ENV, cwd=str(KIT), creationflags=K.NO_WINDOW, timeout=120)
            lines = [l.strip() for l in p.stdout.splitlines() if l.strip()]
            hit = next((l for l in lines if l.startswith("JEOPSU ")), "")
            if p.returncode == 0 and hit:
                import json
                res = int(json.loads(hit[7:])["wait"])
            else:
                bad = [l for l in lines if l.startswith("❌")]
                reason = re.sub(r"^❌\s*", "", bad[-1] if bad else "원인 출력 없음")[:100]
        except Exception as e:
            reason = "실행하지 못했습니다: " + type(e).__name__
        self.root.after(0, self.show_jeopsu, res, reason, True)

    def show_jeopsu(self, res, reason, from_check):
        if from_check:
            self.jeopsu_busy = False
        if res is not None:
            self.jeopsu_cv.itemconfigure(self.jeopsu_num, text=str(res), fill="#0891b2" if res else GREEN)
        elif from_check:
            self.jeopsu_cv.itemconfigure(self.jeopsu_num, text="--", fill="#9ca3af")
            K.log_line("업무위젯 기관접수대기 못 읽음: " + reason)

    # ── 자동 업데이트 (work_widget_update.py: 서명 확인 → 받기 → 덮어쓰기 → 위젯 다시 켜기) ──
    def check_update(self, manual=False):
        if UPD is None or self.upd_busy:
            if manual:
                self.say("업데이트 기능이 없는 버전이에요 — 설치 파일로 한 번 다시 설치해 주세요" if UPD is None else "업데이트 확인 중이에요")
            return
        self.upd_busy = True
        if manual:
            self.say("⏳ 새 버전 확인 중…", "#4b5563")

        def work():
            try:
                m = UPD.check(KIT)
                self.root.after(0, self.got_update, m, "", manual)
            except Exception as e:
                self.root.after(0, self.got_update, None, (str(e).splitlines() or [type(e).__name__])[0][:80], manual)
        threading.Thread(target=work, daemon=True).start()

    def got_update(self, m, err, manual):
        self.upd_busy = False
        if err:
            K.log_line("업무위젯 업데이트 확인 실패: " + err)
            if manual:
                self.say("⚠️ 업데이트 확인 실패: " + err)
            return
        if not m:
            if manual:
                self.say("✅ 최신 버전이에요 (v%s)" % UPD.local_version(KIT), "#15803d")
            return
        self.apply_update(m)

    def apply_update(self, m):
        if self.busy or self.sanctn_busy or self.jeopsu_busy:     # 로그인·화면 열기·건수 읽기 중이면 5분 뒤에
            self.root.after(5 * 60 * 1000, self.apply_update, m)
            return
        self.busy = "업데이트 중"
        self.upd_busy = True
        self.say("⏳ 새 버전(v%s)으로 바꾸는 중…" % m["version"], "#4b5563")

        def work():
            try:
                UPD.apply(KIT, m, lambda s: self.root.after(0, self.say, "⏳ " + s + "…", "#4b5563"))
                self.root.after(0, self.relaunch)
            except Exception as e:
                msg = (str(e).splitlines() or [type(e).__name__])[0][:80]
                K.log_line("업무위젯 업데이트 실패: " + msg)
                self.root.after(0, self.say, "⚠️ 업데이트 실패 (다음에 다시 해요): " + msg)
            finally:
                self.busy = None
                self.upd_busy = False
        threading.Thread(target=work, daemon=True).start()

    def relaunch(self):
        """새 파일로 위젯을 다시 켠다 — 이 위젯이 끝난 뒤(한 개만 뜨기 표시가 풀린 뒤) 3초쯤 있다가 뜬다."""
        pyw = K.PY.with_name("pythonw.exe")
        cmd = 'cmd /c ping -n 4 127.0.0.1 >nul & start "" "%s" "%s"' % (pyw, HERE0 / "바로가기위젯.pyw")
        base = 0x00000008 | 0x00000200
        try:
            subprocess.Popen(cmd, cwd=str(HERE0), creationflags=base | 0x01000000, close_fds=True)
        except OSError:
            subprocess.Popen(cmd, cwd=str(HERE0), creationflags=base, close_fds=True)
        self.quit()

    def update_loop(self):
        self.check_update()
        self.root.after(UPDATE_EVERY_MS, self.update_loop)

    def jeopsu_loop(self):
        self.refresh_jeopsu()
        self.root.after(SANCTN_EVERY_MS, self.jeopsu_loop)

    # ── 보이기·종료 ──
    def hwnd(self):
        try:
            return int(self.root.wm_frame(), 16)
        except Exception:
            return 0

    def keep_visible(self, raise_=False):
        if self.mini is not None:
            return
        try:
            self.root.update_idletasks()
            if self.root.state() != "normal":
                self.root.deiconify()
            x, y = self.root.winfo_x(), self.root.winfo_y()
            nx, ny = K.fit_on_screen(x, y, self.root.winfo_width(), self.root.winfo_height())
            if (nx, ny) != (x, y):
                self.root.geometry("+%d+%d" % (nx, ny))
            if raise_:
                self.root.attributes("-topmost", True)
                self.root.lift()
        except Exception as e:
            K.log_line("업무위젯 keep_visible 오류 %r" % e)

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.root.attributes("-topmost", self.pinned)
        self.pin_label.configure(fg="#4b5563" if self.pinned else "#b3bac4")

    def open_setup(self):
        subprocess.Popen([str(K.PY.with_name("pythonw.exe")), str(K.HERE / "바로가기_설정창.pyw")], cwd=str(K.HERE), env=K.ENV)
        self.say("설정 창에서 마쳐 주세요", "#4b5563")

    # ── 시스템 트레이로 내리기 / 되살리기 ──
    def minimize(self):
        """위젯을 숨기고 시스템 트레이(작업표시줄 오른쪽 아래)에 아이콘을 둔다. 아이콘을 누르면 되살아난다."""
        if self.mini is not None:
            return
        self.save_pos()
        if not self.tray.add():
            self.say("트레이 아이콘을 만들지 못했어요", "#dc2626")
            return
        self.mini = True
        self.root.withdraw()

    def restore(self):
        if self.mini is None:
            return
        self.mini = None
        self.tray.remove()
        self.root.deiconify()
        self.keep_visible(raise_=True)

    def drain_tray(self):
        try:
            while True:
                ev = self.tray.q.get_nowait()
                if ev == "show":
                    self.restore()
                elif ev == "auto":
                    self.auto_var.set(not self.auto_var.get())
                    self.toggle_autostart()
                elif ev == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        except Exception as e:
            K.log_line("업무위젯 트레이 오류 %r" % e)
        self.root.after(150, self.drain_tray)

    # ── 환경설정 메뉴 · 윈도우 시작 시 자동 실행 ──
    def popup(self, x, y):
        self.auto_var.set(self.autostart_on())
        self.auto_cache = self.auto_var.get()
        self.m.tk_popup(x, y)

    def show_options(self):
        self.popup(self.gear.winfo_rootx(), self.gear.winfo_rooty() + self.gear.winfo_height())

    # 바로가기 이름·아이콘 (이름은 «업무위젯», 예전 이름이 있으면 새 이름으로 바꿔 준다)
    LNK_NAME = "업무위젯.lnk"
    OLD_LNK = "나이스 에듀파인 바로가기.lnk"

    @staticmethod
    def special_folder(kind):
        """kind: 'Startup' | 'Desktop' — 윈도우가 실제로 쓰는 폴더(OneDrive로 옮겨진 바탕화면 포함)."""
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; [Environment]::GetFolderPath('%s')" % kind],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=0x08000000, timeout=15)
            d = r.stdout.strip()
        except Exception:
            d = ""
        if d:
            return Path(d)
        if kind == "Startup":
            return Path(K.os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return Path(K.os.environ["USERPROFILE"]) / "Desktop"

    def make_lnk(self, lnk):
        pyw = K.PY.with_name("pythonw.exe")
        target = HERE0 / "바로가기위젯.pyw"
        ico = HERE0 / "업무위젯.ico"
        icon = ico if ico.exists() else pyw
        ps = ('$s=(New-Object -ComObject WScript.Shell).CreateShortcut("%s"); $s.TargetPath="%s"; '
              "$s.Arguments='\"%s\"'; $s.WorkingDirectory=\"%s\"; $s.IconLocation=\"%s,0\"; $s.Description=\"업무위젯\"; $s.Save()"
              % (lnk, pyw, target, HERE0, icon))
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True, creationflags=0x08000000, timeout=20)

    def startup_lnk(self):
        return self.special_folder("Startup") / self.LNK_NAME

    def autostart_on(self):
        try:
            d = self.special_folder("Startup")
            return (d / self.LNK_NAME).exists() or (d / self.OLD_LNK).exists()
        except Exception:
            return False

    def migrate_shortcuts(self):
        """예전 이름(나이스 에듀파인 바로가기)의 바로가기를 «업무위젯» 이름·새 아이콘으로 바꾼다 (한 번이면 충분, 실패해도 무시)."""
        try:
            for kind in ("Desktop", "Startup"):
                d = self.special_folder(kind)
                old = d / self.OLD_LNK
                if old.exists():
                    self.make_lnk(d / self.LNK_NAME)
                    old.unlink(missing_ok=True)
        except Exception as e:
            K.log_line("업무위젯 바로가기 이름 바꾸기 오류 %r" % e)

    def toggle_autostart(self):
        try:
            d = self.special_folder("Startup")
            if self.auto_var.get():
                self.make_lnk(d / self.LNK_NAME)
                (d / self.OLD_LNK).unlink(missing_ok=True)
                self.say("윈도우를 켜면 위젯이 자동으로 떠요", "#15803d")
            else:
                (d / self.LNK_NAME).unlink(missing_ok=True)
                (d / self.OLD_LNK).unlink(missing_ok=True)
                self.say("자동 실행을 껐어요", "#4b5563")
        except Exception as e:
            K.log_line("업무위젯 자동실행 설정 오류 %r" % e)
            self.auto_var.set(self.autostart_on())
            self.say("자동 실행을 바꾸지 못했어요", "#dc2626")
        self.auto_cache = self.auto_var.get()

    def quit(self):
        self.save_pos()
        try:
            self.tray.remove()
        except Exception:
            pass
        self.root.destroy()

    def tick(self):
        self.root.after(1000 - datetime.now().microsecond // 1000, self.tick)
        d = datetime.now()
        vals = {"mo": "%02d" % d.month, "dd": "%02d" % d.day, "wk": "월화수목금토일"[d.weekday()],
                "hh": "%02d" % d.hour, "mi": "%02d" % d.minute, "ss": "%02d" % d.second}
        for key, (cv, item) in self.clock.items():
            if key in self.cards:
                self.cards[key].flip(vals[key])
            else:
                cv.itemconfigure(item, text=vals[key])

    def poll(self):
        """바로가기를 또 눌렀는지(앞으로 나오기) · 2초마다 화면 밖·숨김 확인."""
        k = K.ctypes.windll.kernel32
        if self.ev_show and k.WaitForSingleObject(K.wt.HANDLE(self.ev_show), 0) == 0:
            self.restore()
            self.keep_visible(raise_=True)
            self.say("여기 있어요!", "#15803d")
            k.SetEvent(K.wt.HANDLE(self.ev_ack))
        self.ticks += 1
        if self.ticks % K.GUARD_EVERY == 0 and not self.dragging:
            self.keep_visible()
        self.root.after(400, self.poll)

    def mainloop(self):
        threading.Thread(target=self.migrate_shortcuts, daemon=True).start()
        self.drain_tray()
        self.root.after(200, self.keep_visible)
        self.tick()
        self.poll()
        self.root.after(4000, self.sanctn_loop)
        self.root.after(70_000, self.jeopsu_loop)           # 결재대기 읽기와 겹치지 않게 1분쯤 늦게
        if UPD is not None:
            self.root.after(120_000, self.update_loop)
            v = UPD.just_updated(KIT)
            if v:
                self.root.after(1500, lambda: self.say("✨ 새 버전(v%s)으로 바뀌었어요" % v, "#15803d"))
        if not K.configured():
            self.root.after(800, lambda: self.say("오른쪽 클릭 → 인증서 설정부터 해 주세요", "#dc2626"))
        self.root.mainloop()


def breakaway():
    """클로드(코드 화면)가 띄운 명령은 «잡(job)»으로 묶여 클로드가 끝나면 같이 죽는다 → 잡 밖으로 이 «업무위젯 파일»을 다시 띄우고 끝낸다.
    (원본의 breakaway 는 원본 파일을 다시 띄우므로 쓰지 않는다)"""
    if "--unjobbed" in sys.argv:
        return False
    try:
        k = K.ctypes.windll.kernel32
        injob = K.ctypes.c_int(0)
        if not k.IsProcessInJob(k.GetCurrentProcess(), None, K.ctypes.byref(injob)) or not injob.value:
            return False
        flags = 0x01000000 | 0x00000008 | 0x00000200          # CREATE_BREAKAWAY_FROM_JOB | DETACHED | NEW_PROCESS_GROUP
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--unjobbed"], cwd=str(HERE0), creationflags=flags,
                         close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    if breakaway():
        sys.exit(0)
    if K.single_instance():      # 이미 떠 있다 → 그 위젯을 앞으로 꺼내고 나는 끝
        sys.exit(0)
    Widget().mainloop()
