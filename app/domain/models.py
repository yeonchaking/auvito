"""Domain models for project, execution, and artifacts."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import ApprovalStatus, FailureClass, ProjectStatus, StageStatus


class Project(BaseModel):
    """Project entity."""

    id: UUID
    slug: str
    title_seed: str
    channel_name: str
    niche: str
    language: str = "ko-KR"
    target_duration_sec: int = 480
    status: ProjectStatus
    current_stage: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StageRun(BaseModel):
    """Stage execution record."""

    stage_run_id: str
    run_id: str
    stage_name: str
    attempt_no: int
    status: StageStatus
    requested_mode: Literal["skip", "resume", "overwrite"]

    execution_digest: str

    resumable: bool
    checkpoint_path: Optional[str] = None
    completed_units: int = 0
    total_units: Optional[int] = None

    output_contract_path: Optional[str] = None
    output_digest: Optional[str] = None
    reused_from_stage_run_id: Optional[str] = None
    resumed_from_stage_run_id: Optional[str] = None

    actual_cost_usd: Decimal = Decimal("0.00")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class AssetUnitState(BaseModel):
    """Asset unit state for Stage 5 checkpoint."""

    unit_id: str
    kind: Literal["image", "video"]
    status: Literal["PENDING", "SUBMITTED", "COMPLETED", "FAILED"]
    request_digest: str
    provider_job_id: Optional[str] = None
    asset_uri: Optional[str] = None
    asset_sha256: Optional[str] = None
    actual_cost_usd: Optional[Decimal] = None
    reserved_cost_usd: Optional[Decimal] = None
    retry_count: int = 0
    last_error: Optional[str] = None


class AssetStageCheckpoint(BaseModel):
    """Asset stage checkpoint for resumable execution."""

    checkpoint_version: str = "1.0"
    stage_run_id: str
    completed_unit_ids: list[str] = Field(default_factory=list)
    pending_job_ids: dict[str, str] = Field(default_factory=dict)
    units: dict[str, AssetUnitState] = Field(default_factory=dict)


class Artifact(BaseModel):
    """Artifact with provenance metadata."""

    artifact_id: str
    artifact_type: str
    run_id: str
    stage_run_id: str
    uri: str
    sha256: str
    parents: list[str] = Field(default_factory=list)
    source_kind: str
    generator: Optional[dict[str, Any]] = None
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    license_info: Optional[dict[str, Any]] = None
    created_at: datetime


class Approval(BaseModel):
    """Human-in-the-loop approval entity."""

    approval_id: str
    run_id: str
    checkpoint_name: str
    entity_type: str
    entity_ref: str
    status: ApprovalStatus
    estimated_incremental_cost_usd: Decimal
    summary: str
    diff_ref: Optional[str] = None
    reviewer: Optional[str] = None
    decision_comment: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
