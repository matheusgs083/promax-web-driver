@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
rem Login na mesma unidade do Edge (Patos); Sume exige troca de unidade.
set PROMAX_REPORT_UNIT=PATOS
echo.
echo === Testes ===
python -m pytest tests/promax_http -q
echo.
echo === Liga Entrega via HTTP (Patos e Sume), sem publicar ===
set PROMAX_HTTP_GRUPOS=liga_entrega
python cli.py relatorios --perfil liga_entrega --rotinas 030224_RESUMO_LIGA 030224_MOTORISTA_LIGA 030224_AJUDANTE_LIGA 031129_LIGA 031120_BOT 030237 --unidade 2210003 --unidade 2210004 --somente-baixar
echo CODIGO_SAIDA=%ERRORLEVEL%
pause
