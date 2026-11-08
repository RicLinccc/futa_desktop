$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceFile = Join-Path $projectDir "src\futa_pet.py"
$assetFile = Join-Path $projectDir "assets\futa-subject.png"
$girlAsset = Join-Path $projectDir "assets\pajama-girl.png"
$iconFile = Join-Path $projectDir "assets\futa.ico"
$distDir = Join-Path $projectDir "dist"
$buildDir = Join-Path $projectDir ".build"
$exeName = "福塔桌宠3.1"

New-Item -ItemType Directory -Force $distDir | Out-Null

$pyiArgs = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--windowed",
  "--name", $exeName,
  "--icon", $iconFile,
  "--add-data", "$assetFile;.",
  "--add-data", "$girlAsset;.",
  "--exclude-module", "numpy",
  "--exclude-module", "scipy",
  "--exclude-module", "pandas",
  "--exclude-module", "matplotlib",
  "--exclude-module", "IPython",
  "--exclude-module", "pytest",
  "--exclude-module", "setuptools",
  "--distpath", $distDir,
  "--workpath", $buildDir,
  "--specpath", $projectDir,
  $sourceFile
)

$built = $false
try {
  pyinstaller @pyiArgs
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
  $built = $true
}
finally {
  # 通知正在运行的桌宠：这次构建成功还是失败（彩蛋：编译联动）。
  try {
    $eventDir = [Environment]::GetFolderPath("LocalApplicationData")
    if (-not $eventDir) { $eventDir = Join-Path $env:USERPROFILE "AppData\Local" }
    $eventDir = Join-Path $eventDir "FutaDesktopPet"
    New-Item -ItemType Directory -Force $eventDir | Out-Null
    $payload = @{ ok = $built; time = (Get-Date).ToString("s") } | ConvertTo-Json -Compress
    Set-Content -LiteralPath (Join-Path $eventDir "build-event.json") -Value $payload -Encoding UTF8
  } catch {
    Write-Warning "无法写入构建事件：$_"
  }
}

Write-Host "Built: $(Join-Path $distDir ($exeName + '.exe'))"
