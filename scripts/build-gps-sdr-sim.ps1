# scripts/build-gps-sdr-sim.ps1
param(
  [string]$Src = "$HOME\gps-sdr-sim",
  [int]$MotionSize = 36000      # 3600 s @ 10 Hz
)
if (-not (Test-Path $Src)) {
  git clone https://github.com/osqzss/gps-sdr-sim.git $Src
}
$gcc = (Get-Command gcc -ErrorAction SilentlyContinue)
if (-not $gcc) { throw "gcc not found on PATH (install mingw-w64 / use Git Bash toolchain)" }
$out = Join-Path $Src "gps-sdr-sim.exe"
& gcc "$Src\gpssim.c" -lm -O3 "-DUSER_MOTION_SIZE=$MotionSize" -o $out
Write-Host "Built: $out"
Write-Host "Set it with:  `$env:GPS_SDR_SIM = '$out'"
