# 업무 위젯 설치 — 묶음에 든 나이스 자동화 키트(공개, MIT, 고정 버전) 위에 업무 위젯(업무포털·나이스·내부기안·품의등록·결재대기)을 얹는다.
# 이 파일은 install_widget.cmd 가 부른다. 인증서 암호는 여기서 다루지 않는다 (마지막에 뜨는 설정 창에서 선생님이 직접 넣는다).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$app = Join-Path $here "app.zip"
$kit = Join-Path $env:LOCALAPPDATA "neis-automation-kit"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  업무 위젯 설치 (5~15분 걸릴 수 있어요. 창을 닫지 마세요)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

if (-not (Test-Path $app)) {
    Write-Host "  X 같이 받은 payload 폴더(app.zip)가 없습니다. 압축 파일을 «모두 풀어서» 그 폴더 안에서 다시 실행하세요." -ForegroundColor Red
    exit 1
}

# 1) 묶음에 든 키트+업무 위젯(시험한 버전으로 고정, build.py 가 만든다)을 푼다 — 인터넷에서 받지 않는다
Write-Host "[1/4] 설치 파일을 푸는 중..."
try {
    $t = Join-Path $env:TEMP "work-widget-x"
    if (Test-Path $t) { Remove-Item $t -Recurse -Force }
    Expand-Archive $app $t -Force
    if (-not (Test-Path (Join-Path $t "widget\install.ps1"))) { throw "app.zip 안에 widget\install.ps1 이 없습니다" }
} catch {
    Write-Host "  X 설치 파일을 풀지 못했습니다: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
Write-Host "  OK" -ForegroundColor Green

# 2) %LOCALAPPDATA%\neis-automation-kit 에 넣는다 (.venv·크롬 프로필은 건드리지 않는다)
Write-Host "[2/4] 위젯 파일을 넣는 중..."
robocopy $t $kit /E /XD .venv "chrome_profile*" /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Host "  X 파일을 복사하지 못했습니다 (robocopy $LASTEXITCODE)" -ForegroundColor Red; exit 1 }
Get-ChildItem $kit -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike "*\.venv\*" } | Unblock-File
Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  OK" -ForegroundColor Green

# 3) 키트 설치(파이썬·패키지·크롬 제어 도구) 후 설정 창 — 지역·인증서·암호는 선생님이 직접
Write-Host "[3/4] 키트 설치 + 설정 창 (파이썬·패키지 설치에 시간이 걸립니다)..."
$inst = Join-Path $kit "widget\install.ps1"
cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ""$inst"" < nul"
if ($LASTEXITCODE -ne 0) { Write-Host "  X 키트 설치가 끝나지 않았습니다." -ForegroundColor Red; exit 1 }

Write-Host "[4/4] 끝났습니다. 설정 창에서 [저장하고 위젯 켜기]를 누르면 위젯이 뜹니다." -ForegroundColor Green
Write-Host "      다음부터는 바탕화면의 «업무위젯» 를 더블클릭하세요."
