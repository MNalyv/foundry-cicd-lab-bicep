"""Evaluator = quality gate.

    python scripts/run_eval.py --env dev

Прогоняет агента по эталонному набору eval/golden_set.jsonl и считает долю
успешных ответов. Если она ниже min_pass_rate из config/<env>.json —
скрипт завершается с ошибкой, и pipeline останавливается (опора 2: gates).

Это намеренно простой «evaluator» на ключевых словах, чтобы был понятен принцип.
В реальных проектах используют evaluators из каталога Foundry
(релевантность, groundedness, безопасность и т. д.).

Агента вызывают по ИМЕНИ: какую версию он отдаст, решает version selector
endpoint (в dev — latest, в prod — закреплённая версия).
"""

import argparse
import json
import sys

from common import ROOT, load_agent, load_config, project_client, write_summary


def check(answer: str, case: dict) -> bool:
    text = answer.lower()
    has_expected = any(word.lower() in text for word in case.get("expected_any", []))
    has_forbidden = any(word.lower() in text for word in case.get("forbidden", []))
    return has_expected and not has_forbidden


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    parser.add_argument("--dataset", default=str(ROOT / "eval" / "golden_set.jsonl"))
    parser.add_argument("--min-pass-rate", type=float, default=None)
    args = parser.parse_args()

    cfg = load_config(args.env)
    agent = load_agent()
    threshold = args.min_pass_rate if args.min_pass_rate is not None else cfg["min_pass_rate"]

    with open(args.dataset, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    results = []
    with project_client(cfg["project_endpoint"]) as client:
        openai_client = client.get_openai_client()
        for case in cases:
            response = openai_client.responses.create(
                input=case["question"],
                extra_body={"agent_reference": {"name": agent["name"], "type": "agent_reference"}},
            )
            answer = response.output_text or ""
            ok = check(answer, case)
            results.append({"id": case["id"], "passed": ok, "answer": answer})
            print(f"{'PASS' if ok else 'FAIL'}  {case['id']:<14} {answer[:90]!r}")

    pass_rate = sum(r["passed"] for r in results) / len(results)
    verdict = "PASSED" if pass_rate >= threshold else "FAILED"
    print(f"\n[{args.env}] pass rate = {pass_rate:.0%}  (порог {threshold:.0%})  → {verdict}")

    reports = ROOT / "eval" / "reports"
    reports.mkdir(exist_ok=True)
    (reports / f"{args.env}.json").write_text(
        json.dumps({"pass_rate": pass_rate, "threshold": threshold, "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rows = "\n".join(f"| {r['id']} | {'✅' if r['passed'] else '❌'} |" for r in results)
    write_summary(
        f"### Quality gate ({args.env}): **{verdict}**\n"
        f"Pass rate **{pass_rate:.0%}**, порог {threshold:.0%}\n\n| Кейс | Результат |\n|---|---|\n{rows}"
    )

    if verdict == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
