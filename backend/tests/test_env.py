from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.env import load_default_env_files, load_env_file  # noqa: E402


class EnvLoaderTests(unittest.TestCase):
    def test_load_env_file_applies_simple_values_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "OPENAI_API_KEY=from_file",
                        "export CIVIC_SETTING='quoted value'",
                        "INLINE=value # local comment",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["OPENAI_API_KEY"] = "from_process"
            self.addCleanup(os.environ.pop, "OPENAI_API_KEY", None)
            self.addCleanup(os.environ.pop, "CIVIC_SETTING", None)
            self.addCleanup(os.environ.pop, "INLINE", None)

            loaded = load_env_file(env_path)

            self.assertNotIn("OPENAI_API_KEY", loaded)
            self.assertEqual(os.environ["OPENAI_API_KEY"], "from_process")
            self.assertEqual(os.environ["CIVIC_SETTING"], "quoted value")
            self.assertEqual(os.environ["INLINE"], "value")

    def test_default_loader_accepts_emv_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".emv"
            env_path.write_text("OPENAI_API_KEY=from_emv\n", encoding="utf-8")
            original = os.environ.pop("OPENAI_API_KEY", None)
            self.addCleanup(_restore_env, "OPENAI_API_KEY", original)

            loaded = load_default_env_files(start_dir=tmp_dir)

            self.assertEqual(loaded["OPENAI_API_KEY"], "from_emv")
            self.assertEqual(os.environ["OPENAI_API_KEY"], "from_emv")


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
