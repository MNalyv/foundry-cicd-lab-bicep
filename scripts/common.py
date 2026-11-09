"""Общие функции для скриптов лаборатории.

Вход везде keyless: DefaultAzureCredential сам выбирает способ —
локально это `az login`, в GitHub Actions — токен, полученный через OIDC (azure/login).
"""

import json
import os
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_config(env: str) -> dict:
    path = ROOT / "config" / f"{env}.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if "<" in cfg["project_endpoint"]:
        sys.exit(
            f"[config] Заполните project_endpoint в {path.relative_to(ROOT)} "
            "(значение берётся из terraform output project_endpoints)."
        )
    return cfg


def load_agent() -> dict:
    data = yaml.safe_load((ROOT / "agent" / "agent.yaml").read_text(encoding="utf-8"))
    for field in ("name", "model", "instructions"):
        if not data.get(field):
            sys.exit(f"[agent.yaml] Не заполнено обязательное поле: {field}")
    return data


def credential():
    # Импорт внутри функции: validate.py работает и без пакетов Azure.
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def project_client(endpoint: str):
    # Data plane: работа ВНУТРИ проекта (нужна роль Foundry User).
    from azure.ai.projects import AIProjectClient

    return AIProjectClient(endpoint=endpoint, credential=credential())


def set_output(name: str, value) -> None:
    """Передать значение следующему шагу GitHub Actions (steps.<id>.outputs.<name>)."""
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def write_summary(markdown: str) -> None:
    """Показать текст на странице запуска pipeline (Job summary)."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")
