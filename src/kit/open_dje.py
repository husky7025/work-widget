# -*- coding: utf-8 -*-
"""DJE Talk(대전교육청 메신저) 로그인 — 실행 → [Login] → 인증서 비밀번호 → [확인].

위젯의 «DJE 메신저» 메뉴가 돌린다. 인증서 암호는 업무위젯이 쓰는 같은 keyring 항목에서 읽는다 (코드·로그에는 남기지 않는다).
창 안의 입력칸에 직접 값을 넣고(키보드 흉내 아님), 창 이름·칸·버튼이 모두 맞을 때만 입력한다. 로그인된 화면이면 아무것도 하지 않는다.
--dry-run 은 창·칸만 확인하고 암호를 꺼내지도 않는다.
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

import keyring

SERVICE = "DJE-Talk-cert"
ACCOUNT = "default"
EXE_NAME = "ucware_m.exe"
DIALOG_TITLE = "인증서 선택"
WAIT_SECONDS = 120

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
BM_CLICK = 0x00F5
LVM_GETSELECTEDCOUNT = 0x1032
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.EnumWindows.argtypes = [EnumProc, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumProc, wintypes.LPARAM]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
kernel32.OpenProcess.restype = wintypes.HANDLE
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                       wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
SMTO_ABORTIFHUNG = 0x0002


def send(hwnd, msg, wparam=0, lparam=0, timeout_ms=1500):
    """SendMessage 인데 창이 응답 없음이면 기다리지 않고 None 을 돌려준다. (DJE Talk 가 멈춰도 이 쪽이 같이 멈추지 않게)"""
    res = ctypes.c_size_t(0)
    ok = user32.SendMessageTimeoutW(hwnd, msg, wparam, lparam, SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(res))
    return res.value if ok else None


def text_of(hwnd):
    n = send(hwnd, WM_GETTEXTLENGTH)
    if not n:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    if send(hwnd, WM_GETTEXT, n + 1, ctypes.addressof(buf)) is None:
        return ""
    return buf.value


def class_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def exe_of(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def rect_of(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def find_dialog():
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and text_of(hwnd) == DIALOG_TITLE \
                and class_of(hwnd) == "#32770" and exe_of(hwnd) == EXE_NAME:
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def children(dlg):
    items = []

    def cb(hwnd, _):
        items.append((hwnd, class_of(hwnd), text_of(hwnd) if class_of(hwnd) != "Edit" else ""))
        return True

    user32.EnumChildWindows(dlg, EnumProc(cb), 0)
    return items


def inspect(dlg):
    """입력칸·확인 버튼·목록을 확인해 돌려준다. 하나라도 이상하면 None."""
    items = children(dlg)
    label = next((h for h, c, t in items if c == "Static" and "인증서 비밀번호" in t), None)
    ok = next((h for h, c, t in items if c == "Button" and t == "확인"), None)
    lst = next((h for h, c, t in items if c == "SysListView32"), None)
    edits = [h for h, c, t in items if c == "Edit"]
    if label is None or ok is None or lst is None or len(edits) != 1:
        return None
    edit = edits[0]
    lr, er = rect_of(label), rect_of(edit)
    same_row = abs((lr.top + lr.bottom) // 2 - (er.top + er.bottom) // 2) < 20
    if not (same_row and er.left >= lr.right - 5):
        return None
    return edit, ok, lst


WIDGET_SERVICE = "neis-automation"  # 업무위젯(나이스 키트)이 인증서 비밀번호를 두는 곳
WIDGET_CONFIG = os.path.join(os.environ.get("LOCALAPPDATA", ""), "neis-automation", "teacher_config.json")


def get_pw():
    """업무위젯과 같은 자격 증명 항목을 먼저 쓰고, 없으면 이 도구가 저장한 항목을 쓴다."""
    try:
        import json
        with open(WIDGET_CONFIG, encoding="utf-8") as f:
            name = json.load(f).get("cert_name")
        if name:
            pw = keyring.get_password(WIDGET_SERVICE, name)
            if pw:
                return pw
    except (OSError, ValueError):
        pass
    return keyring.get_password(SERVICE, ACCOUNT)


def find_exe():
    """DJE Talk 실행 파일 위치: 설치 기록(레지스트리) → 흔한 위치. (꺼져 있을 때만 부른다)"""
    try:
        import winreg
        base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for root, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                          (winreg.HKEY_LOCAL_MACHINE, base), (winreg.HKEY_CURRENT_USER, base)):
            try:
                key = winreg.OpenKey(root, sub)
            except OSError:
                continue
            with key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        with winreg.OpenKey(key, winreg.EnumKey(key, i)) as k:
                            if "dje talk" in winreg.QueryValueEx(k, "DisplayName")[0].lower():
                                exe = os.path.join(winreg.QueryValueEx(k, "InstallLocation")[0], "ucware_m.exe")
                                if os.path.isfile(exe):
                                    return exe
                    except OSError:
                        continue
    except ImportError:
        pass
    for b in (r"C:\UCWARE", r"D:\UCWARE", r"C:\Program Files\UCWARE", r"C:\Program Files (x86)\UCWARE"):
        exe = os.path.join(b, "Dje Talk", "ucware_m.exe")
        if os.path.isfile(exe):
            return exe
    return None


def is_daejeon():
    """위젯 환경설정의 지역이 대전(dje)일 때만 쓴다. 설정이 없으면 대전으로 본다(기본값)."""
    try:
        import json
        with open(WIDGET_CONFIG, encoding="utf-8") as f:
            url = json.load(f).get("neis_url") or ""
        return not url or "//dje." in url
    except (OSError, ValueError):
        return True


MAIN_CLASS = "TFM_ucware_main.UnicodeClass"
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
# 로그인 화면에서 [Login] 버튼 중심 위치 (메인 창 크기 385x550 기준 비율)
LOGIN_BTN_X, LOGIN_BTN_Y = 191 / 385, 332 / 550


def find_main(include_hidden=False):
    """메인 창. include_hidden 이면 트레이로 숨겨진 창도 찾는다."""
    found = []

    def cb(hwnd, _):
        if (include_hidden or user32.IsWindowVisible(hwnd)) and class_of(hwnd) == MAIN_CLASS and exe_of(hwnd) == EXE_NAME:
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


WS_VISIBLE = 0x10000000
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND


def shown_within(hwnd, top):
    """hwnd 부터 top 바로 아래까지 모두 '보이기' 상태인가. (top 자체가 트레이로 숨겨져 있어도 판단할 수 있게
    IsWindowVisible 대신 각 창의 WS_VISIBLE 만 본다)"""
    for _ in range(50):
        if not hwnd or hwnd == top:
            return hwnd == top
        if not (user32.GetWindowLongW(hwnd, -16) & WS_VISIBLE):
            return False
        hwnd = user32.GetParent(hwnd)
    return False


def on_login_screen(main_hwnd):
    """로그인 화면이면 True: '자동으로 로그인하기' 체크박스가 보인다. (메인 창이 트레이에 숨어 있어도 판단)"""
    for h, c, t in children(main_hwnd):
        if c.startswith("TOnUniCheckBox") and "자동으로 로그인" in t and shown_within(h, main_hwnd):
            return True
    return False


def bring_up(main_hwnd):
    """트레이에 숨은 로그인 창을 화면에 꺼낸다."""
    user32.ShowWindow(main_hwnd, 5)      # SW_SHOW
    if user32.IsIconic(main_hwnd):
        user32.ShowWindow(main_hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(main_hwnd)
    time.sleep(1.0)


LOGIN_ASPECT = 385 / 550   # 로그인 화면 창의 가로/세로 비율 (단추 위치를 잡은 기준)


def login_layout_ok(main_hwnd):
    """창 비율이 기준(385x550)과 많이 다르면 화면이 바뀐 것이다 — 엉뚱한 곳을 누르지 않도록 클릭하지 않는다."""
    r = rect_of(main_hwnd)
    w, h = r.right - r.left, r.bottom - r.top
    return h > 0 and abs(w / h - LOGIN_ASPECT) / LOGIN_ASPECT < 0.18


def click_login(main_hwnd):
    """[Login] 버튼 자리에 마우스 클릭 메시지를 보낸다. (PostMessage: 인증서 창이 떠도 멈추지 않음)
    화면 배율(125%·150% 등)이 달라도 맞도록, 이 스레드를 DJE Talk 창과 같은 DPI 방식으로 맞춘 채 좌표를 계산한다."""
    if user32.IsIconic(main_hwnd):          # 작업표시줄로 내려가 있으면 좌표가 없으니 먼저 펼친다
        user32.ShowWindow(main_hwnd, 9)      # SW_RESTORE
        time.sleep(1.0)
    old_ctx = None
    try:
        user32.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
        user32.GetWindowDpiAwarenessContext.argtypes = [wintypes.HWND]
        user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        old_ctx = user32.SetThreadDpiAwarenessContext(user32.GetWindowDpiAwarenessContext(main_hwnd))
    except (AttributeError, OSError):
        old_ctx = None
    try:
        r = rect_of(main_hwnd)
        px = int(r.left + (r.right - r.left) * LOGIN_BTN_X)
        py = int(r.top + (r.bottom - r.top) * LOGIN_BTN_Y)
        best, best_area = None, None
        for h, _c, _t in children(main_hwnd):
            if not user32.IsWindowVisible(h):
                continue
            cr = rect_of(h)
            if cr.left <= px < cr.right and cr.top <= py < cr.bottom:
                area = (cr.right - cr.left) * (cr.bottom - cr.top)
                if best is None or area < best_area:
                    best, best_area = h, area
        target = best or main_hwnd
        pt = wintypes.POINT(px, py)
        user32.ScreenToClient(target, ctypes.byref(pt))
        lp = (pt.y << 16) | (pt.x & 0xFFFF)
        user32.PostMessageW(target, WM_LBUTTONDOWN, 1, lp)
        time.sleep(0.08)
        user32.PostMessageW(target, WM_LBUTTONUP, 0, lp)
    finally:
        if old_ctx:
            user32.SetThreadDpiAwarenessContext(old_ctx)


def process_running():
    """ucware_m.exe 가 (창이 안 보여도) 떠 있는가."""
    try:
        import subprocess
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ucware_m.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=15, creationflags=0x08000000).stdout or ""
        return "ucware_m.exe" in out.lower()
    except Exception:
        return False


def start_and_open_cert_dialog():
    """DJE Talk 실행(꺼져 있으면) → 로그인 화면 → [Login] 클릭 → 인증서 창을 돌려준다."""
    dlg = find_dialog()
    if dlg:
        return dlg
    main_hwnd = find_main()
    if main_hwnd or process_running():
        # 이미 켜져 있거나 윈도우 시작과 함께 막 켜지는 중이다 — 두 번째로 띄우지 않고 창을 기다린다.
        # 로그인 화면이면(트레이에 숨어 있어도) 창을 꺼내 진행, 창이 6초 넘게 있는데 로그인 화면이 아니면 이미 로그인됨,
        # 20초 동안 메인 창 자체가 없으면 이미 로그인된 것으로 본다.
        t_end, first_seen, seen = time.time() + 20, None, False
        while time.time() < t_end:
            main_hwnd = find_main(include_hidden=True)
            if main_hwnd:
                first_seen = first_seen or time.time()
                if on_login_screen(main_hwnd):
                    if not user32.IsWindowVisible(main_hwnd):
                        print("트레이에 숨은 DJE Talk 로그인 창을 꺼냅니다.")
                        bring_up(main_hwnd)
                    seen = True
                    break
                if time.time() - first_seen > 6:
                    break
            time.sleep(0.2)
        if not seen:
            return "LOGGED_IN"
    else:
        exe = find_exe()
        if not exe:
            print("❌ DJE Talk 설치 위치를 찾지 못했습니다. DJE Talk가 설치돼 있는지 확인하세요.")
            return "NO_EXE"
        print("DJE Talk를 실행합니다.")
        import subprocess
        subprocess.Popen([exe], cwd=os.path.dirname(exe))
    deadline = time.time() + WAIT_SECONDS
    clicks, last_click = 0, 0.0
    while time.time() < deadline:
        dlg = find_dialog()
        if dlg:
            return dlg
        main_hwnd = find_main()
        if main_hwnd and clicks < 2 and on_login_screen(main_hwnd) and time.time() - last_click > 8:
            time.sleep(1.0)  # 화면이 다 그려질 때까지
            if not login_layout_ok(main_hwnd):
                print("❌ DJE Talk 로그인 화면 모양이 달라져 [Login] 단추 위치를 믿을 수 없습니다. 직접 [Login]을 눌러 주세요.")
                return "LAYOUT"
            print("[Login]을 누릅니다." if clicks == 0 else "[Login]을 한 번 더 누릅니다.")
            click_login(main_hwnd)
            clicks += 1
            last_click = time.time()
        time.sleep(0.2)
    # 시간 안에 인증서 창이 안 떴다 — 어느 단계에서 막혔는지 알려준다
    m = find_main()
    if m is None:
        print("❌ DJE Talk 창이 나타나지 않았습니다. 프로그램이 켜졌는지 작업표시줄·트레이를 확인하세요.")
    elif on_login_screen(m):
        print("❌ 로그인 화면은 보이는데 [Login]을 눌러도 인증서 창이 뜨지 않았습니다. 직접 [Login]을 눌러 보세요.")
    else:
        print("❌ 로그인 화면이 아니고 인증서 창도 없습니다. 이미 로그인됐거나 다른 화면일 수 있어요.")
    return "SHOWN"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)     # 위젯이 진행 문구를 바로바로 받게
    except Exception:
        pass
    dry = "--dry-run" in sys.argv
    print(f"DJE Talk 로그인을 시작합니다. (최대 {WAIT_SECONDS}초)")
    if not is_daejeon():
        print("❌ DJE 메신저는 대전교육청용입니다. ⚙ → 환경설정의 지역이 대전이 아닙니다.")
        return 6
    dlg = start_and_open_cert_dialog()
    if dlg == "NO_EXE":
        return 7
    if dlg == "LAYOUT":
        return 9
    if dlg == "SHOWN":          # 이유는 위에서 이미 알렸다
        return 1
    if dlg == "LOGGED_IN":
        print("✅ DJE 메신저에 로그인했습니다 (이미 로그인돼 있었어요)")
        return 0
    time.sleep(0.7)  # 창이 다 그려질 때까지

    parts = inspect(dlg)
    if not parts:
        print("❌ 창 모양이 예상과 다릅니다. 아무것도 입력하지 않고 멈춥니다.")
        return 2
    edit, ok, lst = parts

    if not send(lst, LVM_GETSELECTEDCOUNT):
        print("❌ 인증서가 선택되어 있지 않습니다. 선생님이 인증서를 고른 뒤 다시 실행해 주세요.")
        return 3

    if dry:
        has = bool(get_pw())
        print("[연습] 창·비밀번호 칸·확인 버튼·선택된 인증서를 모두 확인했습니다. 입력은 하지 않았습니다.")
        print(f"[연습] 저장된 인증서 비밀번호: {'있음' if has else '없음'} (값은 표시하지 않습니다)")
        return 0

    pw = get_pw()
    if not pw:
        print("❌ 저장된 비밀번호가 없습니다. ⚙ → 환경설정에서 인증서 암호를 저장해 주세요.")
        return 4

    buf = ctypes.create_unicode_buffer(pw)
    pw = None
    sent = send(edit, WM_SETTEXT, 0, ctypes.addressof(buf), timeout_ms=5000)
    ctypes.memset(buf, 0, ctypes.sizeof(buf))  # 메모리에서 바로 지움
    if sent is None:
        print("❌ 인증서 창이 응답하지 않아 비밀번호를 넣지 못했습니다. DJE Talk 창을 확인하세요.")
        return 8
    time.sleep(0.2)
    user32.PostMessageW(ok, BM_CLICK, 0, 0)  # Post: 로그인이 길어져도 이 쪽이 멈추지 않게
    # 로그인이 끝났는지 본다: 인증서 창이 닫히고 로그인 화면이 사라지면 성공
    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(0.7)
        m = find_main(include_hidden=True)
        if find_dialog() is None and m and not on_login_screen(m):
            print("✅ DJE 메신저에 로그인했습니다")
            return 0
    print("❌ 비밀번호는 넣었지만 로그인이 끝났는지 확인하지 못했습니다. DJE Talk 창을 확인하세요.")
    return 5


if __name__ == "__main__":
    sys.exit(main())
