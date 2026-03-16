import os
import sqlite3
import tempfile
from unittest.mock import MagicMock

from beeref.fileio.scratch import (
    create_scratch_file,
    delete_scratch_file,
    derive_swp_path,
    derive_untitled_swp_path,
    list_recovery_files,
)


def test_derive_swp_path_deterministic(settings):
    path1 = derive_swp_path("/some/path/file.bee")
    path2 = derive_swp_path("/some/path/file.bee")
    assert path1 == path2


def test_derive_swp_path_different_for_different_files(settings):
    path1 = derive_swp_path("/some/path/file.bee")
    path2 = derive_swp_path("/other/path/file.bee")
    assert path1 != path2


def test_derive_swp_path_in_recovery_dir(settings):
    path = derive_swp_path("/some/path/file.bee")
    assert "recovery" in path
    assert path.endswith(".bee.swp")
    assert "file_" in os.path.basename(path)


def test_derive_untitled_swp_path(settings):
    path = derive_untitled_swp_path()
    assert "recovery" in path
    assert "untitled_" in os.path.basename(path)
    assert path.endswith(".bee.swp")


def test_create_scratch_file_copies_existing(settings):
    with tempfile.NamedTemporaryFile(suffix=".bee", delete=False) as f:
        f.write(b"test content 12345")
        original = f.name
    try:
        swp = create_scratch_file(original)
        assert os.path.exists(swp)
        with open(swp, "rb") as f:
            assert f.read() == b"test content 12345"
        os.remove(swp)
    finally:
        os.remove(original)


def test_create_scratch_file_reports_progress(settings):
    with tempfile.NamedTemporaryFile(suffix=".bee", delete=False) as f:
        f.write(b"x" * 1024)
        original = f.name
    try:
        worker = MagicMock()
        swp = create_scratch_file(original, worker=worker)
        worker.begin_processing.emit.assert_called_once_with(100)
        worker.progress.emit.assert_called()
        os.remove(swp)
    finally:
        os.remove(original)


def test_create_scratch_file_none_creates_empty_db(settings):
    swp = create_scratch_file(None)
    assert os.path.exists(swp)
    # Verify it's a valid sqlite db with the schema
    conn = sqlite3.connect(swp)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    assert "items" in table_names
    assert "sqlar" in table_names
    conn.close()
    os.remove(swp)


def test_delete_scratch_file(settings):
    with tempfile.NamedTemporaryFile(suffix=".bee.swp", delete=False) as f:
        path = f.name
    assert os.path.exists(path)
    delete_scratch_file(path)
    assert not os.path.exists(path)


def test_delete_scratch_file_nonexistent(settings):
    # Should not raise
    delete_scratch_file("/nonexistent/path.bee.swp")


def test_list_recovery_files(settings):
    recovery_dir = settings.get_recovery_dir()
    swp1 = os.path.join(recovery_dir, "test1.bee.swp")
    swp2 = os.path.join(recovery_dir, "test2.bee.swp")
    other = os.path.join(recovery_dir, "notaswp.txt")
    for path in (swp1, swp2, other):
        open(path, "w").close()

    files = list_recovery_files()
    assert len(files) == 2
    basenames = [os.path.basename(f) for f in files]
    assert "test1.bee.swp" in basenames
    assert "test2.bee.swp" in basenames


def test_list_recovery_files_empty(settings):
    files = list_recovery_files()
    assert files == []


def test_close_event_deletes_scratch_file(main_window, settings):
    """Closing the main window should delete the scratch file."""
    swp = create_scratch_file(None)
    main_window.view.scene._scratch_file = swp
    assert os.path.exists(swp)
    main_window.close()
    assert not os.path.exists(swp)


def test_clear_scene_deletes_scratch_file(view, settings):
    """Clearing the scene should delete the scratch file."""
    swp = create_scratch_file(None)
    view.scene._scratch_file = swp
    assert os.path.exists(swp)
    view.clear_scene()
    assert not os.path.exists(swp)
    assert view.scene._scratch_file is None
