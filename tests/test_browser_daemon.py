from unittest.mock import patch, MagicMock
from scripts.browser_daemon import is_browser_running, ensure_browser_running


def test_is_browser_running_success():
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_open.return_value.__enter__.return_value = mock_resp
        assert is_browser_running(port=9444) is True


def test_is_browser_running_failure():
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        assert is_browser_running(port=9444) is False


def test_ensure_browser_running_already_active():
    with patch("scripts.browser_daemon.is_browser_running", return_value=True):
        assert ensure_browser_running() is True


def test_ensure_browser_running_spawns_process():
    with patch("scripts.browser_daemon.is_browser_running", side_effect=[False, True]), \
         patch("subprocess.Popen") as mock_popen:
        assert ensure_browser_running() is True
        mock_popen.assert_called_once()


def test_ensure_browser_running_linux_flags():
    # 1. Linux platform
    with patch("scripts.browser_daemon.is_browser_running", side_effect=[False, True]), \
         patch("sys.platform", "linux"), \
         patch("subprocess.Popen") as mock_popen, \
         patch("settings.get_browser_config", return_value={"headless": False}):
        assert ensure_browser_running() is True
        args = mock_popen.call_args[0][0]
        assert "--no-sandbox" in args
        assert "--disable-dev-shm-usage" in args
        assert "--disable-gpu" in args

    # 2. Docker environment variable
    with patch("scripts.browser_daemon.is_browser_running", side_effect=[False, True]), \
         patch("sys.platform", "win32"), \
         patch.dict("os.environ", {"IS_DOCKER": "1"}, clear=False), \
         patch("subprocess.Popen") as mock_popen, \
         patch("settings.get_browser_config", return_value={"headless": False}):
        assert ensure_browser_running() is True
        args = mock_popen.call_args[0][0]
        assert "--no-sandbox" in args
        assert "--disable-dev-shm-usage" in args
        assert "--disable-gpu" in args

    # 3. Headless mode
    with patch("scripts.browser_daemon.is_browser_running", side_effect=[False, True]), \
         patch("sys.platform", "win32"), \
         patch.dict("os.environ", {}, clear=True), \
         patch("subprocess.Popen") as mock_popen, \
         patch("settings.get_browser_config", return_value={"headless": True}):
        assert ensure_browser_running() is True
        args = mock_popen.call_args[0][0]
        assert "--headless=new" in args
        assert "--no-sandbox" in args
        assert "--disable-dev-shm-usage" in args
        assert "--disable-gpu" in args


def test_browser_daemon_appends_linux_flags():
    test_ensure_browser_running_linux_flags()

