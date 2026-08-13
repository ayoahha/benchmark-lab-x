"""Adaptateur HTML pur ; le port runtime reste l'unique frontière système."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol

from verify_v7 import (
    HTML_ADMISSION_RULE,
    AdapterIdentity,
    AxisExecutionRequest,
    AxisObservation,
    CandidatePermit,
    HarnessPreparation,
    TeardownObservation,
    admission_stage_proof,
)


@dataclass(frozen=True)
class CandidateExecutionObservation:
    session_id: str
    axis_id: str
    ready_receipt_ref: str
    artifact_digest: str
    artifact_proof_ref: str
    budget_digest: str
    environment_digest: str
    stage_proofs: tuple[tuple[str, str], ...]
    evaluation_completed: bool
    verdict: str | None
    budget_expired: bool
    watchdog_healthy: bool
    ambiguous: bool
    network_attempted: bool
    confinement_healthy: bool
    confinement_ambiguous: bool


class HtmlAxisRuntime(Protocol):
    def prepare(self) -> HarnessPreparation: ...

    def execute_candidate(
        self,
        permit: CandidatePermit,
    ) -> CandidateExecutionObservation: ...

    def teardown(self) -> TeardownObservation: ...


class HtmlRuntimePort(Protocol):
    def open_axis(self, request: AxisExecutionRequest) -> HtmlAxisRuntime: ...


_URL_ATTRIBUTES = frozenset({
    "action",
    "archive",
    "background",
    "cite",
    "classid",
    "codebase",
    "formaction",
    "href",
    "icon",
    "longdesc",
    "manifest",
    "ping",
    "poster",
    "profile",
    "src",
    "srcset",
    "usemap",
    "xlink:href",
})


def _remove_css_comments(value: str) -> str | None:
    output: list[str] = []
    cursor = 0
    while cursor < len(value):
        if value.startswith("/*", cursor):
            end = value.find("*/", cursor + 2)
            if end < 0:
                return None
            cursor = end + 2
            continue
        if value.startswith("*/", cursor):
            return None
        output.append(value[cursor])
        cursor += 1
    return "".join(output)


def _decode_css_escapes(value: str) -> str | None:
    output: list[str] = []
    cursor = 0
    while cursor < len(value):
        if value[cursor] != "\\":
            output.append(value[cursor])
            cursor += 1
            continue
        cursor += 1
        if cursor == len(value):
            return None
        match = re.match(r"[0-9a-fA-F]{1,6}", value[cursor:])
        if match is not None:
            token = match.group(0)
            codepoint = int(token, 16)
            if codepoint == 0 or codepoint > 0x10FFFF:
                return None
            output.append(chr(codepoint))
            cursor += len(token)
            if value.startswith("\r\n", cursor):
                cursor += 2
            elif cursor < len(value) and value[cursor].isspace():
                cursor += 1
            continue
        if value[cursor] in "\r\n\f":
            return None
        output.append(value[cursor])
        cursor += 1
    return "".join(output)


def _safe_css(value: str) -> bool:
    uncommented = _remove_css_comments(value)
    if uncommented is None:
        return False
    decoded = _decode_css_escapes(uncommented)
    if decoded is None:
        return False
    normalized = decoded.casefold()
    if "@import" in normalized or "image-set" in normalized:
        return False
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\burl\s*\(", normalized):
        end = normalized.find(")", match.end())
        if end < 0:
            return False
        content = normalized[match.end() : end].strip()
        if len(content) >= 2 and content[0] == content[-1] and content[0] in "\"'":
            content = content[1:-1].strip()
        if re.fullmatch(r"#[^\s()\"']+", content) is None:
            return False
        spans.append((match.start(), end + 1))
    remainder = normalized
    for start, end in reversed(spans):
        remainder = remainder[:start] + remainder[end:]
    return re.search(r"\burl\b", remainder) is None


def _safe_reference(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip()
    return re.fullmatch(r"#[^\s()\"']+", normalized) is not None


class _StaticHtmlAdmission(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.valid = True
        self.root_starts = 0
        self.root_ends = 0
        self._style_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.casefold()
        if name == "html":
            self.root_starts += 1
            if self.get_starttag_text() != "<html>":
                self.valid = False
        if name == "base":
            self.valid = False
        normalized_attrs = [(key.casefold(), value) for key, value in attrs]
        if any(key == "srcdoc" for key, _ in normalized_attrs):
            self.valid = False
        if name == "meta":
            for key, value in normalized_attrs:
                if key == "http-equiv" and value is not None and value.strip().casefold() == "refresh":
                    self.valid = False
        for key, value in normalized_attrs:
            if key == "style" and (value is None or not _safe_css(value)):
                self.valid = False
            if key in _URL_ATTRIBUTES or (key == "data" and name == "object"):
                if key == "srcset":
                    references = () if value is None else tuple(value.split(","))
                    if not references or not all(_safe_reference(item) for item in references):
                        self.valid = False
                elif not _safe_reference(value):
                    self.valid = False
        if name == "style":
            self._style_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if name == "html":
            self.root_ends += 1
        if name == "style":
            self._style_depth = max(0, self._style_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._style_depth and not _safe_css(data):
            self.valid = False


def _admit_html(candidate_bytes: bytes) -> bool:
    try:
        document = candidate_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    if not document.startswith("<html>") or not document.endswith("</html>"):
        return False
    parser = _StaticHtmlAdmission()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return False
    return parser.valid and parser.root_starts == 1 and parser.root_ends == 1


class HtmlAxisSession:
    def __init__(
        self,
        *,
        request: AxisExecutionRequest,
        runtime: HtmlAxisRuntime,
    ) -> None:
        self._request = request
        self._runtime = runtime

    def prepare(self) -> HarnessPreparation:
        return self._runtime.prepare()

    def inspect_and_execute(self, permit: CandidatePermit) -> AxisObservation:
        admission = permit.inspect(rule=HTML_ADMISSION_RULE, predicate=_admit_html)
        admission_proof_ref = admission_stage_proof(
            attestation=admission,
            ready=permit.ready_attestation,
        )
        if not admission.accepted:
            return AxisObservation(
                session_id=permit.ready_attestation.session_id,
                axis_id=self._request.axis_id,
                ready_receipt_ref=permit.ready_attestation.receipt_ref,
                artifact_digest=self._request.artifact_digest,
                artifact_proof_ref=self._request.artifact_proof_ref,
                budget_digest=self._request.budget_digest,
                environment_digest=self._request.environment_digest,
                admission_result=False,
                admission_attestation=admission,
                admission_stage_proof_ref=admission_proof_ref,
                stage_proofs=(),
                evaluation_completed=False,
                verdict=None,
                budget_expired=False,
                watchdog_healthy=True,
                ambiguous=False,
                network_attempted=False,
                confinement_healthy=True,
                confinement_ambiguous=False,
            )
        execution = self._runtime.execute_candidate(permit)
        return AxisObservation(
            session_id=execution.session_id,
            axis_id=execution.axis_id,
            ready_receipt_ref=execution.ready_receipt_ref,
            artifact_digest=execution.artifact_digest,
            artifact_proof_ref=execution.artifact_proof_ref,
            budget_digest=execution.budget_digest,
            environment_digest=execution.environment_digest,
            admission_result=True,
            admission_attestation=admission,
            admission_stage_proof_ref=admission_proof_ref,
            stage_proofs=execution.stage_proofs,
            evaluation_completed=execution.evaluation_completed,
            verdict=execution.verdict,
            budget_expired=execution.budget_expired,
            watchdog_healthy=execution.watchdog_healthy,
            ambiguous=execution.ambiguous,
            network_attempted=execution.network_attempted,
            confinement_healthy=execution.confinement_healthy,
            confinement_ambiguous=execution.confinement_ambiguous,
        )

    def teardown(self) -> TeardownObservation:
        return self._runtime.teardown()


@dataclass(frozen=True)
class HtmlModalityAdapter:
    identity: AdapterIdentity
    runtime_port: HtmlRuntimePort

    def open_axis(self, request: AxisExecutionRequest) -> HtmlAxisSession:
        return HtmlAxisSession(
            request=request,
            runtime=self.runtime_port.open_axis(request),
        )
