@echo off
set "PROFILE_DIR=C:\Users\Sachin\.tweetytweets\edge-profile"
del /f /q "%PROFILE_DIR%\Singleton*" 2>nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9444 --remote-allow-origins=* --user-data-dir="%PROFILE_DIR%" --new-window --window-size=1280,800 --window-position=50,50 --no-first-run --no-default-browser-check --disable-background-mode "https://x.com/home"
