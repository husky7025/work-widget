# -*- coding: utf-8 -*-
"""업무 위젯 — 시계 · 업무포털 · 나이스 ▾ · 에듀파인 ▾ · DJE Talk 단추 + 에듀파인 결재대기·통합관리 기관접수대기 건수 타일 (⚙ 에서 투명도·시계 카드, 마지막 위치 기억).

키트의 «바로가기위젯.pyw» 를 이 파일로 바꿔 끼워 쓴다 (설치 파일이 원본을 «바로가기위젯_원본.pyw» 로 보관한다).
한 개만 뜨기·바탕화면/시작프로그램 바로가기·설정 창의 «위젯 켜기»·화면 밖 되돌리기는 원본의 것을 그대로 가져다 쓴다.

단추는 키트 폴더의 open_portal.py · open_neis.py · open_gian.py · open_pumui.py 를 돌리고, 결재대기 칸은 check_sanctn.py(읽기만)를 30분마다 돌린다.
  업무포털 — 인증서 로그인 후 업무포털 메인 화면까지
  나이스   — 인증서 로그인 후 나이스 화면까지
  내부기안 — 에듀파인 공용서식 «표준 서식(결재4인,협조4인)» 빈 기안 창
  품의등록 — 에듀파인 학교회계 > 사업담당 > 품의/정산 > 품의등록 빈 화면
  «▾» 단추(나이스·에듀파인)는 누르면 칸 한 줄을 아래로(화면 아래가 모자라면 위로) 펼친다 — SUBMENUS 참고.
  펼친 칸의 하위 메뉴는 work_widget_menu.py 가 연다 (나이스: 메뉴 글자를 차례로 누름 / 에듀파인: 메뉴ID 로 gfnOpenMenu).
모두 신청·저장·결재·상신은 하지 않는다. 인증서 암호는 이 파일이 다루지 않는다 (키트가 자격 증명 관리자에서 읽는다).
"""
import contextlib
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
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
UPDATE_HOUR = 12                         # 새 버전 확인: 위젯을 켤 때(2분쯤 뒤) 한 번 + 매일 정오에 한 번 (정오에 꺼져 있었으면 켤 때 확인으로 대신)
UPDATE_POLL_MS = 5 * 60 * 1000           # 정오가 됐는지 5분마다 본다 (절전에서 깨어나도 놓치지 않게)
import ctypes as _c0


def _screen_dpi():
    """윈도우 «화면 배율» 인식을 켜서(안 켜면 윈도우가 흐릿하게 늘려 그린다) 지금 배율을 돌려준다 (1.0 = 100%, 1.5 = 150%). 못 켜면 1.0."""
    try:
        try:
            _c0.windll.shcore.SetProcessDpiAwareness(1)           # 시스템 DPI 인식 — 이미 정해져 있어 실패해도 괜찮다
        except Exception:
            _c0.windll.user32.SetProcessDPIAware()
        aw = _c0.c_int(-1)
        if _c0.windll.shcore.GetProcessDpiAwareness(None, _c0.byref(aw)) != 0 or aw.value < 1:
            return 1.0                                                 # 인식이 안 켜졌으면 윈도우가 알아서 늘리니 우리는 그대로
        return max(1.0, _c0.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:
        return 1.0


SIZE_CHOICES = ((85, "작게 (85%)"), (100, "보통 (100%)"), (120, "크게 (120%)"))
try:
    UI_PCT = int(K.load_state().get("ui_scale", 100))
except Exception:
    UI_PCT = 100
if UI_PCT not in [c[0] for c in SIZE_CHOICES]:
    UI_PCT = 100
DPI = _screen_dpi()
SC = DPI * UI_PCT / 100.0              # 그림 크기 배율 (글자는 윈도우가 화면 배율을 따로 곱해 주므로 UI_PCT 만)


def px(n):
    return int(round(n * SC))


SIZE_W, SIZE_H = px(424), px(190)
TILE, GAP, PAD = px(60), px(6), px(12)
PANEL, TILE_BG, EDGE, GREEN, WHITE = "#f2f0eb", "#ffffff", "#e4e0d8", "#00754A", "#212121"   # 스타벅스 톤: 크림 판 / 타일 / 테두리 / 그린 / 글자
FONT = "Malgun Gothic"
# 페이퍼로지 글꼴 — 위젯 폴더의 ttf 를 이 프로그램에서만 쓰게 올린다 (PC에 설치 안 해도 됨 · 실패하면 맑은 고딕)
_PL = {"r": HERE0 / "Paperlogy-4Regular.ttf", "b": HERE0 / "Paperlogy-7Bold.ttf"}
try:
    import ctypes as _ct
    _ok = all(p.exists() and _ct.windll.gdi32.AddFontResourceExW(str(p), 0x10, 0) > 0 for p in _PL.values())
except Exception:
    _ok = False
FONT_R, FONT_B = ("Paperlogy 4 Regular", "Paperlogy 7 Bold") if _ok else (FONT, FONT)


def FS(size):
    return max(6, int(round(size * UI_PCT / 100.0)))


def F(size, bold=False):
    size = FS(size)
    return (FONT_B, size) if (bold and _ok) else ((FONT_R, size, "bold") if bold else (FONT_R, size))


def fit_font(text, max_w, size=8, bold=True, smallest=6):
    """칸 안에 들어가도록 글자 크기를 줄인다 (가장 긴 줄 기준). 그래도 넘치면 가장 작은 크기."""
    lines = str(text).split("\n")
    for s in range(size, smallest - 1, -1):
        f = tkfont.Font(font=F(s, bold))
        if max(f.measure(t) for t in lines) <= max_w:
            return F(s, bold)
    return F(smallest, bold)


KEY = "#010203"        # 이 색은 투명하게 빠진다 (둥근 모서리용)
ACCENT = {"portal": ("#00754A", "#d4e9e2", "#eef6f2"), "neis": ("#006241", "#d4e9e2", "#eef6f2"),
          "gian": ("#1E3932", "#d4e9e2", "#eef6f2"), "pumui": ("#2b5148", "#d4e9e2", "#eef6f2"),
          "dje": ("#2b5148", "#d4e9e2", "#eef6f2"), "edu": ("#1E3932", "#d4e9e2", "#eef6f2")}      # (강조색, 아이콘 배경, 눌렀을 때 타일 바탕)

JOBS = {
    "portal": ("open_portal.py", "업무포털 메인 화면을 열었습니다", "✅ 업무포털 메인 화면을 열었습니다"),
    "neis":   ("open_neis.py", "나이스 화면을 열었습니다", "✅ 나이스 화면을 열었습니다 (로그인됨)"),
    "gian":   ("open_gian.py", "내부기안 창을 열었습니다", "✅ 내부기안 창을 열었습니다 (작성·저장·상신은 안 함)"),
    "pumui":  ("open_pumui.py", "품의등록 화면을 열었습니다", "✅ 품의등록 화면을 열었습니다 (입력·저장·결재요청은 안 함)"),
    "jeopsu": ("open_jeopsu.py", "기관접수대기 화면을 열었습니다", "✅ 기관접수대기 화면을 열었습니다 (접수·제출은 안 함)"),
    "sanctn": ("open_sanctn.py", "결재대기함을 열었습니다", "✅ 결재대기함을 열었습니다 (결재·반려는 안 함)"),
    "dje":    ("open_dje.py", "DJE 메신저에 로그인했습니다", "✅ DJE 메신저에 로그인했습니다"),
}
BUTTONS = [("portal", "🏫", "1. 업무포털"), ("neis", "🗂", "2. 나이스"), ("edu", "📁", "3. 에듀파인"), ("dje", "💬", "4. DJE Talk")]
BUTTON_NOT_DJE = ("gian", "📝", "4. 내부기안")      # DJE Talk 는 대전교육청 메신저 — 지역이 대전이 아니면 4번 칸은 내부기안
# «▾» 단추를 누르면 위젯 아래(화면 아래가 모자라면 위)로 펼쳐지는 칸들 — (칸 글자, 상태 줄 이름, 할 일)
# 할 일: JOBS 의 열쇠(문자열) 또는 ("neis", [[메뉴, 단계]…]) / ("edufine", 에듀파인 메뉴ID) — work_widget_menu.py 가 연다
SUBMENUS = {
    "neis": [("나이스\n첫 화면", "나이스", "neis"),
             ("개인근무\n상황관리", "개인근무상황관리", ("neis", [["복무", 0], ["개인근무상황관리", 1]])),
             ("개인초과\n근무관리", "개인초과근무관리", ("neis", [["복무", 0], ["개인초과근무관리", 1]]))],
    "edu": [("내부기안", "내부기안", "gian"),
            ("품의등록", "품의등록", "pumui"),
            ("기안한\n문서", "기안한문서", ("edufine", "A00AAB0106001")),
            ("문서등록\n대장", "문서등록대장", ("edufine", "A00AAB0107001")),
            ("품의목록", "품의목록", ("edufine", "A00FAA0104001002")),
            ("사업관리\n카드(담당)", "사업관리카드(담당)", ("edufine", "A00FAA0101001"))],
}
SUB_COLS = 6
CREDIT = "만든 사람 · 대전동산고 J.S."           # 제목에 마우스를 올렸을 때만 보인다
SUB_MAX = 12                     # 펼침 칸은 두 줄(12칸)까지
SUB_IDLE_S = 10                  # 펼친 채 마우스가 위젯 밖에 이만큼 있으면 저절로 접는다
SUB_BUILTIN = {"neis": [("나이스 첫 화면", "neis")], "edu": [("내부기안", "gian"), ("품의등록", "pumui")]}   # 메뉴를 안 읽어도 고를 수 있는 것
MENUS_FILE_NAME = "work_widget_menus.json"   # work_widget_menu.py read 가 적는 «내 메뉴» 목록 (키트 폴더)


def sub_defaults():
    return {k: [{"name": n, "text": t, "job": j} for t, n, j in v] for k, v in SUBMENUS.items()}


def sub_text(name):
    """칸에 쓸 글자 (세 줄까지). 띄어쓰기가 있으면 낱말을 5글자 안쪽으로 묶고, 없으면 4글자씩 끊는다.
    끝에 붙은 (괄호)는 끝줄에 붙이거나 한 줄로 둔다. 세 줄이 넘으면 «…» 로 줄인다."""
    name = str(name).strip()

    def chunks(t):
        n = len(t)
        return [t] if n <= 4 else [t[:3], t[3:]] if n == 5 else [t[i:i + 4] for i in range(0, n, 4)]

    if " " in name:
        lines, cur = [], ""
        for wd in name.split():
            if cur and len(cur) + 1 + len(wd) > 5:
                lines.append(cur)
                cur = wd
            else:
                cur = (cur + " " + wd).strip()
        lines.append(cur)
    elif name.endswith(")") and "(" in name[1:]:
        i = name.index("(", 1)
        lines, paren = chunks(name[:i]), name[i:]
        if len(lines[-1]) + len(paren) <= 6:
            lines[-1] += paren
        else:
            lines.append(paren)
    else:
        lines = chunks(name)
    if len(lines) > 3:
        lines = lines[:3]
        lines[2] = lines[2][:3] + "…"
    return "\n".join(lines)


def sub_job_ok(job):
    if isinstance(job, str):
        return job in ("neis", "gian", "pumui")
    if not (isinstance(job, (list, tuple)) and len(job) == 2):
        return False
    site, target = job
    if site == "edufine":
        return isinstance(target, str) and bool(re.fullmatch(r"[A-Z0-9]{4,20}", target))
    if site == "neis":
        return (isinstance(target, list) and 0 < len(target) <= 4
                and all(isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], int) for x in target))
    return False


def sub_load(st):
    """저장된 펼침 메뉴 — 이상한 값은 버리고, 없으면 기본값."""
    out = sub_defaults()
    saved = st.get("submenus")
    if isinstance(saved, dict):
        for k in ("neis", "edu"):
            v = saved.get(k)
            if isinstance(v, list):
                items = [x for x in v if isinstance(x, dict) and isinstance(x.get("name"), str) and sub_job_ok(x.get("job"))]
                out[k] = items[:SUB_MAX]
    return out
CLOCK_KEYS = ("mo", "dd", "wk", "hh", "mi", "ss")
CLOCK_LABEL = {"mo": "월", "dd": "일", "wk": "요일", "hh": "시", "mi": "분", "ss": "초"}
SANCTN_EVERY_MS =30 * 60 * 1000        # 에듀파인 결재대기 건수를 30분마다 읽는다 (읽기만 함)


def is_daejeon():
    """환경설정의 지역이 대전이면 True. 지역이 아직 없으면 대전(기본값)으로 본다."""
    try:
        url = (K.cfg() or {}).get("neis_url") or ""
    except Exception:
        url = ""
    return (not url) or "//dje." in url


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

    def balloon(self, title, text, warn=False):
        """트레이 풍선 알림(윈도우 알림). 아이콘이 없으면 잠깐 달고 True 를 돌려준다(→ 부른 쪽이 나중에 떼어 준다)."""
        if not self.hwnd:
            return False
        temp = not self.added
        if temp and not self.add():
            return False
        nid = self._data()
        nid.uFlags |= 0x10                                  # NIF_INFO
        nid.szInfoTitle = title[:60]
        nid.szInfo = text[:250]
        nid.dwInfoFlags = 0x2 if warn else 0x1              # NIIF_WARNING / NIIF_INFO
        _shell32.Shell_NotifyIconW(1, ctypes.byref(nid))    # NIM_MODIFY
        return temp

    def remove(self):
        if self.hwnd and self.added:
            _shell32.Shell_NotifyIconW(2, ctypes.byref(self._data()))                     # NIM_DELETE
            self.added = False

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == self.CB:
                ev = lparam & 0xFFFF
                if ev in (0x202, 0x203, 0x405):   # 왼쪽 단추 뗌 / 더블클릭 / 알림 풍선을 누름 → 열기
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
    _FLIP_FONT = str(_PL["b"]) if _ok else r"C:\Windows\Fonts\malgunbd.ttf"
    ImageFont.truetype(_FLIP_FONT, 10)
    HAVE_FLIP = True
except Exception:
    HAVE_FLIP = False


class FlipCard:
    """숫자 카드. 값이 바뀌면 윗조각이 접혀 내려오고 아랫조각이 펼쳐지는 모양으로 넘어간다."""
    W, H, SS = px(46), px(32), 4
    TOP, BOTTOM, LINE = "#faf8f4", "#efece5", "#d6d1c6"
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
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=px(7) * S, fill=255)
        card = Image.new("RGB", (W, H), self.bg)
        card.paste(base, (0, 0), mask)
        d = ImageDraw.Draw(card)
        d.text((W // 2, H // 2), text, font=ImageFont.truetype(_FLIP_FONT, px(21) * S), fill=self.color, anchor="mm")
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
        self.notify_on = bool(st.get("notify_sanctn", True))      # 결재대기가 새로 오면 윈도우 알림
        self.dje_auto = bool(st.get("dje_autostart", False))      # 위젯을 켤 때 DJE 메신저에 자동 로그인 (기본 꺼짐)
        self.sanctn_last = st.get("sanctn_last")                  # 마지막으로 읽은 [결재대기, 긴급] — 껐다 켜도 같은 건으로 또 알리지 않게
        self.pinned = bool(st.get("pinned", True))              # 📍 항상 위 — 껐으면 다음에도 꺼진 채로
        self.root.attributes("-topmost", self.pinned)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)
        self.opacity = min(1.0, max(0.3, float(st.get("opacity", 1.0))))
        self.root.attributes("-alpha", self.opacity)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = K.fit_on_screen(int(st.get("x", sw - SIZE_W - 40)), int(st.get("y", 40)), SIZE_W, SIZE_H)
        self.root.geometry("%dx%d+%d+%d" % (SIZE_W, SIZE_H, x, y))
        self.bgc = tk.Canvas(self.root, width=SIZE_W, height=SIZE_H, bg=KEY, highlightthickness=0)
        self.bgc.place(x=0, y=0)
        round_rect(self.bgc, 1, 1, SIZE_W - 2, SIZE_H - 2, px(16), fill=PANEL, outline="#d6d1c6", width=1)
        tk.Misc.lower(self.bgc)
        self.busy = None
        self.dje_busy = False                 # DJE 메신저 로그인 중 (크롬을 안 쓰므로 self.busy 와 따로 센다)
        self.lock = threading.Lock()
        self.dragging = False
        self.ticks = 0
        self.root.report_callback_exception = lambda *a: K.log_line("ERROR  " + " ".join(str(v) for v in a[:2]))
        k = K._kernel32()
        self.ev_show = k.CreateEventW(None, False, False, K.SHOW_EVENT)      # 바로가기를 또 누르면 «앞으로 나와»
        self.ev_ack = k.CreateEventW(None, False, False, K.ACK_EVENT)

        # 위쪽 줄: 📍(항상 위) ⚙(환경설정) ✕(닫기)
        bar = tk.Frame(self.root, bg=PANEL)
        bar.pack(fill="x", padx=PAD - px(4), pady=(px(8), 0))
        self.title_lb = tk.Label(bar, text="업무위젯", bg=PANEL, fg="#6b6b6b", font=F(9, True))
        self.title_lb.pack(side="left", padx=(px(10), 0))
        self.tip = None                       # 제목에 마우스를 올리면 만든 사람이 작게 뜬다
        self.title_lb.bind("<Enter>", lambda e: self.show_tip(), add="+")
        self.title_lb.bind("<Leave>", lambda e: self.hide_tip(), add="+")
        for text, cmd, tip in (("✕", self.minimize, "시스템 트레이로 내리기 (완전 종료: 톱니바퀴 → 위젯 완전 종료)"),
                               ("⚙", self.show_options, "환경설정"),
                               ("📍", self.toggle_pin, "항상 위 켜기/끄기")):
            b = tk.Label(bar, text=text, bg=PANEL, fg="#5c5c5c", font=F(10), cursor="hand2", padx=px(5))
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            if text == "📍":
                self.pin_label = b
            if text == "⚙":
                self.gear = b
        self.pin_label.configure(fg="#5c5c5c" if self.pinned else "#b5b0a5")

        self.bar = bar
        grid = tk.Frame(self.root, bg=PANEL)
        grid.pack(padx=PAD, pady=(px(2), 0))
        self.grid = grid
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
            c.create_text(TILE // 2, px(47), text=label, fill=GREEN, font=F(7, True))
            if key == "ss":
                c.itemconfigure("edge", fill="#eef6f2", outline="#a9cdbf")
            if HAVE_FLIP:
                num = None
                self.cards[key] = FlipCard(c, TILE // 2, px(24), "#eef6f2" if key == "ss" else TILE_BG,
                                           GREEN if key == "ss" else WHITE,
                                           top="#e3f0ea" if key == "ss" else None, bottom="#d4e9e2" if key == "ss" else None,
                                           line="#a9cdbf" if key == "ss" else None)
            else:
                num = c.create_text(TILE // 2, px(26), text="--", fill=GREEN if key == "ss" else WHITE, font=F(18, True))
            self.clock[key] = (c, num)
            self.clock_vars[key] = tk.BooleanVar(value=self.clock_on[key])
        # 아랫줄: 단추 4 + 결재대기 칸 + 기관접수대기 칸 (투명도는 ⚙ 메뉴)
        self.sub_tiles = {}          # 펼침 단추(나이스 ▾ · 에듀파인 ▾)의 칸
        self.sub_open = None         # 지금 펼친 단추 (없으면 None)
        self.sub_frame = None
        self.sub_extra = 0           # 펼쳐서 늘어난 높이
        self.sub_up = False          # 위로 펼쳤나 (그만큼 위젯을 위로 올렸다)
        self.base_h = SIZE_H
        self.submenus = sub_load(st)
        self.sub_idle = 0
        self.picker = None
        buttons = BUTTONS if is_daejeon() else [b if b[0] != "dje" else BUTTON_NOT_DJE for b in BUTTONS]
        lab_font = min((fit_font(b[2], TILE - px(8)) for b in buttons), key=lambda f: f[1])   # 네 칸 모두 같은 크기로
        for i, (kind, icon, label) in enumerate(buttons):
            c = self.make_tile(grid, 2, i, hand=True)
            acc, badge, tint = ACCENT[kind]
            c.create_oval(TILE // 2 - px(14), px(7), TILE // 2 + px(14), px(35), fill=badge, outline="")
            c.create_text(TILE // 2, px(21), text=icon, fill=acc, font=("Segoe UI Emoji", FS(14)))
            c.create_text(TILE // 2, px(46), text=label, fill=WHITE, font=lab_font, anchor="center")
            if kind in SUBMENUS:                  # 펼침 단추 표시: 오른쪽 위 작은 화살표 (펼치면 위로 뒤집힌다)
                c.create_polygon(self.chev_pts(False), fill=acc, outline="", tags="chev")
                c.bind("<Button-1>", lambda e, k=kind: self.toggle_sub(k))
                self.sub_tiles[kind] = c
            else:
                c.bind("<Button-1>", lambda e, k=kind: self.click(k))
            c.bind("<Enter>", lambda e, w=c, a=acc, tt=tint: w.itemconfigure("edge", outline=a, fill=tt))
            c.bind("<Leave>", lambda e, w=c, k=kind: self.sub_open != k and w.itemconfigure("edge", outline=EDGE, fill=TILE_BG))
        sc = self.make_tile(grid, 2, 4, hand=True)
        self.sanctn_cv = sc
        self.sanctn_num = sc.create_text(TILE // 2, px(17), text="--", fill="#a8a49b", font=F(17, True))
        self.sanctn_lab = sc.create_text(TILE // 2, px(44), text="에듀파인\n결재대기", fill=WHITE, font=F(8, True), justify="center")
        sc.bind("<Button-1>", lambda e: self.click("sanctn"))                 # 눌러서 결재대기함 열기
        sc.bind("<Button-3>", lambda e: (self.refresh_sanctn(manual=True), "break")[1])   # 오른쪽 클릭 = 숫자만 새로고침
        self.sanctn_look = (TILE_BG, EDGE, 1, False)           # (바탕, 테두리, 테두리 굵기, 알림 중?) — 결재대기가 있으면 눈에 띄게 바뀐다
        sc.bind("<Enter>", lambda e: self.paint_sanctn(hover=True))
        sc.bind("<Leave>", lambda e: self.paint_sanctn())
        self.sanctn_busy = False
        # 기관접수대기 칸 — 숫자는 30분마다 읽고(check_jeopsu.py), 누르면 그 화면을 연다(open_jeopsu.py)
        jc = self.make_tile(grid, 2, 5, hand=True)
        self.jeopsu_cv = jc
        self.jeopsu_num = jc.create_text(TILE // 2, px(17), text="--", fill="#a8a49b", font=F(17, True))
        jc.create_text(TILE // 2, px(44), text="교데통\n기관접수", fill=WHITE, font=F(8, True), justify="center")
        jc.bind("<Button-1>", lambda e: self.click("jeopsu"))
        jc.bind("<Enter>", lambda e: jc.itemconfigure("edge", outline="#2b5148", fill="#eef6f2"))
        jc.bind("<Leave>", lambda e: jc.itemconfigure("edge", outline=EDGE, fill=TILE_BG))
        self.jeopsu_busy = False
        self.opa_var = tk.IntVar(value=int(round(self.opacity * 10) * 10))

        self.status = tk.Label(self.root, text="", bg=PANEL, fg="#c82014", font=F(8), anchor="w")
        self.status.pack(fill="x", padx=PAD + px(2), pady=(px(6), 0))
        for w in (self.root, self.bgc, bar, self.title_lb, grid, self.status):
            self.bind_drag(w)

        self.mini = None
        self.auto_var = tk.BooleanVar(value=self.autostart_on())
        self.auto_cache = self.auto_var.get()
        self.tray = Tray(HERE0 / "업무위젯.ico", "업무위젯 (누르면 열려요)", lambda: self.auto_cache)
        # 메뉴가 길어지지 않게 성격별로 묶는다: 환경설정 / 화면 ▸ / 자동 실행·알림 ▸ / 도움말 ▸ / 종료
        self.m = tk.Menu(self.root, tearoff=0, font=F(10))
        self.m.add_command(label="환경설정 (지역·인증서·암호)", command=self.open_setup)
        vm = tk.Menu(self.m, tearoff=0, font=F(10))       # 화면 ▸ 시계 카드·투명도·크기
        cm = tk.Menu(vm, tearoff=0, font=F(10))
        for key in CLOCK_KEYS:
            cm.add_checkbutton(label=CLOCK_LABEL[key], variable=self.clock_vars[key], command=self.apply_clock)
        cm.add_separator()
        cm.add_command(label="모두 켜기", command=lambda: self.set_all_clock(True))
        cm.add_command(label="모두 끄기 (위젯이 작아져요)", command=lambda: self.set_all_clock(False))
        vm.add_cascade(label="시계 카드 보이기", menu=cm)
        om = tk.Menu(vm, tearoff=0, font=F(10))
        for pct in range(100, 20, -10):
            om.add_radiobutton(label="%d%%" % pct + ("  (흐리게)" if pct == 30 else ""), value=pct, variable=self.opa_var,
                               command=lambda: self.on_opacity(self.opa_var.get()))
        vm.add_cascade(label="투명도", menu=om)
        self.size_var = tk.IntVar(value=UI_PCT)
        sm = tk.Menu(vm, tearoff=0, font=F(10))
        for pct, name in SIZE_CHOICES:
            sm.add_radiobutton(label=name, value=pct, variable=self.size_var, command=self.on_size)
        vm.add_cascade(label="위젯 크기", menu=sm)
        self.m.add_cascade(label="화면 (시계·투명도·크기)", menu=vm)
        self.m.add_command(label="펼침 메뉴 고르기 (나이스·에듀파인)", command=self.open_picker)
        am = tk.Menu(self.m, tearoff=0, font=F(10))       # 자동 실행·알림 ▸ 켜고 끄는 항목들
        am.add_checkbutton(label="윈도우 시작할 때 자동 실행", variable=self.auto_var, command=self.toggle_autostart)
        self.notify_var = tk.BooleanVar(value=self.notify_on)
        am.add_checkbutton(label="결재대기 알림 (새로 오면 알려줘요)", variable=self.notify_var, command=self.toggle_notify)
        daejeon = is_daejeon()                # DJE 메신저는 대전교육청용 — 지역이 대전일 때만 메뉴에 보인다
        if daejeon:
            self.dje_auto_var = tk.BooleanVar(value=self.dje_auto)
            am.add_checkbutton(label="위젯을 켤 때 DJE 메신저 자동 로그인", variable=self.dje_auto_var, command=self.toggle_dje_auto)
        self.m.add_cascade(label="자동 실행·알림", menu=am)
        # DJE 메신저 로그인은 4번 단추(DJE Talk)로 옮겼다 — 메뉴에는 «켤 때 자동 로그인» 켜고 끄기만 남긴다
        hm = tk.Menu(self.m, tearoff=0, font=F(10))       # 도움말 ▸ 업데이트·문제 해결
        hm.add_command(label="업데이트 확인 (지금 v%s)" % (UPD.local_version(KIT) if UPD else "?"),
                       command=lambda: self.check_update(manual=True))
        hm.add_command(label="문제 해결용 기록 복사 (붙여넣어 보내기)", command=self.copy_support)
        self.m.add_cascade(label="도움말 (업데이트·문제 해결)", menu=hm)
        self.upd_busy = False
        self.upd_start_pending = True                     # 켤 때 한 번 확인 (성공하면 got_update 에서 내린다)
        self.m.add_separator()
        self.m.add_command(label="위젯 완전 종료", command=self.quit_from_menu)
        self.root.bind("<Button-3>", lambda e: self.popup(e.x_root, e.y_root))
        self.apply_clock(save=False)

    # ── 시계 카드 켜기·끄기 (모두 끄면 윗줄이 빠지고 위젯 높이가 줄어든다) ──
    def set_all_clock(self, on):
        for v in self.clock_vars.values():
            v.set(on)
        self.apply_clock()

    def apply_clock(self, save=True):
        self.close_sub()
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
        self.base_h = SIZE_H if on else SIZE_H - (TILE + GAP)
        self.set_height(self.base_h)
        if save:
            try:
                K.save_state(clock_cards=on)
            except Exception:
                pass
            self.keep_visible()

    @staticmethod
    def chev_pts(up):
        x0, x1, xm = TILE - px(13), TILE - px(6), TILE - px(9.5)
        y0, y1 = px(6), px(10)
        return (x0, y1, x1, y1, xm, y0) if up else (x0, y0, x1, y0, xm, y1)

    def set_height(self, h, y=None):
        self.root.geometry("%dx%d" % (SIZE_W, h) + ("" if y is None else "+%d+%d" % (self.root.winfo_x(), y)))
        self.bgc.configure(height=h)
        self.bgc.delete("all")
        round_rect(self.bgc, 1, 1, SIZE_W - 2, h - 2, px(16), fill=PANEL, outline="#d6d1c6", width=1)

    # ── 펼침 단추 (나이스 ▾ · 에듀파인 ▾) — 아래로 한 줄 펼치고, 화면 아래가 모자라면 위로 펼친다 ──
    def toggle_sub(self, kind):
        was = self.sub_open
        self.close_sub()
        if was != kind:
            self.open_sub(kind)

    def open_sub(self, kind):
        items = self.submenus.get(kind) or []
        if not items:
            self.say("펼칠 메뉴가 없어요 — ⚙ → 펼침 메뉴 고르기에서 넣어 주세요", "#c82014")
            return
        acc, badge, tint = ACCENT[kind]
        rows = (len(items) + SUB_COLS - 1) // SUB_COLS
        self.sub_extra = rows * (TILE + GAP) + px(8)
        self.root.update_idletasks()
        y = self.root.winfo_y()
        bottom = self.root.winfo_screenheight() - px(48)          # 작업표시줄 몫을 남긴다
        self.sub_up = y + self.base_h + self.sub_extra > bottom and y - self.sub_extra >= 0
        if self.sub_up:                                            # 위로: 시계 카드와 단추 줄 사이(1번 줄)에 넣고 위젯을 그만큼 올린다
            f = tk.Frame(self.grid, bg=PANEL)
            f.grid(row=1, column=0, columnspan=6, pady=(px(4), px(4)))
        else:
            f = tk.Frame(self.root, bg=PANEL)
            f.pack(after=self.grid, padx=PAD, pady=(px(4), 0))
        self.bind_drag(f)
        for i, it in enumerate(items):
            name, job = it["name"], it["job"]
            text = it.get("text") or sub_text(name)
            c = tk.Canvas(f, width=TILE, height=TILE, bg=PANEL, highlightthickness=0, cursor="hand2")
            c.grid(row=i // SUB_COLS, column=i % SUB_COLS, padx=GAP // 2, pady=GAP // 2)
            round_rect(c, px(2), px(2), TILE - px(2), TILE - px(2), px(12), fill=tint, outline=badge, width=1, tags="edge")
            c.create_rectangle(px(16), px(7), TILE - px(16), px(10), fill=acc, outline="")
            c.create_text(TILE // 2, TILE // 2 + px(3), text=text, fill=WHITE, font=fit_font(text, TILE - px(8)), justify="center")
            c.bind("<Button-1>", lambda e, j=job, n=name: self.click_sub(j, n))
            c.bind("<Enter>", lambda e, w=c, a=acc: w.itemconfigure("edge", outline=a, fill=TILE_BG))
            c.bind("<Leave>", lambda e, w=c, t=tint, b=badge: w.itemconfigure("edge", outline=b, fill=t))
        self.sub_frame = f
        self.sub_open = kind
        self.sub_tiles[kind].itemconfigure("edge", outline=acc, fill=tint)
        self.sub_tiles[kind].coords("chev", *self.chev_pts(True))
        self.set_height(self.base_h + self.sub_extra, y - self.sub_extra if self.sub_up else None)
        self.sub_idle = 0
        self.sub_watch_id = self.root.after(1000, self.sub_watch)

    def sub_watch(self):
        """펼친 채 마우스가 위젯 밖에 SUB_IDLE_S 초 있으면 접는다 (위젯 위에 있으면 계속 펼쳐 둔다)."""
        if self.sub_open is None:
            return
        try:
            mx, my = self.root.winfo_pointerxy()
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            inside = x <= mx < x + self.root.winfo_width() and y <= my < y + self.root.winfo_height()
        except Exception:
            inside = False
        self.sub_idle = 0 if inside else self.sub_idle + 1
        if self.sub_idle >= SUB_IDLE_S:
            self.close_sub()
            return
        self.sub_watch_id = self.root.after(1000, self.sub_watch)

    def close_sub(self):
        if self.sub_open is None:
            return
        kind, self.sub_open = self.sub_open, None
        if getattr(self, "sub_watch_id", None):            # 펼칠 때마다 감시가 하나씩 쌓이지 않게 앞의 것을 끈다
            self.root.after_cancel(self.sub_watch_id)
            self.sub_watch_id = None
        self.sub_tiles[kind].itemconfigure("edge", outline=EDGE, fill=TILE_BG)
        self.sub_tiles[kind].coords("chev", *self.chev_pts(False))
        if self.sub_frame is not None:
            self.sub_frame.destroy()
            self.sub_frame = None
        self.root.update_idletasks()
        y = self.root.winfo_y() + (self.sub_extra if self.sub_up else 0)
        self.sub_up = False
        self.sub_extra = 0
        self.set_height(self.base_h, y)

    def click_sub(self, job, name):
        self.close_sub()
        if isinstance(job, str):                  # 원래 단추 하나와 같은 일 (나이스 첫 화면 · 내부기안 · 품의등록)
            self.click(job)
            return
        site, target = job[0], job[1]
        arg = json.dumps(target, ensure_ascii=False) if site == "neis" else target
        self.click(("work_widget_menu.py", ("open-" + site, arg, name),
                    "✅  열었습니다", "✅ %s 화면을 열었습니다 (신청·저장·결재는 안 함)" % name))

    def show_tip(self):
        self.hide_tip()
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        tk.Label(t, text=CREDIT, bg="#fffdf7", fg="#6b6b6b", font=F(8), padx=px(6), pady=px(2),
                 highlightthickness=1, highlightbackground="#d6d1c6").pack()
        t.update_idletasks()
        x = self.title_lb.winfo_rootx()
        y = self.title_lb.winfo_rooty() - t.winfo_reqheight() - px(4)
        if y < 0:
            y = self.title_lb.winfo_rooty() + self.title_lb.winfo_height() + px(4)
        t.geometry("+%d+%d" % (x, y))
        self.tip = t

    def hide_tip(self):
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None

    # ── 펼침 메뉴 고르기 창 (⚙ 메뉴) ──
    @staticmethod
    def menus_file():
        return KIT / MENUS_FILE_NAME

    def load_catalog(self):
        try:
            d = json.loads(self.menus_file().read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else None
        except Exception:
            return None

    def read_menus(self):
        self.click(("work_widget_menu.py", ("read",), "✅  메뉴를 읽었습니다", "✅ 내 메뉴를 읽었어요 — 고르는 창에 목록이 나와요"))

    def open_picker(self):
        if self.picker is not None and self.picker.winfo_exists():
            self.picker.deiconify()
            self.picker.lift()
            return
        self.close_sub()
        top = tk.Toplevel(self.root)
        self.picker = top
        top.title("펼침 메뉴 고르기")
        top.configure(bg=PANEL)
        top.attributes("-topmost", True)
        try:
            top.iconbitmap(str(HERE0 / "업무위젯.ico"))
        except Exception:
            pass
        sty = ttk.Style(top)
        sty.configure("Treeview", font=F(9), rowheight=px(22))
        sty.configure("TNotebook.Tab", font=F(9, True), padding=(px(12), px(4)))
        chosen = {k: [dict(x) for x in self.submenus.get(k, [])] for k in ("neis", "edu")}
        state = {"cat": self.load_catalog(), "mtime": self._menus_mtime()}

        def key(job):
            return json.dumps(job, ensure_ascii=False)

        def options(kind):
            out = [{"name": n, "job": j, "group": "기본", "crumb": ""} for n, j in SUB_BUILTIN[kind]]
            cat = state["cat"] or {}
            if kind == "neis":
                out += [{"name": m["name"], "job": ["neis", m["path"]], "group": m["group"], "crumb": m.get("crumb", "")}
                        for m in cat.get("neis", []) if isinstance(m, dict) and "path" in m]
            else:
                out += [{"name": m["name"], "job": ["edufine", m["id"]], "group": m["group"], "crumb": m.get("crumb", "")}
                        for m in cat.get("edufine", []) if isinstance(m, dict) and "id" in m]
            have = {key(o["job"]) for o in out}
            out += [{"name": x["name"], "job": x["job"], "group": "지금 펼침 칸에 있는 메뉴", "crumb": ""}
                    for x in chosen[kind] if key(x["job"]) not in have]
            return out

        head = tk.Label(top, bg=PANEL, fg="#5c5c5c", font=F(9), justify="left", anchor="w")
        head.pack(fill="x", padx=px(12), pady=(px(10), px(4)))
        nb = ttk.Notebook(top)
        nb.pack(fill="both", expand=True, padx=px(10))
        views = {}
        for kind, title in (("neis", "  나이스 ▾  "), ("edu", "  에듀파인 ▾  ")):
            f = tk.Frame(nb, bg=PANEL)
            nb.add(f, text=title)
            lf = tk.Frame(f, bg=PANEL)
            lf.pack(side="left", fill="both", expand=True, padx=(px(6), px(4)), pady=px(6))
            tk.Label(lf, text="전체 메뉴 — 눌러서 넣기 / 빼기", bg=PANEL, fg=WHITE, font=F(9, True), anchor="w").pack(fill="x")
            tvf = tk.Frame(lf, bg=PANEL)
            tvf.pack(fill="both", expand=True)
            tv = ttk.Treeview(tvf, show="tree", height=16, selectmode="browse")
            sb = ttk.Scrollbar(tvf, orient="vertical", command=tv.yview)
            tv.configure(yscrollcommand=sb.set)
            tv.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            rf = tk.Frame(f, bg=PANEL)
            rf.pack(side="left", fill="y", padx=(px(4), px(6)), pady=px(6))
            tk.Label(rf, text="펼침 칸 (이 순서, 최대 %d개)" % SUB_MAX, bg=PANEL, fg=WHITE, font=F(9, True), anchor="w").pack(fill="x")
            lb = tk.Listbox(rf, height=14, width=22, font=F(9), activestyle="none", exportselection=False)
            lb.pack(fill="y", expand=True)
            bf = tk.Frame(rf, bg=PANEL)
            bf.pack(fill="x", pady=(px(4), 0))
            views[kind] = {"tv": tv, "lb": lb, "map": {}}
            for t, cmd in (("▲ 위로", lambda k=kind: move(k, -1)), ("▼ 아래로", lambda k=kind: move(k, 1)), ("빼기", lambda k=kind: remove(k))):
                tk.Button(bf, text=t, font=F(9), command=cmd, relief="groove", bg=TILE_BG).pack(side="left", expand=True, fill="x", padx=1)
            tv.bind("<<TreeviewSelect>>", lambda e, k=kind: toggle(k))

        def mark(kind):
            v = views[kind]
            keys = {key(x["job"]) for x in chosen[kind]}
            for iid, o in v["map"].items():
                v["tv"].item(iid, text=("☑  " if key(o["job"]) in keys else "☐  ") + o["name"])
            v["lb"].delete(0, "end")
            for x in chosen[kind]:
                v["lb"].insert("end", x["name"])

        def fill(kind):
            v = views[kind]
            tv = v["tv"]
            tv.delete(*tv.get_children())
            v["map"] = {}
            nodes = {}
            for o in options(kind):
                g = o["group"]
                if g not in nodes:
                    nodes[g] = tv.insert("", "end", text=g, open=g in ("기본", "지금 펼침 칸에 있는 메뉴", "나의메뉴"))
                parent = nodes[g]
                if o["crumb"]:
                    ck = (g, o["crumb"])
                    if ck not in nodes:
                        nodes[ck] = tv.insert(nodes[g], "end", text=o["crumb"])
                    parent = nodes[ck]
                v["map"][tv.insert(parent, "end", text=o["name"])] = o
            mark(kind)

        def toggle(kind):
            v = views[kind]
            sel = v["tv"].selection()
            if not sel or sel[0] not in v["map"]:
                return
            o = v["map"][sel[0]]
            v["tv"].selection_remove(sel[0])
            k = key(o["job"])
            if any(key(x["job"]) == k for x in chosen[kind]):
                chosen[kind] = [x for x in chosen[kind] if key(x["job"]) != k]
            elif len(chosen[kind]) >= SUB_MAX:
                head.configure(text="펼침 칸은 %d개까지예요 — 오른쪽에서 하나를 뺀 뒤 넣어 주세요" % SUB_MAX, fg="#c82014")
                return
            else:
                chosen[kind].append({"name": o["name"], "job": o["job"]})
            mark(kind)

        def move(kind, d):
            lb = views[kind]["lb"]
            sel = lb.curselection()
            if not sel:
                return
            i, j = sel[0], sel[0] + d
            if 0 <= j < len(chosen[kind]):
                chosen[kind][i], chosen[kind][j] = chosen[kind][j], chosen[kind][i]
                mark(kind)
                lb.selection_set(j)

        def remove(kind):
            sel = views[kind]["lb"].curselection()
            if sel:
                del chosen[kind][sel[0]]
                mark(kind)

        def show_head():
            cat = state["cat"]
            if cat:
                head.configure(fg="#5c5c5c", text="내 메뉴를 읽은 때: %s   (역할·권한이 바뀌었으면 [내 메뉴 다시 읽기])" % cat.get("read_at", "?"))
            else:
                head.configure(fg="#c82014", text="아직 내 메뉴를 읽지 않았어요 — 아래 [내 메뉴 읽어오기]를 누르면 나이스·에듀파인에 로그인해서\n"
                                                  "선생님 계정의 메뉴 목록을 읽어 와요 (1분쯤, 화면은 옮기지 않아요)")

        def reset():
            d = sub_defaults()
            for k in chosen:
                chosen[k] = d[k]
                fill(k)

        def save():
            self.submenus = {k: [dict(x) for x in chosen[k]] for k in chosen}
            K.save_state(submenus=self.submenus)
            self.say("✅ 펼침 메뉴를 저장했어요", "#00754A")
            close()

        def close():
            self.picker = None
            top.destroy()

        def watch():                      # 메뉴 읽기가 끝나면(파일이 바뀌면) 목록을 새로 채운다
            if self.picker is not top or not top.winfo_exists():
                return
            m = self._menus_mtime()
            if m != state["mtime"]:
                state["mtime"], state["cat"] = m, self.load_catalog()
                for k in chosen:
                    fill(k)
                show_head()
            top.after(1500, watch)

        bot = tk.Frame(top, bg=PANEL)
        bot.pack(fill="x", padx=px(10), pady=px(10))
        for t, cmd, side in (("저장", save, "right"), ("취소", close, "right"), ("기본값으로", reset, "left"),
                             ("내 메뉴 읽어오기" if not state["cat"] else "내 메뉴 다시 읽기", self.read_menus, "left")):
            tk.Button(bot, text=t, font=F(9, t == "저장"), command=cmd, relief="groove", padx=px(10),
                      bg=GREEN if t == "저장" else TILE_BG, fg="#ffffff" if t == "저장" else WHITE).pack(side=side, padx=px(3))
        top.protocol("WM_DELETE_WINDOW", close)
        for k in chosen:
            fill(k)
        show_head()
        top.update_idletasks()
        w, h = max(top.winfo_reqwidth(), px(560)), top.winfo_reqheight()
        top.geometry("%dx%d+%d+%d" % (w, h, max(0, (top.winfo_screenwidth() - w) // 2), max(0, (top.winfo_screenheight() - h) // 3)))
        top.after(1500, watch)

    def _menus_mtime(self):
        try:
            return self.menus_file().stat().st_mtime
        except Exception:
            return None

    # ── 타일 ──
    def make_tile(self, parent, r, c, hand=False):
        cv = tk.Canvas(parent, width=TILE, height=TILE, bg=PANEL, highlightthickness=0, cursor="hand2" if hand else "")
        cv.grid(row=r, column=c, padx=GAP // 2, pady=GAP // 2)
        round_rect(cv, px(2), px(2), TILE - px(2), TILE - px(2), px(12), fill=TILE_BG, outline=EDGE, width=1, tags="edge")
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
        try:
            if str(e.widget.cget("cursor")) == "hand2":      # ✕ ⚙ 📍 · 단추 칸을 누른 것은 끌기가 아니다 (위로 번져 올라온 누름)
                return
        except Exception:
            pass
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
            K.save_state(x=self.root.winfo_x(), y=self.root.winfo_y() + (self.sub_extra if self.sub_up else 0))
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
    def say(self, text, color="#c82014"):
        self.status.configure(text=text, fg=color)

    def click(self, kind):
        is_dje = (kind == "dje")
        if is_dje:
            # DJE 메신저는 크롬(포털 탭)을 쓰지 않으니 포털·건수 작업과 따로 돈다. DJE끼리만 겹치지 않게 한다.
            if self.dje_busy:
                self.say("DJE 메신저 로그인이 이미 진행 중입니다", "#c82014")
                return
        else:
            if self.sanctn_busy or self.jeopsu_busy:        # 건수 자동 조회가 같은 포털 탭을 쓰는 중이면 끝난 뒤에
                self.say("건수를 읽는 중이에요 — 잠시 뒤 다시 눌러 주세요", "#c82014")
                return
            if self.busy:
                self.say("지금 다른 작업이 진행 중입니다 (%s)" % self.busy, "#c82014")
                return
        if isinstance(kind, tuple):               # 펼침 칸: (스크립트, 인자, 끝 표시, 끝 안내)
            script, args, done, done_msg = kind
        else:
            script, done, done_msg = JOBS[kind]
            args = ()
        if not (KIT / ".venv" / "Scripts" / "python.exe").exists() or not (KIT / script).exists():
            self.say("키트 파일을 찾지 못했습니다 (%s) — 업무위젯 설치를 다시 실행하세요" % script)
            return
        if not K.configured():
            self.say("먼저 ⚙ → 환경설정 (지역·인증서·암호)", "#c82014")
            return
        if is_dje:
            self.dje_busy = True
        else:
            self.busy = "로그인 중"
        self.say("⏳ DJE 메신저 로그인 중… (다른 단추는 그대로 쓸 수 있어요)" if is_dje else "⏳ 로그인 중… (크롬 창이 뜹니다)", "#5c5c5c")
        threading.Thread(target=self.run_job, args=(script, done, done_msg, is_dje, args), daemon=True).start()

    def run_job(self, script, done, done_msg, is_dje=False, args=()):
        t0 = time.time()
        last = ""
        ok = False
        timer = None
        try:
            # DJE 로그인은 크롬 잠금(self.lock)을 쓰지 않는다. 대신 멈춘 창에 걸려도 150초 뒤엔 스스로 끊는다.
            with (contextlib.nullcontext() if is_dje else self.lock):
                p = subprocess.Popen([str(K.PY), "-X", "utf8", str(KIT / script), *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", env=K.ENV, cwd=str(KIT), creationflags=K.NO_WINDOW)
                if is_dje:
                    timer = threading.Timer(150, p.kill)
                    timer.daemon = True
                    timer.start()
                tail = []
                for line in p.stdout:
                    line = line.strip()
                    tail.append(line)
                    if line.startswith("JEOPSU ") and line[7:].strip().isdigit():     # 기관접수대기 화면을 열며 읽은 건수
                        self.root.after(0, self.show_jeopsu, int(line[7:].strip()), "", False)
                    if done in line:
                        ok = True
                        msg = "✅ 이미 로그인되어 있습니다" if (is_dje and "이미 로그인" in line) else done_msg
                        self.root.after(0, self.say, msg, "#00754A")
                    elif line.startswith(("⏸", "❌")):
                        # 작은따옴표 안(인증서 이름 등)은 가린다
                        last = re.sub(r"'[^']*'", "'***'", re.sub(r"^[⏸❌]\s*", "", line))[:110]
                        self.root.after(0, self.say, "⚠️ " + last, "#c82014")
                p.wait()
            if p.returncode != 0 and not ok:
                if is_dje and not last:
                    last = "응답이 없어 중단했습니다 (DJE Talk 창이 멈췄는지 확인하세요)"
                self.root.after(0, self.say, "❌ 열지 못했습니다: " + (last or "원인 출력 없음"), "#c82014")
        except Exception as e:
            self.root.after(0, self.say, "❌ 실행하지 못했습니다: " + type(e).__name__, "#c82014")
        finally:
            if timer:
                timer.cancel()
            if is_dje:
                self.dje_busy = False
            else:
                self.busy = None
            K.log_line("업무위젯 %s %.1fs %s" % (" ".join([script, *args[:1]]), time.time() - t0, "ok" if ok else "FAIL " + last))
            if ok and script == "open_sanctn.py":       # 결재대기함을 연 김에 숫자도 새로 읽는다 (조용히)
                self.root.after(4000, self.refresh_sanctn)

    # ── 에듀파인 결재대기 건수 (check_sanctn.py 가 업무포털 메인 숫자만 읽는다 · 30분마다 + 칸을 누르면 바로) ──
    def refresh_sanctn(self, manual=False):
        if self.sanctn_busy or self.jeopsu_busy or self.busy:     # 로그인·화면 열기·접수 건수 읽기 중에는 포털 탭을 건드리지 않는다
            if manual:
                self.say("다른 작업이 끝난 뒤 다시 눌러 주세요", "#c82014")
            return
        script = KIT / "check_sanctn.py"
        if not (KIT / ".venv" / "Scripts" / "python.exe").exists() or not script.exists():
            if manual:
                self.say("키트에 check_sanctn.py 가 없습니다 — 업무위젯 설치를 다시 실행하세요")
            return
        if not K.configured():
            return
        self.sanctn_busy = True
        self.sanctn_cv.itemconfigure(self.sanctn_num, fill="#a8a49b")
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
            color = "#c82014" if urgent else ("#b7791f" if wait else GREEN)
            self.sanctn_cv.itemconfigure(self.sanctn_num, text=str(wait), fill=color)
            self.sanctn_cv.itemconfigure(self.sanctn_lab, text="에듀파인\n" + ("긴급 %d" % urgent if urgent else "결재대기"))
            # 결재대기가 있으면 칸 바탕·테두리에 색을 넣는다 (긴급 = 붉은 음영, 일반 = 노란 음영)
            if urgent:
                self.sanctn_look = ("#fde3df", "#c82014", 2, True)
            elif wait:
                self.sanctn_look = ("#fff0c2", "#e0a526", 2, True)
            else:
                self.sanctn_look = (TILE_BG, EDGE, 1, False)
            self.paint_sanctn()
            if manual:
                self.say("✅ 결재대기 %d건 (%s)" % (wait, hm), "#00754A")
            self.notify_sanctn(wait, urgent)
        else:
            self.sanctn_look = (TILE_BG, EDGE, 1, False)           # 못 읽었을 땐 색을 빼서 «0건» 으로 오해하지 않게
            self.paint_sanctn()
            self.sanctn_cv.itemconfigure(self.sanctn_num, text="--", fill="#a8a49b")
            self.sanctn_cv.itemconfigure(self.sanctn_lab, text="에듀파인\n결재대기")
            if manual:
                self.say("⚠️ " + reason, "#c82014")

    def paint_sanctn(self, hover=False):
        """결재대기 칸 색칠. 평소엔 sanctn_look · 마우스를 올리면 알림 중엔 같은 색을 조금 진하게, 아니면 기존 초록."""
        fill, outline, width, alert = self.sanctn_look
        if hover:
            fill, outline, width = (("#fbd2cc" if fill == "#fde3df" else "#ffe69a"), outline, 3) if alert else ("#eef6f2", GREEN, 1)
        self.sanctn_cv.itemconfigure("edge", fill=fill, outline=outline, width=width)

    def notify_sanctn(self, wait, urgent):
        """결재대기·긴급이 지난번보다 «늘었을 때만» 윈도우 알림을 띄운다 (처음 읽을 때는 기준만 저장 · 줄거나 같으면 조용히)."""
        prev = self.sanctn_last
        self.sanctn_last = [wait, urgent]
        try:
            K.save_state(sanctn_last=self.sanctn_last)
        except Exception:
            pass
        if not self.notify_on or not isinstance(prev, list) or len(prev) != 2:
            return
        new_wait, new_urgent = wait - int(prev[0]), urgent - int(prev[1])
        if new_urgent > 0:
            title, text, warn = "긴급 결재가 도착했어요", "긴급 결재 %d건 · 결재대기 모두 %d건" % (urgent, wait), True
        elif new_wait > 0:
            title, text, warn = "결재대기가 새로 왔어요", "새로 %d건 · 결재대기 모두 %d건" % (new_wait, wait), False
        else:
            return
        try:
            temp = self.tray.balloon(title, text, warn)
        except Exception as e:
            K.log_line("업무위젯 알림 오류 %r" % e)
            return
        K.log_line("업무위젯 결재대기 알림: %s" % text)
        # 트레이 아이콘은 항상 달려 있으므로 알림 뒤에 떼지 않는다

    def on_size(self):
        """작게/보통/크게 — 모든 칸의 크기가 바뀌므로 저장한 뒤 위젯을 다시 켠다."""
        v = self.size_var.get()
        if v == UI_PCT:
            return
        if self.busy or self.dje_busy or self.sanctn_busy or self.jeopsu_busy or self.upd_busy:
            self.size_var.set(UI_PCT)
            self.say("하던 작업이 끝난 뒤 크기를 바꿔 주세요", "#c82014")
            return
        K.save_state(ui_scale=v)
        self.say("크기를 바꾸려고 위젯을 다시 켜요…", "#5c5c5c")
        self.save_pos()
        self.root.after(300, self.relaunch)

    @staticmethod
    def mask_private(text):
        """기록에 섞일 수 있는 개인 정보를 가린다 — 작은따옴표 안(인증서 이름 등) · 윈도우 사용자 폴더 이름 · 메일 주소 · 6자리 이상 숫자."""
        text = re.sub(r"'[^']*'", "'***'", text)
        text = re.sub(r"(?i)([A-Za-z]:\\Users\\)[^\\/\s]+", r"\1***", text)
        text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "***@***", text)
        return re.sub(r"\d{6,}", "******", text)

    def support_text(self):
        import platform
        chrome = any((Path(b) / "Google" / "Chrome" / "Application" / "chrome.exe").exists()
                     for b in (K.os.environ.get("PROGRAMFILES"), K.os.environ.get("PROGRAMFILES(X86)"), K.os.environ.get("LOCALAPPDATA")) if b)
        try:
            lines = K.LOG.read_text(encoding="utf-8").splitlines()[-30:] if K.LOG.exists() else []
        except Exception:
            lines = []
        head = [
            "[업무위젯 문제 해결용 기록]",
            "위젯 버전: v%s" % (UPD.local_version(KIT) if UPD else "?"),
            "윈도우: %s · 파이썬 %s" % (platform.platform(), platform.python_version()),
            "화면 배율: %d%% · 위젯 크기: %d%%" % (round(DPI * 100), UI_PCT),
            "설정(지역·인증서): %s" % ("있음" if K.configured() else "없음"),
            "구글 크롬 설치: %s" % ("있음" if chrome else "못 찾음"),
            "결재대기 알림: %s · 항상 위: %s" % ("켜짐" if self.notify_on else "꺼짐", "켜짐" if self.pinned else "꺼짐"),
            "--- 최근 기록 %d줄 (개인 정보는 *** 로 가렸어요) ---" % len(lines),
        ]
        return self.mask_private("\n".join(head + lines))

    def copy_support(self):
        try:
            txt = self.support_text()
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            self.root.update()                                  # 창이 닫혀도 클립보드가 남도록 바로 넘긴다
            self.say("✅ 기록을 복사했어요 — 메신저에 붙여넣기(Ctrl+V) 하세요", "#00754A")
        except Exception as e:
            K.log_line("업무위젯 기록 복사 오류 %r" % e)
            self.say("기록을 복사하지 못했어요", "#c82014")

    def toggle_dje_auto(self):
        self.dje_auto = self.dje_auto_var.get()
        K.save_state(dje_autostart=self.dje_auto)
        self.say("다음부터 위젯을 켜면 DJE 메신저에 자동 로그인해요" if self.dje_auto else "DJE 메신저 자동 로그인을 껐어요",
                 "#00754A" if self.dje_auto else "#5c5c5c")

    def dje_watch(self, until):
        """DJE 메신저 창이 나타나기를 지켜보다가, 보이는 순간 로그인을 시작한다 (직접 켜지는 않는다 — 윈도우 시작 때 스스로 켜지는 경우용).
        지켜보기는 가벼운 창 확인뿐이라 다른 단추를 막지 않는다. 최대 10분만 지켜보고 그만둔다."""
        if not (self.dje_auto and is_daejeon()):
            return
        try:
            _user32.FindWindowW.restype = _wt.HWND
            _user32.IsWindowVisible.argtypes = [_wt.HWND]
            hwnd = _user32.FindWindowW("TFM_ucware_main.UnicodeClass", None)
            seen = bool(hwnd) and bool(_user32.IsWindowVisible(hwnd))
        except Exception:
            return
        if seen:
            if not self.dje_busy:
                self.click("dje")               # 켜져 있으면 바로 로그인 (이미 로그인돼 있으면 스크립트가 알아서 건너뜀)
                return
        if time.time() < until:
            self.root.after(300, lambda: self.dje_watch(until))


    def toggle_notify(self):
        self.notify_on = self.notify_var.get()
        K.save_state(notify_sanctn=self.notify_on)
        self.say("결재대기 알림을 켰어요" if self.notify_on else "결재대기 알림을 껐어요", "#00754A" if self.notify_on else "#5c5c5c")

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
        self.jeopsu_cv.itemconfigure(self.jeopsu_num, fill="#a8a49b")
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
                reason = re.sub(r"'[^']*'", "'***'", re.sub(r"^❌\s*", "", bad[-1] if bad else "원인 출력 없음"))[:100]     # 작은따옴표 안(인증서 이름 등)은 가린다
        except Exception as e:
            reason = "실행하지 못했습니다: " + type(e).__name__
        self.root.after(0, self.show_jeopsu, res, reason, True)

    def show_jeopsu(self, res, reason, from_check):
        if from_check:
            self.jeopsu_busy = False
        if res is not None:
            self.jeopsu_cv.itemconfigure(self.jeopsu_num, text=str(res), fill="#2b5148" if res else GREEN)
        elif from_check:
            self.jeopsu_cv.itemconfigure(self.jeopsu_num, text="--", fill="#a8a49b")
            K.log_line("업무위젯 기관접수대기 못 읽음: " + reason)

    # ── 자동 업데이트 (work_widget_update.py: 서명 확인 → 받기 → 덮어쓰기 → 위젯 다시 켜기) ──
    def check_update(self, manual=False):
        if UPD is None or self.upd_busy:
            if manual:
                self.say("업데이트 기능이 없는 버전이에요 — 설치 파일로 한 번 다시 설치해 주세요" if UPD is None else "업데이트 확인 중이에요")
            return
        self.upd_busy = True
        if manual:
            self.upd_popup("🔄 업데이트 확인 중", "잠시만 기다려 주세요…", "#00754A")

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
                self.upd_popup("⚠ 업데이트 확인 실패", "인터넷 연결을 확인해 주세요", "#c82014", 5000)
            return
        self.upd_start_pending = False
        K.save_state(update_checked=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if not m:
            if manual:
                self.upd_popup("✅ 최신 버전", "지금 v%s 를 쓰고 있어요" % UPD.local_version(KIT), "#00754A", 3000)
            return
        self.apply_update(m, manual)

    def apply_update(self, m, manual=False):
        if self.busy or self.dje_busy or self.sanctn_busy or self.jeopsu_busy:     # 로그인·화면 열기·건수 읽기 중이면 잠깐 뒤에 다시 (직접 눌렀으면 15초, 자동이면 1분)
            if manual:
                self.upd_popup("⏳ 업데이트 대기", "하던 작업이 끝나면 v%s 로 바로 업데이트할게요" % m["version"], "#5c5c5c")
            self.upd_busy = True                      # 기다리는 동안 다른 확인이 또 시작되지 않게
            self.root.after(15_000 if manual else 60_000, self.apply_update, m, manual)
            return
        self.busy = "업데이트 중"
        self.upd_busy = True
        self.upd_popup("⬇ 업데이트 중", "v%s 로 바꾸고 있어요 · 끝나면 위젯이 다시 켜져요" % m["version"], "#00754A")

        state = {"done": False}

        def watchdog():
            """3분이 지나도 끝나지 않으면 «업데이트 중» 표시만 푼다 (위젯은 다시 쓸 수 있게).
            뒤에서 도는 업데이트가 끝날 때까지 upd_busy 는 그대로 둬서 업데이트가 겹쳐 시작되지 않게 한다."""
            if state["done"]:
                return
            if self.busy == "업데이트 중":
                self.busy = None
            K.log_line("업무위젯 업데이트가 3분 안에 끝나지 않아 멈춤 표시를 풀었습니다")
            self.upd_popup("⚠ 업데이트가 오래 걸려요", "지금 버전 그대로 써요 · 잠시 뒤 다시 확인해 보세요", "#c82014", 8000)
        self.root.after(180_000, watchdog)

        def work():
            try:
                UPD.apply(KIT, m, lambda s: self.root.after(0, self.say, "⏳ " + s + "…", "#5c5c5c"))
                state["done"] = True
                self.root.after(0, self.relaunch_when_idle)
            except Exception as e:
                msg = (str(e).splitlines() or [type(e).__name__])[0][:80]
                K.log_line("업무위젯 업데이트 실패: " + msg)
                self.root.after(0, self.upd_popup, "⚠ 업데이트 실패", "지금 버전 그대로 써요 · 다음에 다시 해 볼게요", "#c82014", 6000)
            finally:
                state["done"] = True
                if self.busy == "업데이트 중":            # 워치독 뒤 선생님이 시작한 작업 표시는 지우지 않는다
                    self.busy = None
                self.upd_busy = False
        threading.Thread(target=work, daemon=True).start()

    def relaunch_when_idle(self):
        """워치독이 풀린 뒤 선생님이 다른 작업을 시작했으면 끝날 때까지 기다렸다가 다시 켠다."""
        if (self.busy and self.busy != "업데이트 중") or self.dje_busy or self.sanctn_busy or self.jeopsu_busy:
            self.root.after(5000, self.relaunch_when_idle)
            return
        self.relaunch()

    def relaunch(self):
        """새 파일로 위젯을 다시 켠다 — 이 위젯이 끝난 뒤(한 개만 뜨기 표시가 풀린 뒤) 3초쯤 있다가 뜬다.
        창 없는 pythonw 가 기다렸다 켜므로 검은 명령 창이 뜨지 않는다."""
        pyw = str(K.PY.with_name("pythonw.exe"))
        code = ("import time,subprocess,sys;time.sleep(3);"
                "subprocess.Popen([sys.argv[1],sys.argv[2]],cwd=sys.argv[3],creationflags=0x08000000|0x00000200)")
        args = [pyw, "-c", code, pyw, str(HERE0 / "바로가기위젯.pyw"), str(HERE0)]
        base = 0x08000000 | 0x00000200          # 창 없음 · 새 프로세스 그룹
        try:
            subprocess.Popen(args, cwd=str(HERE0), creationflags=base | 0x01000000, close_fds=True)
        except OSError:
            subprocess.Popen(args, cwd=str(HERE0), creationflags=base, close_fds=True)
        self.quit()

    def upd_popup(self, title, sub="", color="#00754A", close_ms=None):
        """위젯 위에 작은 업데이트 알림 창을 띄운다 (같은 창을 계속 바꿔 쓴다 · 누르면 닫힘)."""
        try:
            pop = getattr(self, "_upd_pop", None)
            if pop is None or not pop.winfo_exists():
                pop = tk.Toplevel(self.root)
                pop.overrideredirect(True)
                pop.attributes("-topmost", True)
                pop.configure(bg=color)
                inner = tk.Frame(pop, bg="#ffffff")
                inner.pack(padx=2, pady=2)
                pop._t = tk.Label(inner, bg="#ffffff", font=F(12, True))
                pop._t.pack(padx=px(22), pady=(px(14), 2))
                pop._s = tk.Label(inner, bg="#ffffff", fg="#5c5c5c", font=F(9))
                pop._s.pack(padx=px(22), pady=(0, px(14)))
                for w in (pop, inner, pop._t, pop._s):
                    w.bind("<Button-1>", lambda e: self.close_upd_popup())
                self._upd_pop = pop
            pop.configure(bg=color)
            pop._t.configure(text=title, fg=color)
            pop._s.configure(text=sub)
            pop.update_idletasks()
            w, h = pop.winfo_reqwidth(), pop.winfo_reqheight()
            x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2
            x, y = K.fit_on_screen(x, y, w, h)
            pop.geometry("+%d+%d" % (x, y))
            pop.deiconify()
            pop.lift()
            if getattr(self, "_upd_pop_after", None):
                self.root.after_cancel(self._upd_pop_after)
                self._upd_pop_after = None
            if close_ms:
                self._upd_pop_after = self.root.after(close_ms, self.close_upd_popup)
        except Exception:
            self.say(title + (" — " + sub if sub else ""), color)

    def close_upd_popup(self):
        self._upd_pop_after = None
        pop = getattr(self, "_upd_pop", None)
        if pop is not None:
            try:
                pop.destroy()
            except Exception:
                pass
        self._upd_pop = None

    def update_due(self, now=None):
        """켠 뒤 아직 확인에 성공하지 못했거나, 정오가 지났는데 오늘 정오 이후로 확인한 적이 없으면 True."""
        if getattr(self, "upd_start_pending", True):
            return True
        now = now or datetime.now()
        if now.hour < UPDATE_HOUR:
            return False
        noon = now.strftime("%Y-%m-%d ") + "%02d:00:00" % UPDATE_HOUR
        return str(K.load_state().get("update_checked") or "") < noon      # 예전 형식("YYYY-MM-DD")도 정오 전으로 친다

    def update_loop(self):
        try:
            if self.update_due() and not self.upd_busy:
                self.check_update()               # 날짜는 확인에 성공했을 때(got_update)만 기록 → 실패하면 다음 점검 때 다시 시도
        finally:
            self.root.after(UPDATE_POLL_MS, self.update_loop)

    def jeopsu_first(self):
        if self.sanctn_busy or self.jeopsu_busy or self.busy:     # 겹치면 건너뛰지 않고 잠깐 뒤 다시 본다
            self.root.after(3000, self.jeopsu_first)
            return
        self.jeopsu_loop()

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
                if not self.pinned:
                    self.root.attributes("-topmost", False)      # 한 번 앞으로만 꺼내고 항상 위는 다시 끈다
        except Exception as e:
            K.log_line("업무위젯 keep_visible 오류 %r" % e)

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.root.attributes("-topmost", self.pinned)
        self.pin_label.configure(fg="#5c5c5c" if self.pinned else "#b5b0a5")
        K.save_state(pinned=self.pinned)

    def open_setup(self):
        subprocess.Popen([str(K.PY.with_name("pythonw.exe")), str(K.HERE / "바로가기_설정창.pyw")], cwd=str(K.HERE), env=K.ENV)
        self.say("설정 창에서 마쳐 주세요", "#5c5c5c")

    # ── 시스템 트레이로 내리기 / 되살리기 ──
    def minimize(self):
        """위젯을 숨기고 시스템 트레이(작업표시줄 오른쪽 아래)에 아이콘을 둔다. 아이콘을 누르면 되살아난다."""
        if self.mini is not None:
            return
        self.close_sub()
        self.save_pos()
        if not self.tray.add():
            self.say("트레이 아이콘을 만들지 못했어요", "#c82014")
            return
        self.mini = True
        self.root.withdraw()

    def restore(self):
        if self.mini is None:
            return
        self.mini = None
        self.root.deiconify()
        self.keep_visible(raise_=True)

    def drain_tray(self):
        try:
            while True:
                ev = self.tray.q.get_nowait()
                if ev == "show":
                    self.restore()
                    self.keep_visible(raise_=True)
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
        self._pop_t = time.monotonic()
        self.m.tk_popup(x, y)

    def show_options(self):
        # 위젯이 화면 아래쪽에 있으면 윈도우가 메뉴를 위로 밀어 올려, 마지막 줄(위젯 완전 종료)이 톱니바퀴 자리에 오고
        # 마우스를 떼는 순간 눌려 버린다 → 아래가 모자라면 톱니바퀴 «위쪽»에 메뉴 바닥이 오게 직접 올려 띄운다.
        gx, gy, gh = self.gear.winfo_rootx(), self.gear.winfo_rooty(), self.gear.winfo_height()
        est_h = (self.m.index("end") + 1) * px(30) + px(12)           # 줄 수로 어림한 메뉴 높이
        y = gy + gh + px(2)
        if y + est_h > self.root.winfo_screenheight() - px(48):       # 작업표시줄 몫 48 을 남긴다
            y = max(0, gy - est_h - px(2))
        self.popup(gx, y)

    def quit_from_menu(self):
        """메뉴에서 «위젯 완전 종료»: 메뉴가 뜬 직후(0.4초 안)의 눌림은 실수로 보고 무시하고, 그 뒤에도 한 번 묻는다."""
        if time.monotonic() - getattr(self, "_pop_t", 0) < 0.4:
            return
        try:
            from tkinter import messagebox
            if not messagebox.askyesno("업무위젯", "위젯을 완전히 끝낼까요?\n(창만 숨기려면 ✕ 를 누르세요)", parent=self.root):
                return
        except Exception:
            pass
        self.quit()

    # 바로가기 이름·아이콘 (이름은 «업무위젯», 예전 이름이 있으면 새 이름으로 바꿔 준다)
    LNK_NAME = "업무위젯.lnk"
    OLD_LNK = "나이스 에듀파인 바로가기.lnk"

    _folder_cache = {}

    @staticmethod
    def special_folder(kind):
        """kind: 'Startup' | 'Desktop' — 윈도우가 실제로 쓰는 폴더(OneDrive로 옮겨진 바탕화면 포함)."""
        d = Widget._folder_cache.get(kind)
        if d is None:
            d = ""
            try:                                     # 윈도우 API 로 바로 묻는다 (PowerShell 을 띄우지 않아 메뉴가 늦게 열리지 않는다)
                buf = K.ctypes.create_unicode_buffer(520)
                csidl = {"Startup": 0x0007, "Desktop": 0x0010}[kind]
                if K.ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0:
                    d = buf.value.strip()
            except Exception:
                d = ""
            if d:
                Widget._folder_cache[kind] = d
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
        ps = ('$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:WW_LNK); $s.TargetPath=$env:WW_PYW; '
              "$s.Arguments='\"' + $env:WW_TARGET + '\"'; $s.WorkingDirectory=$env:WW_DIR; $s.IconLocation=$env:WW_ICON + ',0'; "
              '$s.Description="업무위젯"; $s.Save()')
        env = dict(K.ENV, WW_LNK=str(lnk), WW_PYW=str(pyw), WW_TARGET=str(target), WW_DIR=str(HERE0), WW_ICON=str(icon))
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True, creationflags=0x08000000, timeout=20, env=env)

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
                self.say("윈도우를 켜면 위젯이 자동으로 떠요", "#00754A")
            else:
                (d / self.LNK_NAME).unlink(missing_ok=True)
                (d / self.OLD_LNK).unlink(missing_ok=True)
                self.say("자동 실행을 껐어요", "#5c5c5c")
        except Exception as e:
            K.log_line("업무위젯 자동실행 설정 오류 %r" % e)
            self.auto_var.set(self.autostart_on())
            self.say("자동 실행을 바꾸지 못했어요", "#c82014")
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
            self.say("여기 있어요!", "#00754A")
            k.SetEvent(K.wt.HANDLE(self.ev_ack))
        self.ticks += 1
        if self.ticks % K.GUARD_EVERY == 0 and not self.dragging:
            self.keep_visible()
        self.root.after(400, self.poll)

    def mainloop(self):
        threading.Thread(target=self.migrate_shortcuts, daemon=True).start()
        self.tray.add()                                      # 위젯이 떠 있는 동안에도 트레이 아이콘을 항상 보인다
        self.drain_tray()
        self.root.after(200, self.keep_visible)
        self.tick()
        self.poll()
        if self.dje_auto and is_daejeon() and K.configured():
            self.root.after(1_000, lambda: self.dje_watch(time.time() + 600))  # 켠 지 1초 뒤부터 DJE 메신저를 지켜보다 뜨면 자동 로그인 (체크했을 때만)
        self.root.after(30_000, self.sanctn_loop)           # 켠 지 30초 뒤 첫 읽기 (그 사이 업무포털 로그인을 마칠 시간)
        self.root.after(30_000, self.jeopsu_first)          # 같이 30초 뒤 — 결재대기 읽기가 끝나기를 기다렸다가 이어서 읽는다
        if UPD is not None:
            self.root.after(120_000, self.update_loop)
            v = UPD.just_updated(KIT)
            if v:
                self.root.after(1500, lambda: self.upd_popup("🎉 업데이트 완료", "새 버전 v%s 로 바뀌었어요" % v, "#00754A", 5000))
        if not K.configured():
            self.root.after(800, lambda: self.say("⚙ → 환경설정 (지역·인증서·암호)부터 해 주세요", "#c82014"))
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
