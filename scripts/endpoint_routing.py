"""Version selector агента: посмотреть, защитить и закрепить версию (pin / rollback).

    python scripts/endpoint_routing.py show    --env prod
    python scripts/endpoint_routing.py protect --env prod   # если стоит latest — закрепить текущую
    python scripts/endpoint_routing.py pin     --env prod --version 3

Запросы идут в REST API проекта Foundry (data plane):
  GET   {project_endpoint}/agents/{name}?api-version=v1
  PATCH {project_endpoint}/agents/{name}?api-version=v1   (application/merge-patch+json)
Формат тела PATCH взят из документации Microsoft Foundry
(«Configure agent endpoint routing»): одно правило FixedRatio на 100% трафика.
"""

import argparse
import json
import sys

import requests

from common import credential, load_agent, load_config, set_output, write_summary

API_VERSION = "v1"
TOKEN_SCOPE = "https://ai.azure.com/.default"  # аудитория data plane Foundry


def _headers(content_type: str | None = None) -> dict:
    token = credential().get_token(TOKEN_SCOPE).token
    headers = {"Authorization": f"Bearer {token}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _agent_url(cfg: dict, agent_name: str) -> str:
    return f"{cfg['project_endpoint']}/agents/{agent_name}?api-version={API_VERSION}"


def get_state(cfg: dict, agent_name: str) -> dict:
    resp = requests.get(_agent_url(cfg, agent_name), headers=_headers(), timeout=60)
    if resp.status_code == 404:
        return {"exists": False, "pinned": None, "latest": None}
    resp.raise_for_status()
    data = resp.json()
    rules = (data.get("agent_endpoint") or {}).get("version_selector", {}).get("version_selection_rules") or []
    pinned = rules[0].get("agent_version") if rules else None
    latest = ((data.get("versions") or {}).get("latest") or {}).get("version")
    return {"exists": True, "pinned": pinned, "latest": latest}


def pin(cfg: dict, agent_name: str, version: str) -> None:
    body = {
        "agent_endpoint": {
            "version_selector": {
                "version_selection_rules": [
                    {"agent_version": str(version), "traffic_percentage": 100, "type": "FixedRatio"}
                ]
            },
            "protocol_configuration": {"responses": {}},
        }
    }
    resp = requests.patch(
        _agent_url(cfg, agent_name),
        headers=_headers("application/merge-patch+json"),
        data=json.dumps(body),
        timeout=60,
    )
    if resp.status_code == 403:
        sys.exit("403: у идентичности не хватает прав на изменение endpoint агента. См. README → «Роли».")
    resp.raise_for_status()
    print(f"[{cfg['environment']}] 100% трафика → версия {version}")
    write_summary(f"### Version selector ({cfg['environment']})\nPinned → версия **{version}**")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["show", "protect", "pin"])
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    parser.add_argument("--version")
    args = parser.parse_args()

    cfg = load_config(args.env)
    name = load_agent()["name"]
    state = get_state(cfg, name)

    if args.action == "show":
        mode = f"pinned → {state['pinned']}" if state["pinned"] else "always use latest"
        print(f"[{args.env}] exists={state['exists']}  selector: {mode}  latest={state['latest']}")
        set_output("pinned_version", state["pinned"] or "")
        set_output("latest_version", state["latest"] or "")

    elif args.action == "protect":
        # Важно для prod: по умолчанию стоит «Always use latest», и новая версия
        # сразу получила бы трафик. Сначала закрепляем то, что работает сейчас.
        if state["exists"] and not state["pinned"] and state["latest"]:
            pin(cfg, name, state["latest"])
        current = state["pinned"] or state["latest"] or ""
        print(f"[{args.env}] текущая рабочая версия: {current or 'нет (первый выпуск)'}")
        set_output("previous_version", current)

    elif args.action == "pin":
        if not args.version:
            sys.exit("Укажите --version")
        pin(cfg, name, args.version)


if __name__ == "__main__":
    main()
