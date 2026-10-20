@echo off
setlocal
title Team Mail Bot VPS Manager
set "VPS=root@45.136.254.62"
if not defined TEAM_MAIL_SSH_KNOWN_HOSTS set "TEAM_MAIL_SSH_KNOWN_HOSTS=%USERPROFILE%\.ssh\known_hosts"
if not exist "%TEAM_MAIL_SSH_KNOWN_HOSTS%" (
    echo SSH known_hosts file not found: "%TEAM_MAIL_SSH_KNOWN_HOSTS%"
    echo Set TEAM_MAIL_SSH_KNOWN_HOSTS to the known_hosts file for your Windows account.
    echo Example: set TEAM_MAIL_SSH_KNOWN_HOSTS=C:\Users\YourName\.ssh\known_hosts
    pause
    exit /b 1
)
set "SSH_USER_KNOWN_HOSTS_OPTION=UserKnownHostsFile=%TEAM_MAIL_SSH_KNOWN_HOSTS%"

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
echo 5. Pull latest code and update services
echo 6. View recent logs
echo 7. List GNU Screen sessions
echo 8. Open SSH shell
echo 9. Exit
echo.
choice /c 123456789 /n /m "Choose an action: "
if errorlevel 9 goto :eof
if errorlevel 8 goto :shell
if errorlevel 7 goto :screens
if errorlevel 6 goto :logs
if errorlevel 5 goto :update
if errorlevel 4 goto :restart
if errorlevel 3 goto :stop
if errorlevel 2 goto :start
if errorlevel 1 goto :status
goto :menu

:status
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes %VPS% "systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:start
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes %VPS% "systemctl start team-mail@bot.service team-mail@worker.service team-mail@web.service && systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:stop
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes %VPS% "systemctl stop team-mail@web.service team-mail@worker.service team-mail@bot.service && systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:restart
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes %VPS% "systemctl restart team-mail@bot.service team-mail@worker.service team-mail@web.service && systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:update
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes %VPS% "sudo -u team-mail git -C /opt/team-mail-bot pull --ff-only origin main && sudo -u team-mail /opt/team-mail-bot/.venv/bin/python -m pip install -r /opt/team-mail-bot/requirements.lock.txt && sudo -u team-mail /opt/team-mail-bot/.venv/bin/python -m pip install --no-deps -e /opt/team-mail-bot && sudo -u team-mail /opt/team-mail-bot/.venv/bin/team-mail init-db && systemctl restart team-mail@bot.service team-mail@worker.service team-mail@web.service && systemctl --no-pager --full status team-mail@bot.service team-mail@worker.service team-mail@web.service"
goto :done

:logs
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes %VPS% "tail -n 100 -- /opt/team-mail-bot/logs/bot.log /opt/team-mail-bot/logs/worker.log /opt/team-mail-bot/logs/web.log; journalctl -u team-mail@bot.service -u team-mail@worker.service -u team-mail@web.service -n 50 --no-pager"
goto :done

:screens
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes %VPS% "sudo -u team-mail screen -ls"
goto :done

:shell
ssh -o "%SSH_USER_KNOWN_HOSTS_OPTION%" -o StrictHostKeyChecking=yes -t %VPS%
goto :menu

:done
echo.
pause
goto :menu
