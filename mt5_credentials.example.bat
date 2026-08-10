@echo off
REM Copy this file to mt5_credentials.local.bat (same folder) and fill in
REM your real MT5 account details. mt5_credentials.local.bat is listed in
REM .gitignore so your credentials never get committed to the repo.

set MT5_LOGIN=00000000
set MT5_PASSWORD=your-password
set MT5_SERVER=YourBroker-Server
set MT5_SYMBOL=XAUUSD.m

REM Leave commented out until you've watched the auto-loop run in
REM dry-run mode and are ready for it to place REAL pending orders with
REM real money. Uncomment only then:
REM set MT5_AUTOTRADE_ENABLED=1
