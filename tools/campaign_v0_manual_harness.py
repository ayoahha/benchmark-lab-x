from __future__ import annotations

from collections.abc import Mapping

from tools.campaign_v0_shared_core_adapter import (
    SLOTS,
    build_receipt,
    canonical_bytes,
)


HARNESS_SCHEMA = "campaign-v0-manual-harness/v1"
DESCRIPTOR_SCHEMA = "campaign-v0-command-descriptor/v1"
ISOLATED_WORKSPACE_PLACEHOLDER = "__ISOLATED_WORKSPACE__"
PROMPT_FILE_PLACEHOLDER = "__PROMPT_FILE__"
PROMPT_PLACEHOLDER = "__PROMPT__"

COMMAND_TEMPLATES = {
    "grok46_xai_build_oauth": {
        "argv": (
            "grok",
            "--model",
            "grok-4.6",
            "--reasoning-effort",
            "xhigh",
            "--permission-mode",
            "plan",
            "--sandbox",
            "read-only",
            "--disable-web-search",
            "--no-subagents",
            "--output-format",
            "plain",
            "--prompt-file",
            PROMPT_FILE_PLACEHOLDER,
        ),
        "workspace": ISOLATED_WORKSPACE_PLACEHOLDER,
    },
    "kimi_k3_cursor_cli": {
        "argv": (
            "agent",
            "--print",
            "--output-format",
            "text",
            "--mode",
            "ask",
            "--sandbox",
            "enabled",
            "--workspace",
            ISOLATED_WORKSPACE_PLACEHOLDER,
            "--model",
            "kimi-k3-max",
            PROMPT_PLACEHOLDER,
        ),
        "workspace": ISOLATED_WORKSPACE_PLACEHOLDER,
    },
}


class ManualHarnessError(ValueError):
    pass


def prepare_command_descriptor(configuration_id: str) -> dict[str, object]:
    if configuration_id not in COMMAND_TEMPLATES:
        raise ManualHarnessError("configuration outside locked panel")
    template = COMMAND_TEMPLATES[configuration_id]
    return {
        "argv": list(template["argv"]),
        "configuration_id": configuration_id,
        "schema_version": DESCRIPTOR_SCHEMA,
        "state": "REQUESTED",
        "workspace": template["workspace"],
    }


class ManualHarness:
    def __init__(self) -> None:
        self._receipt_bytes: list[bytes] = []
        self._content_addresses: list[str] = []
        self._recorded_slots: set[str] = set()

    @property
    def schema_version(self) -> str:
        return HARNESS_SCHEMA

    @property
    def receipts(self) -> tuple[bytes, ...]:
        return tuple(self._receipt_bytes)

    def prepare(self, configuration_id: str) -> dict[str, object]:
        return prepare_command_descriptor(configuration_id)

    def record_observation(
        self,
        configuration_id: str,
        supplied_observations: Mapping[str, object],
    ) -> bytes:
        if configuration_id not in SLOTS:
            raise ManualHarnessError("configuration outside locked panel")
        acquisition_id = SLOTS[configuration_id]
        if acquisition_id in self._recorded_slots:
            raise ManualHarnessError("immutable receipt slot already recorded")
        predecessor = self._content_addresses[-1] if self._content_addresses else None
        receipt = build_receipt(
            configuration_id,
            prepare_command_descriptor(configuration_id),
            supplied_observations,
            predecessor,
        )
        receipt_bytes = canonical_bytes(receipt)
        self._receipt_bytes.append(receipt_bytes)
        self._content_addresses.append(str(receipt["content_address"]["sha256"]))
        self._recorded_slots.add(acquisition_id)
        return receipt_bytes
