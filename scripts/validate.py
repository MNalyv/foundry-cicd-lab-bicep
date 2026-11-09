"""Статические проверки без Azure (первый шаг CI на каждый pull request)."""

import json
import sys

from common import ROOT, load_agent


def main() -> None:
    errors = []

    agent = load_agent()
    if len(agent["instructions"]) < 50:
        errors.append("agent.yaml: инструкции подозрительно короткие")

    with open(ROOT / "eval" / "golden_set.jsonl", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            case = json.loads(line)
            for key in ("id", "question", "expected_any"):
                if key not in case:
                    errors.append(f"golden_set.jsonl, строка {n}: нет поля '{key}'")

    for env in ("dev", "prod"):
        cfg = json.loads((ROOT / "config" / f"{env}.json").read_text(encoding="utf-8"))
        if not 0 < cfg.get("min_pass_rate", 0) <= 1:
            errors.append(f"config/{env}.json: min_pass_rate должен быть в (0, 1]")

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("OK: agent.yaml, golden_set.jsonl и config/*.json корректны")


if __name__ == "__main__":
    main()
