# 西班牙语逐句精读视频工具包：安装（Windows）。双击 install_windows.bat，或在 PowerShell 里运行：
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1            # 基本安装：Supertonic 配音 + 4K 视频 + 自动核查（约 1 GB）
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1 -Qwen3     # 另装 Qwen3 真人感配音要的 PyTorch 等（再加约 2 GB）
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1 -Mirror    # 在国内：用清华 PyPI 镜像、npmmirror 浏览器镜像
#   ... -Python C:\路径\python.exe                                          # 指定 Python（默认自动找 3.12 → 3.11 → 3.13 → 3.10）
# 装好的东西都在本文件夹的 .venv\ 里；删掉 .venv\ 就是卸载。可以重复运行（已装好的会跳过）。
# 本文件必须保存为“UTF-8 带 BOM”（Windows PowerShell 5.1 才能正确读出中文）。
param([switch]$Qwen3, [switch]$Mirror, [string]$Python = '')
$ErrorActionPreference = 'Stop'
$Kit = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Kit
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONUTF8 = '1'

function Step($t) { Write-Host ''; Write-Host "==== $t ====" -ForegroundColor Cyan }
function Die($t) { Write-Host ''; Write-Host "安装失败：$t" -ForegroundColor Red; exit 1 }
function Run($exe, [string[]]$a, $err) { & $exe @a; if ($LASTEXITCODE -ne 0) { Die $err } }
function OkPy($cmd, [string[]]$pre) {
  try { & $cmd @pre -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)' 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

Step '1/6 找 Python（需要 3.10–3.13，推荐 3.12）'
$py = $null; $pre = @()
if ($Python) {
  if (-not (OkPy $Python @())) { Die "$Python 不是 3.10–3.13 的 Python" }
  $py = $Python
} else {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in '-3.12', '-3.11', '-3.13', '-3.10') { if (OkPy 'py' @($v)) { $py = 'py'; $pre = @($v); break } }
  }
  if (-not $py -and (Get-Command python -ErrorAction SilentlyContinue)) { if (OkPy 'python' @()) { $py = 'python' } }
}
if (-not $py) {
  Die '没找到 Python 3.10–3.13。请到 https://www.python.org/downloads/windows/ 下载 Python 3.12 安装包，安装时勾选 “Add python.exe to PATH”，装好后重新运行本脚本。'
}
& $py @pre -V

Step '2/6 建虚拟环境 .venv'
$vpy = Join-Path $Kit '.venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) { Run $py ($pre + @('-m', 'venv', (Join-Path $Kit '.venv'))) '建虚拟环境失败' }
$pipx = @()
if ($Mirror) {
  $pipx = @('-i', 'https://pypi.tuna.tsinghua.edu.cn/simple')
  $env:PLAYWRIGHT_DOWNLOAD_HOST = 'https://npmmirror.com/mirrors/playwright'
}
Run $vpy (@('-m', 'pip', 'install', '--upgrade', 'pip', '-q') + $pipx) 'pip 升级失败（网络？在国内可加 -Mirror）'

Step '3/6 安装 Python 包（西班牙语\kit\requirements.txt）'
$req = Join-Path $Kit '西班牙语\kit\requirements.txt'
Run $vpy (@('-m', 'pip', 'install', '-r', $req) + $pipx) '安装 Python 包失败（网络？在国内可加 -Mirror）'

Step '4/6 安装截图用的浏览器（Chromium，约 150 MB）'
$browserOk = $true
& $vpy -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
  $browserOk = $false
  Write-Host '浏览器下载失败（网络？在国内可加 -Mirror；加了 -Mirror 仍失败就去掉它再试）。先把其余部分装完、做完自检，最后再说怎么补。' -ForegroundColor Yellow
}

if ($Qwen3) {
  Step '5/6 安装 Qwen3 配音要的 PyTorch 等（约 2 GB）'
  Run $vpy (@('-m', 'pip', 'install', 'torch', 'torchaudio') + $pipx) 'PyTorch 安装失败（网络？在国内可加 -Mirror）'
  Run $vpy (@('-m', 'pip', 'install', '-r', (Join-Path $Kit '西班牙语\kit\requirements-qwen3.txt')) + $pipx) 'Qwen3 依赖安装失败'
  Run $vpy (@('-m', 'pip', 'install', '--no-deps', 'qwen-tts==0.1.1') + $pipx) 'qwen-tts 安装失败'
  if (-not (Test-Path (Join-Path $Kit '西班牙语\models\qwen3-base\model.safetensors'))) {
    if (Get-ChildItem -Path $Kit -Filter 'qwen3-tts-1.7b-base.zip.0*' -ErrorAction SilentlyContinue) {
      Run $vpy @((Join-Path $Kit '西班牙语\tools\join_parts.py'), $Kit) 'Qwen3 模型分卷解压失败（看上面的说明）'
    } else {
      Write-Host '还差 Qwen3 模型：从 Release 下载 qwen3-tts-1.7b-base.zip.001、.002 …（和 SHA256SUMS.txt）放进本文件夹，'
      Write-Host "再运行：$vpy 西班牙语\tools\join_parts.py"
    }
  }
} else {
  Step '5/6 Qwen3 配音：没选（要用的话重新运行，加 -Qwen3）'
}

Step '6/6 检查 ffmpeg 并自检'
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
  Write-Host '还没有 ffmpeg（生成视频要用）。安装方法（任选一种）：' -ForegroundColor Yellow
  Write-Host '  ① 在 PowerShell 里运行：winget install --id Gyan.FFmpeg -e   （装好后关掉窗口重新打开）'
  Write-Host '  ② 到 https://www.gyan.dev/ffmpeg/builds/ 下载 ffmpeg-release-essentials.zip，解压后把里面的 bin 文件夹加到系统环境变量 PATH'
  Write-Host '装好后重新运行本脚本自检。'
}
& $vpy -X utf8 (Join-Path $Kit '西班牙语\tools\batch.py') --check
if ($LASTEXITCODE -ne 0) {
  Write-Host ''
  if (-not $browserOk) { Write-Host '截图用的浏览器没下载下来：换个网络（或加 / 去掉 -Mirror）后重新运行安装。' -ForegroundColor Yellow }
  Write-Host '自检没有全部通过：按上面的提示处理后，重新运行安装（已装好的会跳过）。' -ForegroundColor Yellow
  exit 1
}
Write-Host ''
Write-Host '安装完成。生成示例视频：在本文件夹打开命令提示符，运行  生成视频.bat es01 --voice supertonic3_M1F5_25' -ForegroundColor Green
Write-Host '详细用法见 使用说明.md'
