import json

from w8_biayn.integrations.moonlight_aider_task_filenames import migrate_task, task_named_files


def test_task_named_files_uses_task_slug_for_editable_files(tmp_path):
    root = tmp_path / "topic" / "sample-task"
    files = task_named_files(root, {
        "task.h": "#pragma once\n",
        "task.cpp": "#include \"task.h\"\n",
        ".meta/config.json": "{\"files\": {\"solution\": [\"task.h\", \"task.cpp\"]}}\n",
        "CMakeLists.txt": "add_library(sample task.cpp)\n",
    })

    assert files["sample-task.h"] == "#pragma once\n"
    assert files["sample-task.cpp"] == "#include \"sample-task.h\"\n"
    assert "\"sample-task.h\", \"sample-task.cpp\"" in files[".meta/config.json"]
    assert "sample-task.cpp" in files["CMakeLists.txt"]


def test_migrate_task_uses_task_slug_for_editable_files(tmp_path):
    root = tmp_path / "topic" / "sample-task"
    (root / ".meta").mkdir(parents=True)
    (root / "task.h").write_text("#pragma once\n")
    (root / "task.cpp").write_text('#include "task.h"\n')
    (root / ".meta" / "example.cpp").write_text('#include "task.h"\n')
    (root / "task_visible_test.cpp").write_text('#include "task.h"\n')
    (root / ".meta" / "task_hidden_test.cpp").write_text('#include "task.h"\n')
    (root / "CMakeLists.txt").write_text("add_library(sample task.cpp)\n")
    (root / ".meta" / "config.json").write_text(
        json.dumps({"files": {"solution": ["task.h", "task.cpp"]}})
    )

    assert migrate_task(root)
    assert (root / "sample-task.h").is_file()
    assert (root / "sample-task.cpp").is_file()
    assert '#include "sample-task.h"' in (root / "task_visible_test.cpp").read_text()
    assert "sample-task.cpp" in (root / "CMakeLists.txt").read_text()
    assert json.loads((root / ".meta" / "config.json").read_text())["files"]["solution"] == [
        "sample-task.h",
        "sample-task.cpp",
    ]
    assert not migrate_task(root)
