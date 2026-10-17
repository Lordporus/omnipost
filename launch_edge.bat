@echo off
set "PROFILE_DIR=%USERPROFILE%\.omnipost\edge-profile"
if exist "%USERPROFILE%\.tweetytweets\edge-profile" (
    if not exist "%USERPROFILE%\.omnipost\edge-profile" (
        set "PROFILE_DIR=%USERPROFILE%\.tweetytweets\edge-profile"
    )
)
echo Starting Edge with Automation Profile at %PROFILE_DIR%...
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9444 --remote-allow-origins=* --user-data-dir="%PROFILE_DIR%" --new-window --window-size=1280,800 --window-position=50,50 --no-first-run --no-default-browser-check --disable-features=msEdgeStartupBoost "https://x.com/home"
