import ast
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NoDependenciesTest(unittest.TestCase):
    ##= docs/requirements/user-policies.md#fm-pol-20
    ##= type=test
    ## At runtime, the module MUST NOT need Python packages other than Synapse and the standard library.
    def test_no_dependencies(self):
        for path in (ROOT / "synapse_user_policies").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    top = name.split(".")[0]
                    self.assertTrue(
                        top in sys.stdlib_module_names or top.startswith("synapse"),
                        f"{path.name} imports non-stdlib {name}",
                    )
        if tomllib is None:
            self.skipTest("tomllib needs Python 3.11+, pyproject check skipped")
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertEqual(project["dependencies"], [])
