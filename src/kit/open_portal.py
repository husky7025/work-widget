# -*- coding: utf-8 -*-
"""업무포털 인증서 자동 로그인 → 업무포털 메인 화면까지만 연다 (에듀파인으로 넘어가지 않음, 신청·결재 안 함).

로그인은 키트의 edufine_common.login 이 한다 (인증서 암호는 keyring 에서 읽고, 이 파일은 암호를 다루지 않는다).
크롬은 위젯 전용(포트 9324, 프로필 chrome_profile_widget_edufine)을 쓴다 — 나이스 크롬(9222)과 겹치지 않는다.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))


def load_engine():
    spec = importlib.util.spec_from_file_location("wengine", HERE / "widget" / "바로가기_엔진.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    from playwright.sync_api import sync_playwright
    W = load_engine()
    import edufine_common as E
    site = "edufine"
    print("🔐  업무포털 로그인 중…", flush=True)
    W.ensure_chrome(site, minimized=False)
    with sync_playwright() as p:
        browser = W.connect_sync(p, W.SITES[site]["port"])
        ctx = browser.contexts[0]
        # 업무포털 탭을 쓴다. 없으면 빈 탭, 그것도 없으면 새 탭 (같은 크롬에 있는 나이스 탭은 건드리지 않는다)
        blank = ("about:blank", "chrome://newtab/", "chrome://new-tab-page/", "edge://newtab/")
        page = (next((pg for pg in ctx.pages if any(k in pg.url for k in W.SITES[site]["match"])), None)
                or next((pg for pg in ctx.pages if pg.url in blank), None)
                or ctx.new_page())
        page.set_default_timeout(30_000)
        page.on("dialog", E.on_dialog)
        E.grant_local_network(ctx)
        cfg, pw = W.cfg_and_pw()
        E.login(page, cfg["cert_name"], pw)      # 업무포털 → 인증서 → 암호. 막히면 손 로그인 기다리기까지 키트 그대로
        W.to_front_sync(page)
        if "bpm_man_mn00_001" in page.url:
            print("✅  업무포털 메인 화면을 열었습니다.", flush=True)
            return 0
        print("❌  로그인은 끝났지만 업무포털 메인 화면이 아닙니다. 크롬 창을 확인하세요.", flush=True)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        print("❌  " + msg, flush=True)
        sys.exit(1)
