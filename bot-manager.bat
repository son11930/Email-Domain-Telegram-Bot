@echo off
setlocal
title Team Mail Bot VPS Manager
set "VPS=root@45.136.254.62"

:menu
cls
echo ========================================
echo       Team Mail Bot VPS Manager
echo       %VPS%
echo ========================================
echo 1. Check all services
echo 2. Start bot, worker and web
echo 3. Stop bot, worker and web
echo 4. Restart bot, worker and web
echo 5. View recent logs
echo 6. List GNU Screen sessions
echo 7. Open SSH shell
echo 8. Exit
echo.
choice /c 12345678 /n /m "Choose an action: "
if errorlevel 8 goto :eof
if errorlevel 7 goto :shell
if errorlevel 6 goto :screens
if errorlevel 5 goto :logs
if errorlevel 4 goto :restart
if errorlevel 3 goto :stop
if errorlevel 2 goto :start
if errorlevel 1 goto :status
goto :menu

:status
ssh %VPS% "systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:start
ssh %VPS% "systemctl start team-mail@bot.service team-mail@worker.service team-mail@web.service && systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:stop
ssh %VPS% "systemctl stop team-mail@web.service team-mail@worker.service team-mail@bot.service && systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:restart
ssh %VPS% "systemctl restart team-mail@bot.service team-mail@worker.service team-mail@web.service && systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:logs
ssh %VPS% "journalctl -u team-mail@bot.service -u team-mail@worker.service -u team-mail@web.service -n 100 --no-pager"
goto :done

:screens
ssh -t %VPS% "screen -ls"
goto :done

:shell
ssh -t %VPS%
goto :menu

:done
echo.
pause
goto :menu
