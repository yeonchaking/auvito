# Stage 0 & Stage 1 Implementation Guide

## Overview

This document describes the implementation of Stage 0 (Project Intake) and Stage 1 (Benchmark Analysis) for the YouTube content production pipeline.

## Stage 0: IntakeStage

### Purpose
Creates and initializes a project workspace with all required directory structures and metadata files.

### Location
`app/stages/stage0_intake.py`

### Implementation Details

#### Class: `IntakeStage`

**Inherits from**: `BaseStage[Project, Project]`

**Key Methods**:

1. `async execute(project: Project) -> Project`
   - Main entry point for stage execution
   - Takes a Project model and initializes workspace
   - Returns the same project after setup

2. `async _create_directory_structure(project_workspace: Path)`
   - Creates all required subdirectories
   - Follows design specification exactly

#### Workspace Structure Created

```
workspace/projects/{slug}/
├── project.json              # Derived snapshot (read-only)
├── config_snapshot.json      # Settings snapshot at creation time
├── cost_summary.json         # Initial cost tracking (all zeros)
├── logs/
│   └── llm_calls/           # LLM request/response logs
├── approvals/                # Approval checkpoint records
├── provenance/               # Artifact origin tracking
├── 00_intake/
├── 01_benchmark/
├── 02_script/
├── 03_voice/
│   └── transcripts/
├── 04_storyboard/
├── 05_assets/
│   ├── images/
│   └── videos/
├── 06_render/
├── 07_thumbnail/
└── 08_publish/
```

#### JSON Files Created

1. **project.json** (Derived snapshot, read-only)
   ```json
   {
     "id": "uuid",
     "slug": "project-slug",
     "title_seed": "Project Title",
     "channel_name": "Channel Name",
     "niche": "Content Niche",
     "language": "ko-KR",
     "target_duration_sec": 480,
     "status": "created",
     "current_stage": null,
     "created_at": "2026-03-28T...",
     "updated_at": "2026-03-28T..."
   }
   ```

2. **config_snapshot.json**
   ```json
   {
     "language": "ko-KR",
     "target_duration_sec": 480,
     "niche": "Content Niche",
     "snapshot_created_at": "2026-03-28T..."
   }
   ```

3. **cost_summary.json**
   ```json
   {
     "run_id": "uuid",
     "total_cost_usd": "0.00",
     "by_stage": {
       "intake": "0.00",
       "benchmark": "0.00",
       "script": "0.00",
       "voice": "0.00",
       "storyboard": "0.00",
       "assets": "0.00",
       "render": "0.00",
       "thumbnail": "0.00",
       "publish": "0.00"
     },
     "created_at": "2026-03-28T..."
   }
   ```

### Usage Example

```python
from app.stages.stage0_intake import IntakeStage
from app.domain.models import Project
from app.storage.sqlite import Database

# Initialize
db = Database("workspace/pipeline.db")
await db.init()
stage = IntakeStage(db, "workspace")

# Execute
project = await stage.execute(project_instance)
```

### Database Registration

The stage registers the project in SQLite immediately:
- Ensures atomic project creation
- Provides recovery point if subsequent stages fail
- Enables status tracking and querying

---

## Stage 1: BenchmarkStage

### Purpose
Analyzes competitor YouTube videos to extract content patterns, hooks, CTR strategies, and keyword recommendations.

### Location
`app/stages/stage1_benchmark.py`

### Implementation Details

#### Classes

##### `BenchmarkStageInput`
Container for benchmark stage input parameters:
- `project`: Project instance to analyze for
- `search_keywords`: List of YouTube search keywords
- `workspace_root`: Root workspace directory
- `youtube_api_key`: YouTube Data API key
- `anthropic_api_key`: Optional Anthropic API key for LLM analysis

##### `BenchmarkStage`
Main stage implementation inheriting from `BaseStage[BenchmarkStageInput, BenchmarkReport]`

**Key Methods**:

1. `async execute(input_data: BenchmarkStageInput) -> BenchmarkReport`
   - Orchestrates entire benchmark analysis
   - Calls ResearchProvider to collect and analyze videos
   - Generates three output files
   - Saves provenance information

2. `_compute_idempotency_key(project_id, keywords) -> str`
   - Creates reproducible hash from project + keywords
   - Enables caching and skip modes

3. `_format_report_markdown(report: BenchmarkReport) -> str`
   - Converts BenchmarkReport to human-readable markdown
   - Includes patterns, keywords, competitor analysis, insights

4. `_extract_long_tail_keywords(report: BenchmarkReport) -> list[str]`
   - Extracts multi-word phrases from analysis patterns
   - Returns up to 10 long-tail keywords

5. `async _save_provenance(...)`
   - Records request, cost estimate, and output metadata
   - Enables audit trail and debugging

#### Output Files

All files saved to `workspace/projects/{slug}/01_benchmark/`

1. **benchmark_report.json**
   - BenchmarkReport contract (Pydantic model)
   - Machine-readable, schema-validated
   - Consumed by downstream stages (Stage 2+)

   ```json
   {
     "contract_type": "benchmark_report",
     "schema_version": "1.0",
     "contract_id": "bench_...",
     "run_id": "...",
     "generated_by_stage_run_id": "stg_...",
     "created_at": "2026-03-28T...",
     "niche": "Content Niche",
     "analyzed_video_count": 10,
     "analysis_period_days": 30,
     "transcript_available": false,
     "analysis_confidence": "medium",
     "top_patterns": { ... },
     "keyword_bank": { ... },
     "competitor_analysis": { ... },
     "ctr_insights": { ... }
   }
   ```

2. **benchmark_report.md**
   - Human-readable markdown format
   - For manual review and approval
   - Includes formatted patterns, competitor analysis, insights

3. **keyword_bank.json**
   - Structured keyword recommendations
   - Primary, secondary, and long-tail keywords
   - Seasonal trends (if detected)
   - Created for easy reference by Stage 2

4. **provenance.json**
   - Request parameters
   - Cost estimates
   - Output metadata
   - Audit trail for debugging

### Research Provider Integration

#### YouTubeResearchProvider

Located in `app/providers/research.py`

**Features**:
- YouTube Data API v3 integration using httpx async client
- Optional LLM analysis via Anthropic Claude
- Fallback to heuristic pattern extraction if no LLM
- Quota cost estimation
- Rate limit awareness

**Key Methods**:

1. `async estimate_cost(req, ctx) -> CostEstimate`
   - Calculates YouTube API quota cost
   - Adds LLM cost if Anthropic key available
   - Returns cost estimate with confidence level

2. `async benchmark(req, ctx) -> BenchmarkReport`
   - Main analysis method
   - Orchestrates video collection and pattern analysis
   - Returns complete BenchmarkReport

3. `async _search_and_collect_videos(keywords, max_videos)`
   - Uses search.list API to find competitor videos
   - Respects max 5 searches limit from design doc
   - Handles API errors gracefully

4. `async _get_video_details(video_ids, client)`
   - Calls videos.list API for metadata
   - Collects: title, description, view count, likes, comments, duration
   - Handles partial failures

5. `_prepare_analysis_payload(...)`
   - Structures video data for LLM analysis
   - Calculates aggregate metrics
   - Includes keywords and niche context

6. `async _analyze_patterns(payload, ctx)`
   - Routes to LLM or heuristics
   - Returns structured pattern dictionary

7. `async _analyze_with_llm(payload, ctx)`
   - Calls Anthropic Claude API
   - Sends analysis prompt with video data
   - Parses JSON response
   - Falls back to heuristics on error

8. `_analyze_with_heuristics(payload)`
   - No external API calls
   - Extracts title patterns
   - Calculates engagement rates
   - Returns structured patterns

9. `_build_analysis_prompt(payload) -> str`
   - Constructs Claude prompt
   - Formats video data clearly
   - Requests JSON output matching BenchmarkReport schema

10. `_parse_llm_response(content) -> dict`
    - Extracts JSON from markdown code blocks
    - Handles malformed responses gracefully

**YouTube API Usage**:
- search.list: 100 quota units per call (max 5 calls)
- videos.list: 1 quota unit per video
- commentThreads.list: 1 quota unit per comment thread

**Cost Calculation**:
- Quota units converted to USD at ~$0.0001 per unit
- Typical benchmark: $0.01-0.02 API cost
- LLM analysis (if enabled): +$0.10 for Claude

**Error Handling**:
- Gracefully handles missing API key
- Catches and logs HTTP errors
- Falls back to heuristics on LLM failure
- Validates JSON responses

### Usage Example

```python
from app.stages.stage1_benchmark import BenchmarkStage, BenchmarkStageInput
from app.providers.research import YouTubeResearchProvider
from app.storage.sqlite import Database

# Initialize
db = Database("workspace/pipeline.db")
await db.init()
stage = BenchmarkStage(db)

# Prepare input
input_data = BenchmarkStageInput(
    project=project,
    search_keywords=["keyword1", "keyword2", "keyword3"],
    workspace_root="workspace",
    youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
)

# Execute
report = await stage.execute(input_data)
print(f"Analyzed {report.analyzed_video_count} videos")
print(f"Confidence: {report.analysis_confidence}")
```

### Operating Modes

**Mode 1: With YouTube API + Anthropic LLM (Full Analysis)**
- Collects real YouTube competitor data
- Claude performs deep pattern analysis
- Most accurate, highest cost ($0.10-0.20)

**Mode 2: With YouTube API Only (Heuristic Analysis)**
- Collects real YouTube data
- Pattern extraction via heuristics
- Good quality, lower cost ($0.01-0.02)

**Mode 3: Testing/Development (No API)**
- Uses mock data or cached responses
- No external API calls
- Zero cost, useful for testing

### Quality Gate

The stage performs validation:
- Ensures analyzed_video_count > 0
- Validates BenchmarkReport schema
- Checks keyword_bank completeness
- Confirms file creation success

---

## Prompt Template

### Location
`app/prompts/benchmark/v1_analyst.txt`

### Purpose
Jinja2 template for Claude analysis prompt

### Variables
- `niche`: Content niche
- `keywords`: Search keywords list
- `video_count`: Number of videos
- `top_performers`: List of top video data
- `aggregate_metrics`: Aggregate statistics

### Output Schema
Requests JSON with:
- `top_patterns`: Title patterns, hooks, narrative structure
- `keyword_bank`: Primary, secondary, long-tail keywords
- `competitor_analysis`: Video count, engagement rates, differentiation
- `ctr_insights`: Title recommendations, thumbnail strategy, CTR improvement estimate

---

## BaseStage Enhancement

### Location
`app/stages/base.py`

### Changes
Made `execute()` method properly abstract:
- Added `@abstractmethod` decorator
- Clear docstring
- Enforces implementation in subclasses

### Signature
```python
@abstractmethod
async def execute(self, input_data: InputType) -> OutputType:
    """Execute the stage."""
    raise NotImplementedError
```

---

## Data Models & Contracts

### BenchmarkReport Contract
Location: `app/domain/contracts.py`

**Schema Version**: 1.0

**Fields**:
- `contract_type`: "benchmark_report"
- `schema_version`: "1.0"
- `contract_id`: Unique identifier
- `run_id`: Project run ID
- `generated_by_stage_run_id`: Stage execution ID
- `created_at`: Timestamp
- `niche`: Content niche
- `analyzed_video_count`: Number of videos analyzed
- `analysis_period_days`: Lookback period
- `transcript_available`: Boolean
- `analysis_confidence`: "high" | "medium" | "low"
- `top_patterns`: Dictionary of pattern analysis
- `keyword_bank`: Dictionary of keyword recommendations
- `competitor_analysis`: Dictionary of competitive insights
- `ctr_insights`: Dictionary of CTR strategies

### BenchmarkRequest Schema
Location: `app/domain/schemas.py`

**Fields**:
- `topic`: Video topic
- `niche`: Content niche
- `search_keywords`: List of keywords to search
- `max_videos`: Max videos to analyze (default 10)

---

## Configuration

### Environment Variables Required

```bash
YOUTUBE_API_KEY=your_youtube_api_key_here
ANTHROPIC_API_KEY=optional_anthropic_key  # Optional
```

### Config (default.yaml)

**Relevant sections**:

```yaml
cost_guardrail:
  per_stage:
    benchmark:
      hard_cap_usd: 0.50
```

Ensures Stage 1 cost doesn't exceed $0.50 per run.

---

## Storage Integration

### SQLite
- Projects stored with full metadata
- Stage runs tracked for idempotency
- Status transitions recorded

### File Storage
- Workspace directory structure
- JSON/Markdown artifacts
- Provenance sidecars
- Log files in `logs/llm_calls/`

### FileStorage Utility
Used throughout for async file I/O:
- `save_json()`: Save data as JSON
- `load_json()`: Load JSON data
- `save_text()`: Save text files
- `ensure_dir()`: Create directories

---

## Error Handling

### Stage 0 (Intake)
- Validates project model
- Creates idempotent workspace (mkdir with exist_ok=True)
- Handles duplicate projects gracefully
- Logs errors without failing if backup creation succeeds

### Stage 1 (Benchmark)
- Catches YouTube API errors
  - Missing key: Raises ValueError
  - HTTP errors: Logs and retries or falls back
  - No videos found: Raises ValueError
- Catches LLM errors
  - API failure: Falls back to heuristics
  - Malformed response: Parses gracefully
  - Missing key: Uses heuristics
- Validates output contracts
- Saves provenance for debugging

---

## Testing

### Unit Tests
Test individual methods without external dependencies:
- Workspace structure creation
- Heuristic pattern extraction
- Markdown formatting
- JSON serialization

### Integration Tests
Test full stage execution with mock data:
- Stage 0 → workspace creation → SQLite registration
- Stage 1 → provider → report generation

### E2E Tests (requires API keys)
Full pipeline with real APIs:
- YouTube API calls
- Claude LLM analysis
- End-to-end file creation

---

## Logging

### StructuredLogger
Located in `app/utils/logger.py`

Logs in JSON format with timestamp:
```json
{
  "timestamp": "2026-03-28T...",
  "message": "Benchmark analysis completed",
  "project_slug": "my-project",
  "videos_analyzed": 10
}
```

### Log Locations

- **Application logs**: `workspace/projects/{slug}/logs/app.log`
- **LLM call logs**: `workspace/projects/{slug}/logs/llm_calls/`
- **Console output**: Rich formatted output via CLI

---

## Design Compliance

### Artifact-Centric
✓ All outputs saved as files (JSON, Markdown)
✓ Database tracks state, files hold artifacts
✓ Provenance sidecars for all outputs

### Stage Isolation
✓ Stage 0 produces project + metadata
✓ Stage 1 consumes Project, produces BenchmarkReport
✓ No dependencies on downstream stages

### Resume/Idempotency
✓ Execution digest computed from inputs
✓ Can skip if previous run exists
✓ Can resume from checkpoint (Stage 1 ready for extension)

### Cost Control
✓ Cost estimate before execution
✓ Per-stage hard caps enforced by guardrail
✓ All costs logged to cost_summary.json

### HITL Ready
✓ benchmark_report.md for human review
✓ Approval checkpoints defined in config
✓ Integration with ApprovalService ready

---

## Future Extensions

### Stage 2 (Script Generation)
- Consumes BenchmarkReport
- Uses keyword_bank + patterns
- Generates ScriptContract

### Stage 3 (Voice Generation)
- Consumes ScriptContract
- Generates NarrationContract with timing
- TTS audio generation

### Quality Gate Implementation
- Validate schema compliance
- Check file existence
- Verify cost bounds
- Test downstream consumption

---

## Troubleshooting

### "No YouTube API key"
```
Error: YouTube API key required
Solution: Export YOUTUBE_API_KEY environment variable
```

### "Failed to get video details"
```
Error: YouTube API rate limit exceeded
Solution: Wait and retry, or reduce max_videos
```

### "Benchmark report incomplete"
```
Error: Analysis confidence too low
Solution: Check keyword validity, retry with different keywords
```

### "Cost limit exceeded"
```
Error: Stage hard cap exceeded
Solution: Check cost_summary.json, review guardrail config
```

---

## Summary

The Stage 0 and Stage 1 implementations provide:

1. **Complete workspace initialization** (Stage 0)
   - Directory structure matching design spec
   - Metadata snapshots and cost tracking
   - SQLite registration

2. **Robust benchmark analysis** (Stage 1)
   - YouTube API integration
   - Optional LLM analysis
   - Heuristic fallback
   - Structured output contracts
   - Comprehensive provenance

3. **Production-ready code**
   - Full async/await support
   - Comprehensive error handling
   - Structured logging
   - Configuration-driven
   - Schema validation

4. **Design compliance**
   - Artifact-centric approach
   - Cost tracking and guardrails
   - Idempotency support
   - HITL integration points
   - Resume capability ready
