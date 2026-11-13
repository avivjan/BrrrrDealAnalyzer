"""The names of the Mercury token settings the backend reads from the hosting secrets, per workspace label
(tasks/todo/ConstructionAccountPerRehab.md). Names and presence only: nothing here ever reads a token's value into a
variable that leaves this module, and nothing here is ever a token.

One LLC = one Mercury workspace = one label (the suffix of its settings). The read token lets the app see balances
and transactions; the transfer token (a separate, write-capable token) lets it move money between that LLC's own
accounts.
"""

from __future__ import annotations

import os

READ_TOKEN_ENVIRONMENT_VARIABLE_PREFIX = "MERCURY_API_TOKEN"
TRANSFER_TOKEN_ENVIRONMENT_VARIABLE_PREFIX = "MERCURY_TRANSFER_API_TOKEN"
READ_TOKEN_ENVIRONMENT_VARIABLE_NAME_PATTERN = f"{READ_TOKEN_ENVIRONMENT_VARIABLE_PREFIX}_<LABEL>"
TRANSFER_TOKEN_ENVIRONMENT_VARIABLE_NAME_PATTERN = f"{TRANSFER_TOKEN_ENVIRONMENT_VARIABLE_PREFIX}_<LABEL>"
# The label of an unsuffixed read token (`MERCURY_API_TOKEN`), as `mercury_client.discover_tokens` names it.
DEFAULT_WORKSPACE_LABEL = "default"


def read_token_environment_variable_name(mercury_workspace_label: str) -> str:
    if mercury_workspace_label == DEFAULT_WORKSPACE_LABEL:
        return READ_TOKEN_ENVIRONMENT_VARIABLE_PREFIX
    return f"{READ_TOKEN_ENVIRONMENT_VARIABLE_PREFIX}_{mercury_workspace_label}"


def transfer_token_environment_variable_name(mercury_workspace_label: str) -> str:
    return f"{TRANSFER_TOKEN_ENVIRONMENT_VARIABLE_PREFIX}_{mercury_workspace_label}"


def workspace_has_a_transfer_token(mercury_workspace_label: str) -> bool:
    return bool((os.environ.get(transfer_token_environment_variable_name(mercury_workspace_label)) or "").strip())


def workspace_labels_with_a_transfer_token() -> list[str]:
    prefix = TRANSFER_TOKEN_ENVIRONMENT_VARIABLE_PREFIX + "_"
    return sorted(name[len(prefix):] for name, value in os.environ.items()
                  if name.startswith(prefix) and name[len(prefix):] and (value or "").strip())
