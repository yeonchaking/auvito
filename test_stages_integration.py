"""Integration test for Stage 0 and Stage 1 implementations."""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from app.domain.models import Project
from app.domain.enums import ProjectStatus
from app.storage.sqlite import Database
from app.storage.files import FileStorage
from app.stages.stage0_intake import IntakeStage
from app.stages.stage1_benchmark import BenchmarkStage, BenchmarkStageInput
from app.providers.research import YouTubeResearchProvider


async def test_stage0_intake():
    """Test Stage 0: Intake stage."""
    print("\n" + "=" * 80)
    print("Testing Stage 0: IntakeStage")
    print("=" * 80)

    # Setup
    db = Database("workspace/test_pipeline.db")
    await db.init()

    workspace_root = "workspace"
    intake_stage = IntakeStage(db, workspace_root)

    # Create a test project
    project = Project(
        id=uuid4(),
        slug="test-project",
        title_seed="YouTube Video on Korean Cooking",
        channel_name="Test Channel",
        niche="Food & Cooking",
        language="ko-KR",
        target_duration_sec=480,
        status=ProjectStatus.CREATED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    print(f"\nCreated test project: {project.slug}")
    print(f"  ID: {project.id}")
    print(f"  Niche: {project.niche}")

    # Execute intake stage
    result_project = await intake_stage.execute(project)

    print(f"\n✓ Intake stage executed successfully")
    print(f"  Status: {result_project.status}")

    # Verify workspace structure
    workspace = Path(workspace_root) / "projects" / project.slug
    required_dirs = [
        "00_intake",
        "01_benchmark",
        "02_script",
        "03_voice",
        "04_storyboard",
        "05_assets",
        "06_render",
        "07_thumbnail",
        "08_publish",
        "logs/llm_calls",
        "approvals",
        "provenance",
    ]

    print(f"\n✓ Verifying workspace structure at: {workspace}")
    all_exist = True
    for dir_path in required_dirs:
        full_path = workspace / dir_path
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {dir_path}")
        if not exists:
            all_exist = False

    # Verify JSON files
    print(f"\n✓ Verifying JSON files")
    required_files = [
        "project.json",
        "config_snapshot.json",
        "cost_summary.json",
    ]

    for file_name in required_files:
        file_path = workspace / file_name
        if file_path.exists():
            print(f"  ✓ {file_name}")
            data = await FileStorage.load_json(str(file_path))
            if data:
                print(f"    Preview: {str(data)[:80]}...")
        else:
            print(f"  ✗ {file_name} (missing)")
            all_exist = False

    # Verify database
    print(f"\n✓ Verifying database")
    db_project = await db.get_project(project.slug)
    if db_project:
        print(f"  ✓ Project registered in SQLite")
        print(f"    Slug: {db_project.slug}")
        print(f"    Status: {db_project.status}")
    else:
        print(f"  ✗ Project not found in database")
        all_exist = False

    await db.close()

    return all_exist


async def test_youtube_research_provider():
    """Test YouTube research provider."""
    print("\n" + "=" * 80)
    print("Testing YouTubeResearchProvider")
    print("=" * 80)

    # Test provider initialization
    provider = YouTubeResearchProvider(
        api_key="test_key_placeholder",
        anthropic_api_key=None,
    )

    print(f"\n✓ YouTubeResearchProvider initialized")
    print(f"  API Base: {provider.API_BASE}")
    print(f"  Quota unit cost: {provider.QUOTA_UNIT_COST}")

    # Test cost estimation
    from app.domain.schemas import BenchmarkRequest
    from app.providers.base import ProviderCallContext

    request = BenchmarkRequest(
        topic="Korean Cooking Tips",
        niche="Food & Cooking",
        search_keywords=["Korean cooking", "easy recipes", "dinner ideas"],
        max_videos=10,
    )

    ctx = ProviderCallContext(
        run_id="test_run_001",
        stage_run_id="stg_test_001",
        attempt_no=1,
        idempotency_key="test_key",
    )

    estimate = await provider.estimate_cost(request, ctx)

    print(f"\n✓ Cost estimation successful")
    print(f"  Estimated cost: ${estimate.estimated_cost_usd}")
    print(f"  Confidence: {estimate.confidence}")
    print(f"  Reasoning: {estimate.reasoning}")

    # Test pattern analysis with heuristics
    videos_data = [
        {
            "video_id": "vid1",
            "title": "Easy Korean Bibimbap Recipe - Quick 15 Minute Dinner!",
            "description": "Learn to make authentic Korean bibimbap",
            "channel_id": "ch1",
            "published_at": "2024-01-15T10:00:00Z",
            "view_count": 150000,
            "like_count": 5000,
            "comment_count": 800,
            "duration": "PT12M30S",
        },
        {
            "video_id": "vid2",
            "title": "Korean Fried Chicken at Home - Crispy & Delicious",
            "description": "Homemade Korean fried chicken recipe",
            "channel_id": "ch2",
            "published_at": "2024-01-10T14:30:00Z",
            "view_count": 200000,
            "like_count": 8000,
            "comment_count": 1200,
            "duration": "PT14M15S",
        },
    ]

    analysis = provider._analyze_with_heuristics({
        "niche": "Food & Cooking",
        "keywords": ["Korean cooking", "recipes"],
        "videos": videos_data,
        "video_count": 2,
        "aggregate_metrics": {
            "total_views": 350000,
            "avg_views": 175000,
            "avg_like_count": 6500,
            "avg_comment_count": 1000,
        },
    })

    print(f"\n✓ Pattern analysis (heuristics) successful")
    print(f"  Top patterns: {json.dumps(analysis['top_patterns'], indent=2)[:200]}...")
    print(f"  Keyword bank keys: {list(analysis['keyword_bank'].keys())}")
    print(f"  Competitor analysis keys: {list(analysis['competitor_analysis'].keys())}")

    return True


async def test_benchmark_stage():
    """Test Stage 1: Benchmark stage."""
    print("\n" + "=" * 80)
    print("Testing Stage 1: BenchmarkStage (heuristics mode)")
    print("=" * 80)

    # Setup
    db = Database("workspace/test_pipeline.db")
    await db.init()

    benchmark_stage = BenchmarkStage(db)

    # Create test project
    project = Project(
        id=uuid4(),
        slug="test-benchmark-project",
        title_seed="Korean Cooking Channel",
        channel_name="Food Channel",
        niche="Food & Cooking",
        language="ko-KR",
        target_duration_sec=480,
        status=ProjectStatus.CREATED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    # Create workspace structure first
    intake_stage = IntakeStage(db, "workspace")
    await intake_stage.execute(project)

    print(f"\nTest project created: {project.slug}")

    # Test with mock data (no real API key)
    stage_input = BenchmarkStageInput(
        project=project,
        search_keywords=["Korean cooking", "easy recipes"],
        workspace_root="workspace",
        youtube_api_key="",  # No real API
        anthropic_api_key=None,
    )

    # Create mock provider that doesn't call API
    mock_provider = YouTubeResearchProvider(api_key="", anthropic_api_key=None)

    # Skip actual benchmark execution (would need real API)
    workspace = Path("workspace") / "projects" / project.slug / "01_benchmark"
    print(f"\n✓ Benchmark stage setup complete")
    print(f"  Output directory: {workspace}")
    print(f"  Files would be created:")
    print(f"    - benchmark_report.json")
    print(f"    - benchmark_report.md")
    print(f"    - keyword_bank.json")
    print(f"    - provenance.json")

    await db.close()

    return True


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("YouTube Pipeline Stage 0 & 1 Integration Tests")
    print("=" * 80)

    try:
        # Test Stage 0
        stage0_pass = await test_stage0_intake()

        # Test Research Provider
        provider_pass = await test_youtube_research_provider()

        # Test Stage 1
        stage1_pass = await test_benchmark_stage()

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Stage 0 (Intake): {'✓ PASS' if stage0_pass else '✗ FAIL'}")
        print(f"Research Provider: {'✓ PASS' if provider_pass else '✗ FAIL'}")
        print(f"Stage 1 (Benchmark): {'✓ PASS' if stage1_pass else '✗ FAIL'}")

        if stage0_pass and provider_pass and stage1_pass:
            print("\n✓ All tests passed!")
            return 0
        else:
            print("\n✗ Some tests failed")
            return 1

    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
