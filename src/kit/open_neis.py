# -*- coding: utf-8 -*-
"""나이스 인증서 자동 로그인 → 나이스 첫 화면(로그인된 상태)까지만 연다. 메뉴 이동·신청·상신은 하지 않는다.

업무포털·내부기안과 «같은 위젯 크롬»(포트 9324, 프로필 chrome_profile_widget_edufine)의 새 탭에서 연다.
로그인 동작은 키트의 neis_session.login 을 그대로 쓴다 (인증서 암호는 keyring 에서 읽고, 이 파일은 암호를 다루지 않는다).
끝나도 크롬을 닫지 않고, 이 프로그램도 바로 끝난다 (붙었다가 떨어지기만 한다).
"""
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

import importlib.util  # noqa: E402


def load_engine():
    spec = importlib.util.spec_from_file_location("wengine", HERE / "widget" / "바로가기_엔진.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def run():
    from playwright.async_api import async_playwright
    import neis_session as N
    W = load_engine()
    site = "edufine"
    cfg, pw = W.cfg_and_pw()
    print("🔐  나이스 로그인 중…", flush=True)
    W.ensure_chrome(site, minimized=False)
    async with async_playwright() as p:
        browser = await W.connect_async(p, W.SITES[site]["port"])
        ctx = browser.contexts[0]
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(cfg["neis_url"]))
        # 이미 로그인된 나이스 탭이 있으면 그대로 앞으로만 가져온다
        for pg in ctx.pages:
            if "neis" in pg.url and await N.is_logged_in(pg):
                await pg.bring_to_front()
                print("ℹ️  이미 열려 있는 나이스 창으로 이동했습니다", flush=True)
                return True
        try:
            await ctx.grant_permissions(["notifications"], origin=origin)
        except Exception:
            pass
        # 빈 탭이 있으면 쓰고, 없으면 새 탭 (업무포털 탭은 건드리지 않는다)
        page = next((pg for pg in ctx.pages if pg.url in ("about:blank", "chrome://newtab/", "chrome://new-tab-page/")), None) \
            or await ctx.new_page()
        await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        await N.login(page, {**cfg, "cert_name": cfg["cert_name"]}, pw)
        await N.close_notice(page)
        await page.bring_to_front()
        return True


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    try:
        asyncio.run(run())
    except BaseException as e:
        if isinstance(e, SystemExit):
            raise
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        print("❌  " + msg, flush=True)
        return 1
    print("✅  나이스 화면을 열었습니다 (로그인됨)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
