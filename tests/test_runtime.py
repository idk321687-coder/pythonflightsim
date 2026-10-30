from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cesium_backend.runtime import read_dotenv_value


class RuntimeConfigTests(unittest.TestCase):
    def test_dotenv_reader_uses_only_the_requested_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / ".env"
            path.write_text("OTHER=value\nCESIUM_ION_TOKEN='scoped-token'\n", encoding="utf-8")
            self.assertEqual(read_dotenv_value(path, "CESIUM_ION_TOKEN"), "scoped-token")


if __name__ == "__main__":
    unittest.main()
