@echo off
rem GhostSignal Galileo shim -> WSL usrp_galileo (see galileo_wsl_wrapper.py)
python "%~dp0galileo_wsl_wrapper.py" %*
