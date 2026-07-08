from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from generate.generate_tables import generate_friend_graph, generate_table_2, main


class TestNetworkGeneration(unittest.TestCase):
    def setUp(self) -> None:
        self.students = [f"S{i}" for i in range(1, 13)]

    def test_erdos_renyi_reciprocity_extremes(self) -> None:
        reciprocal = generate_friend_graph(
            self.students,
            random.Random(1),
            model="erdos-renyi",
            density=1.0,
            reciprocity=1.0,
        )
        directed = generate_friend_graph(
            self.students,
            random.Random(1),
            model="erdos-renyi",
            density=1.0,
            reciprocity=0.0,
        )
        for left in self.students:
            for right in reciprocal[left]:
                self.assertIn(left, reciprocal[right])
            for right in directed[left]:
                self.assertNotIn(left, directed[right])

    def test_all_models_are_reproducible_and_have_no_self_edges(self) -> None:
        for model in ("erdos-renyi", "watts-strogatz", "planted-communities"):
            kwargs = dict(
                model=model,
                density=0.3,
                reciprocity=0.4,
                communities=3,
                rewiring_probability=0.2,
            )
            first = generate_friend_graph(self.students, random.Random(7), **kwargs)
            second = generate_friend_graph(self.students, random.Random(7), **kwargs)
            self.assertEqual(first, second)
            self.assertTrue(any(first.values()))
            for student_id, friends in first.items():
                self.assertNotIn(student_id, friends)

    def test_course_rows_respect_top_k_for_structured_network(self) -> None:
        rows = generate_table_2(
            self.students,
            ["C1", "C2"],
            random.Random(4),
            top_k=3,
            score_min=1,
            score_max=5,
            network_model="planted-communities",
            network_density=0.7,
            network_reciprocity=0.5,
            network_communities=3,
        )
        counts: dict[tuple[str, str], int] = {}
        for row in rows:
            key = (row.student_id_a, row.course_id)
            counts[key] = counts.get(key, 0) + 1
            self.assertNotEqual(row.student_id_a, row.student_id_b)
        self.assertTrue(counts)
        self.assertLessEqual(max(counts.values()), 3)

    def test_erdos_renyi_density_is_close_to_requested_pair_density(self) -> None:
        students = [f"S{i}" for i in range(200)]
        graph = generate_friend_graph(
            students,
            random.Random(12),
            model="erdos-renyi",
            density=0.2,
            reciprocity=1.0,
        )
        directed_edges = sum(len(friends) for friends in graph.values())
        observed = directed_edges / (len(students) * (len(students) - 1))
        self.assertAlmostEqual(observed, 0.2, delta=0.02)

    def test_cli_writes_scenario_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out1 = root / "table1.csv"
            out2 = root / "table2.csv"
            out3 = root / "table3.csv"
            manifest = root / "scenario.json"
            args = [
                "generate_tables.py", "--students", "8", "--courses", "3",
                "--seed", "5", "--network-model", "erdos-renyi",
                "--network-density", "0.4", "--network-reciprocity", "0.7",
                "--out1", str(out1), "--out2", str(out2), "--out3", str(out3),
                "--out-manifest", str(manifest),
            ]
            with patch.object(sys, "argv", args):
                self.assertEqual(main(), 0)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["network_model"], "erdos-renyi")
            self.assertEqual(payload["seed"], 5)


if __name__ == "__main__":
    unittest.main()
