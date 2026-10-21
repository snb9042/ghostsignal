# scripts/build-galileo-sdr-sim.ps1
param([string]$Src = "$HOME\galileo-sdr-sim")
if (-not (Test-Path $Src)) {
  git clone https://github.com/harshadms/galileo-sdr-sim.git $Src
}
Write-Host "galileo-sdr-sim uses CMake. From a MinGW/MSYS2 shell:"
Write-Host "  cd '$Src'; mkdir build; cd build; cmake .. -G 'MinGW Makefiles'; mingw32-make"
Write-Host "Then set:  `$env:GALILEO_SDR_SIM = '$Src\build\galileo-sdr-sim.exe'"
