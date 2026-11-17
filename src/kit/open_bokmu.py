# -*- coding: utf-8 -*-
"""나이스 인증서 자동 로그인 → 복무 > 개인근무상황관리 화면까지만 연다 (신청·상신 안 함).

로그인은 키트의 neis_session.py 가 한다 (인증서 암호는 keyring 에서 읽고, 이 파일은 암호를 다루지 않는다).
이미 로그인된 크롬(포트 9222)이 있으면 로그인은 건너뛴다.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import neis_session

HERE = Path(__file__).resolve().parent
PY = str(HERE / ".venv" / "Scripts" / "python.exe")
LOG = Path(tempfile.gettempdir()) / "neis_open_bokmu.log"
WAIT_S = 360


def start_login():
    LOG.write_text("", encoding="utf-8")
    f = open(LOG, "ab")
    # 크롬이 이 스크립트와 남남으로 살아 있도록 따로 띄운다
    flags = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen([PY, "-X", "utf8", str(HERE / "neis_session.py")], cwd=str(HERE), stdout=f, stderr=subprocess.STDOUT,
                     creationflags=flags, close_fds=True)
    t0 = time.time()
    while time.time() - t0 < WAIT_S:
        text = LOG.read_text(encoding="utf-8", errors="replace")
        if "READY port=" in text:
            return True
        if "❌" in text:      # 자동 로그인이 막힘. 키트가 5분 동안 직접 로그인을 기다리므로 계속 기다린다
            pass
        time.sleep(1)
    return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    if neis_session.port_answers():
        print("ℹ️  이미 열려 있는 나이스 크롬을 씁니다 (로그인 건너뜀)")
    else:
        print("🔐  나이스 로그인 중…")
        if not start_login():
            print(f"❌  로그인이 {WAIT_S}초 안에 끝나지 않았습니다. 로그: {LOG}")
            return 1
    r = subprocess.run([PY, "-X", "utf8", "neis_cdp.py", "open_bokmu_snippet.py"], cwd=str(HERE))
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
