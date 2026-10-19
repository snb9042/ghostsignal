param([string]$Py = "py -3.12")
Write-Host "Creating .venv with $Py ..."
Invoke-Expression "$Py -m venv .venv"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1"
