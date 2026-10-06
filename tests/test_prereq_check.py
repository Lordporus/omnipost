from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.prereq_check import check_prerequisites, guarantee_state_files


def test_check_python_version_valid():
    with patch("sys.version_info", (3, 12, 0, "final", 0)):
        res = check_prerequisites()
        assert res["python"]["ok"] is True
        assert "3.12" in res["python"]["version"]

    with patch("sys.version_info", (3, 9, 7, "final", 0)):
        res = check_prerequisites()
        assert res["python"]["ok"] is False


def test_check_git_available():
    with patch("shutil.which", return_value="/usr/bin/git"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="git version 2.39.2\n")
        res = check_prerequisites()
        assert res["git"]["ok"] is True
        assert "2.39" in res["git"]["version"]

    with patch("shutil.which", return_value=None):
        res = check_prerequisites()
        assert res["git"]["ok"] is False
        assert res["git"]["version"] == ""


def test_check_browser_detection():
    # Found via settings.find_chrome
    with patch("settings.find_chrome", return_value=Path("/usr/bin/google-chrome")):
        res = check_prerequisites()
        assert res["browser"]["ok"] is True
        assert "google-chrome" in res["browser"]["path"]

    # Found via shutil.which fallback
    with patch("settings.find_chrome", return_value=None), \
         patch("shutil.which", side_effect=lambda name: "/usr/bin/chromium" if name == "chromium" else None):
        res = check_prerequisites()
        assert res["browser"]["ok"] is True
        assert res["browser"]["path"] == "/usr/bin/chromium"

    # Not found
    with patch("settings.find_chrome", return_value=None), \
         patch("shutil.which", return_value=None):
        res = check_prerequisites()
        assert res["browser"]["ok"] is False
        assert res["browser"]["path"] == ""


def test_check_docker_detection():
    def mock_which(name: str):
        if name in ("docker", "docker-compose"):
            return f"/usr/bin/{name}"
        return None

    with patch("shutil.which", side_effect=mock_which):
        res = check_prerequisites()
        assert res["docker"]["ok"] is True
        assert res["docker"]["compose"] is True

    with patch("shutil.which", return_value=None):
        res = check_prerequisites()
        assert res["docker"]["ok"] is False
        assert res["docker"]["compose"] is False


def test_check_port_9444_status():
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        # Port is available
        mock_sock.bind.return_value = None
        res = check_prerequisites()
        assert res["port_9444"]["available"] is True

        # Port is in use
        mock_sock.bind.side_effect = OSError("Address already in use")
        res = check_prerequisites()
        assert res["port_9444"]["available"] is False


def test_check_ledger_atomic_write(tmp_path: Path):
    res = check_prerequisites(root=tmp_path)
    assert res["ledger_writable"]["ok"] is True
    # Temp test file should be cleaned up
    assert not (tmp_path / ".write_test.tmp").exists()

    # When directory write raises error
    with patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")):
        res = check_prerequisites(root=tmp_path)
        assert res["ledger_writable"]["ok"] is False


def test_guarantee_state_files_creates_defaults(tmp_path: Path):
    state_file = tmp_path / "state.json"
    env_file = tmp_path / ".env"
    assert not state_file.exists()
    assert not env_file.exists()

    guarantee_state_files(root=tmp_path)

    assert state_file.is_file()
    assert state_file.read_text(encoding="utf-8").strip() == "{}"
    assert env_file.is_file()
    assert env_file.read_text(encoding="utf-8") == ""

    # Check required directories
    for d in ("drafts", "swipe", "scratch"):
        assert (tmp_path / d).is_dir()


def test_guarantee_state_files_detects_directory_collision(tmp_path: Path):
    state_dir = tmp_path / "state.json"
    state_dir.mkdir()

    with pytest.raises(ValueError, match="state.json is a directory"):
        guarantee_state_files(root=tmp_path)

    state_dir.rmdir()
    env_dir = tmp_path / ".env"
    env_dir.mkdir()

    with pytest.raises(ValueError, match=r"\.env is a directory"):
        guarantee_state_files(root=tmp_path)


def test_check_prerequisites_full(tmp_path: Path):
    res = check_prerequisites(root=tmp_path)
    expected_keys = {
        "python",
        "git",
        "browser",
        "docker",
        "port_9444",
        "ledger_writable",
        "state_files_guaranteed",
    }
    assert expected_keys.issubset(res.keys())
    assert "ok" in res["python"]
    assert "ok" in res["git"]
    assert "ok" in res["browser"]
    assert "ok" in res["docker"]
    assert "available" in res["port_9444"]
    assert "ok" in res["ledger_writable"]
    assert "ok" in res["state_files_guaranteed"]


def test_doctor_healthcheck_success():
    from scripts.doctor import main as doctor_main
    with patch("sys.argv", ["doctor.py", "--healthcheck"]), \
         patch("scripts.doctor.check_python", return_value=("OK", "python 3.12")), \
         patch("scripts.doctor.check_deps", return_value=("OK", "deps")), \
         patch("scripts.doctor.check_config", return_value=("OK", "config")), \
         patch("scripts.doctor.check_chrome", return_value=("OK", "chrome")), \
         patch("scripts.doctor.check_dirs", return_value=("OK", "dirs")), \
         pytest.raises(SystemExit) as exc:
        doctor_main()
    assert exc.value.code == 0


def test_doctor_healthcheck_failure():
    from scripts.doctor import main as doctor_main
    with patch("sys.argv", ["doctor.py", "--healthcheck"]), \
         patch("scripts.doctor.check_python", return_value=("MISSING", "python 3.9")), \
         patch("scripts.doctor.check_deps", return_value=("OK", "deps")), \
         patch("scripts.doctor.check_config", return_value=("OK", "config")), \
         patch("scripts.doctor.check_chrome", return_value=("OK", "chrome")), \
         patch("scripts.doctor.check_dirs", return_value=("OK", "dirs")), \
         pytest.raises(SystemExit) as exc:
        doctor_main()
    assert exc.value.code == 1

