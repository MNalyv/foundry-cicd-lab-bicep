"""Создать новую версию агента в проекте окружения по agent/agent.yaml.

    python scripts/deploy_agent.py --env dev

Версия агента неизменяема: если определение изменилось, Foundry создаёт
новую версию, старые остаются (к ним можно откатиться).
"""

import argparse

from azure.ai.projects.models import PromptAgentDefinition

from common import load_agent, load_config, project_client, set_output, write_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    args = parser.parse_args()

    cfg = load_config(args.env)
    agent = load_agent()

    with project_client(cfg["project_endpoint"]) as client:
        created = client.agents.create_version(
            agent_name=agent["name"],
            definition=PromptAgentDefinition(
                model=agent["model"],
                instructions=agent["instructions"],
            ),
        )

    print(f"[{args.env}] Агент '{created.name}', версия {created.version}")
    set_output("agent_version", created.version)
    write_summary(f"### Развёртывание ({args.env})\nАгент `{created.name}` → версия **{created.version}**")


if __name__ == "__main__":
    main()
