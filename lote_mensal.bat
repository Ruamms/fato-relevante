@echo off
rem Lote mensal do Scout: le os relatorios novos com IA local e publica no site.
rem Agendado no Agendador de Tarefas do Windows (dia 16 de cada mes, 22h).
rem Pre-requisito: Ollama rodando (inicia com o Windows por padrao).
setlocal
cd /d "%~dp0"

echo ============================================
echo  Scout - lote mensal de leituras por IA
echo  %date% %time%
echo ============================================

python -m uv run scout atualizar
rem modelo padrao (qwen2.5:14b): mais lento, porem mais confiavel - decisao de produto
python -m uv run scout ia-lote
if errorlevel 1 (
    echo Lote terminou com erros - veja leituras\_erros.txt. Leituras parciais serao publicadas.
)

git add leituras
git commit -m "Leituras mensais por IA (%date%)"
git push
if errorlevel 1 (
    echo Falha no git push - rode manualmente: git push
    pause
    exit /b 1
)

echo.
echo Leituras publicadas. O proximo build do site as exibe automaticamente.
exit /b 0
