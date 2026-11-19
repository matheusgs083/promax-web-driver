@echo off
REM Baixa a grade de estoque do Cora por HTTP (sem navegador), de hoje, em todas as filiais.
REM So uma filial: testar_cora_estoque_http.bat --filial 747530   (Sousa 487570, Patos 747530, Sume 747548)
REM Outra data:    testar_cora_estoque_http.bat --data 2026-11-20
cd /d "%~dp0cora-web-driver"
"%~dp0venv\Scripts\python.exe" cli.py executar --operacao grade_estoque --job-id teste-estoque %*
pause
