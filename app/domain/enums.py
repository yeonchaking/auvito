"""Domain enumerations."""

from enum import Enum


class ProjectStatus(str, Enum):
    """Project status enumeration."""

    CREATED = "created"
    BENCHMARK_READY = "benchmark_ready"
    SCRIPT_READY = "script_ready"
    SCRIPT_APPROVED = "script_approved"
    VOICE_READY = "voice_ready"
    STORYBOARD_READY = "storyboard_ready"
    STORYBOARD_APPROVED = "storyboard_approved"
    ASSETS_READY = "assets_ready"
    RENDER_READY = "render_ready"
    THUMBNAIL_READY = "thumbnail_ready"
    RENDER_APPROVED = "render_approved"
    DONE = "done"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"


class StageStatus(str, Enum):
    """Stage execution status enumeration."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class FailureClass(str, Enum):
    """Failure classification enumeration."""

    TRANSIENT_PROVIDER = "TRANSIENT_PROVIDER"
    ASYNC_JOB_TIMEOUT = "ASYNC_JOB_TIMEOUT"
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    LOCAL_TOOL_TRANSIENT = "LOCAL_TOOL_TRANSIENT"
    LOCAL_TOOL_FATAL = "LOCAL_TOOL_FATAL"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    PARTIAL_BATCH = "PARTIAL_BATCH"


class StageName(str, Enum):
    """Stage name enumeration."""

    INTAKE = "intake"
    BENCHMARK = "benchmark"
    SCRIPT = "script"
    VOICE = "voice"
    STORYBOARD = "storyboard"
    ASSETS = "assets"
    RENDER = "render"
    THUMBNAIL = "thumbnail"


class ApprovalStatus(str, Enum):
    """Approval status enumeration."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
