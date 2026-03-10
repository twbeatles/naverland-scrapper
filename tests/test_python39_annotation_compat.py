import ast
import os
import sys
import unittest
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"


def _has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "__future__":
            continue
        if any(alias.name == "annotations" for alias in node.names):
            return True
    return False


def _annotation_contains_bitwise_union(node: Optional[ast.AST]) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return True
    for child in ast.iter_child_nodes(node):
        if _annotation_contains_bitwise_union(child):
            return True
    return False


def _module_uses_pep604_annotations(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and _annotation_contains_bitwise_union(node.annotation):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _annotation_contains_bitwise_union(node.returns):
                return True
            for arg in (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
            ):
                if _annotation_contains_bitwise_union(arg.annotation):
                    return True
            if _annotation_contains_bitwise_union(node.args.vararg.annotation if node.args.vararg else None):
                return True
            if _annotation_contains_bitwise_union(node.args.kwarg.annotation if node.args.kwarg else None):
                return True
    return False


class TestPython39AnnotationCompat(unittest.TestCase):
    def test_modules_with_pep604_annotations_postpone_evaluation(self):
        incompatible = []

        for path in SRC_ROOT.rglob("*.py"):
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
            if not _module_uses_pep604_annotations(tree):
                continue
            if _has_future_annotations(tree):
                continue
            incompatible.append(path.relative_to(ROOT).as_posix())

        self.assertEqual(
            incompatible,
            [],
            "Python 3.9 requires postponed evaluation for PEP 604 annotations: "
            + ", ".join(incompatible),
        )


if __name__ == "__main__":
    unittest.main()
