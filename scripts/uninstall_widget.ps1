# 업무 위젯 삭제 — 터미널 없이 확인 창으로 진행한다 (위젯_삭제.cmd 가 부른다)
Add-Type -AssemblyName System.Windows.Forms
$kit = Join-Path $env:LOCALAPPDATA "neis-automation-kit"
$cfg = Join-Path $env:LOCALAPPDATA "neis-automation"
$msg = "업무 위젯을 이 컴퓨터에서 지웁니다.`n`n지워지는 것`n · 위젯·설치된 도구 폴더`n · 바탕화면·시작프로그램의 «업무위젯»`n · 저장해 둔 인증서 설정과 인증서 암호 (Windows 자격 증명 관리자)`n · 위젯용 크롬 로그인 기록`n`n안 지워지는 것`n · 평소 쓰는 크롬, 인증서 파일, 파이썬`n`n지울까요?"
$r = [Windows.Forms.MessageBox]::Show($msg, "업무 위젯 삭제", "YesNo", "Question")
if ($r -ne "Yes") { exit 0 }
$log = @()
try {
  # 1) 켜져 있는 위젯·위젯용 크롬 끄기 (키트 폴더나 위젯용 프로필을 쓰는 것만)
  Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and ($_.CommandLine -like "*neis-automation-kit*" -or $_.CommandLine -like "*neis-automation\chrome_profile*")
  } | ForEach-Object { if ($_.ProcessId -ne $PID) { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }
  Start-Sleep 2
  # 2) 바로가기 — 이 위젯을 가리키는 것만
  $sh = New-Object -ComObject WScript.Shell
  $dirs = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Startup"), [Environment]::GetFolderPath("CommonDesktopDirectory"))
  foreach ($d in $dirs) {
    foreach ($nm in @("업무위젯.lnk", "나이스 에듀파인 바로가기.lnk")) {
      $l = Join-Path $d $nm
      if (Test-Path $l) {
        $s = $sh.CreateShortcut($l)
        if ("$($s.Arguments) $($s.TargetPath)" -like "*neis-automation-kit*") { Remove-Item $l -Force -ErrorAction SilentlyContinue; $log += "바로가기 삭제" }
      }
    }
  }
  # 3) 저장된 인증서 암호 (keyring 서비스 이름 neis-automation)
  cmdkey /list 2>$null | Select-String "Target:\s*(.*neis-automation.*)$" | ForEach-Object {
    $t = $_.Matches[0].Groups[1].Value.Trim(); cmdkey /delete:"$t" | Out-Null; $log += "암호 삭제"
  }
  # 4) 폴더
  foreach ($p in @($kit, $cfg, "$kit-update-backup")) { if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction Stop; $log += "폴더 삭제" } }
  [Windows.Forms.MessageBox]::Show("지웠습니다.`n(설치 묶음을 풀어 둔 폴더는 직접 지우셔도 됩니다)", "업무 위젯 삭제", "OK", "Information") | Out-Null
} catch {
  [Windows.Forms.MessageBox]::Show("일부를 지우지 못했습니다. 컴퓨터를 다시 켠 뒤 한 번 더 실행해 보세요.`n`n$($_.Exception.Message)", "업무 위젯 삭제", "OK", "Warning") | Out-Null
}
