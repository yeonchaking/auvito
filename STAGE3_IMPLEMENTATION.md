# Stage 3: Voice + Subtitles Implementation

## Overview

Stage 3 implements the complete voice narration and subtitle generation pipeline for the YouTube automation system. It takes a `ScriptContract` from Stage 2 and produces:

1. **NarrationContract** - Machine-readable contract with clip-level timing metadata
2. **narration.wav** - Merged audio file with all segments
3. **subtitles.srt** - SRT-format subtitle file with word-level timestamps

## Architecture

### Components

#### 1. EdgeTTSProvider (`app/providers/tts.py`)

Implements text-to-speech using Microsoft Edge TTS API via the `edge_tts` Python library.

**Key Features:**
- Asynchronous segment-by-segment synthesis
- Caching based on text hash (deduplicates identical segments)
- Automatic audio duration detection using ffprobe
- No API cost (Microsoft-provided service)
- Fallback duration estimation from file size if ffprobe unavailable
- Speaking rate support (0.5x - 2.0x) converted to ±XX% format

**Usage Example:**
```python
provider = EdgeTTSProvider(workspace_root="/path/to/workspace")
request = TTSRequest(
    text="안녕하세요",
    voice_id="ko-KR-SunHiNeural",
    language="ko-KR",
    speaking_rate=1.0
)
result = await provider.synthesize(request, ctx)
# result.audio_path: "/path/to/tts_hash_voice.wav"
# result.duration_sec: 2.345
```

**Configuration (default.yaml):**
```yaml
audio:
  tts_provider: edge_tts
  tts_voice: ko-KR-SunHiNeural
  speaking_rate: 1.0
  audio_format: wav
  sample_rate_hz: 24000
```

#### 2. OpenAISTTProvider (`app/providers/stt.py`)

Implements speech-to-text using OpenAI's Whisper API with word-level timestamp extraction.

**Key Features:**
- Primary model: `gpt-4o-transcribe` (recommended for Korean)
- Fallback model: `whisper-1` (Whisper v3 API)
- Word-level timestamp extraction for precise subtitle generation
- Cost estimation: ~$0.006 per minute of audio
- Graceful fallback to timestamp estimation when no word-level data available
- Fallback mode when OPENAI_API_KEY not set (generates placeholder transcripts)

**Usage Example:**
```python
provider = OpenAISTTProvider(api_key=api_key)
request = STTRequest(
    audio_path="/path/to/audio.wav",
    language="ko-KR"
)
result = await provider.transcribe(request, ctx)
# result.text: "전체 음성 텍스트"
# result.words: [
#   {"word": "전체", "start_sec": 0.0, "end_sec": 0.5},
#   {"word": "음성", "start_sec": 0.5, "end_sec": 1.0},
#   ...
# ]
```

**Fallback Mode:**
When `OPENAI_API_KEY` is not set:
- Returns placeholder transcript with duration annotation
- Provides empty word list (subtitles can still be generated from segment text)
- Allows complete pipeline execution for testing/offline scenarios

#### 3. VoiceStage (`app/stages/stage3_voice.py`)

Main orchestration stage that coordinates the entire voice generation pipeline.

**Processing Pipeline:**

1. **Segment Synthesis** (`_synthesize_segments`)
   - Iterates through all script segments
   - Calls EdgeTTSProvider for each segment
   - Creates NarrationClip objects with actual durations
   - Error handling: fails fast on any synthesis error

2. **Audio Merging** (`_merge_audio_clips`)
   - Uses ffmpeg concat demuxer for lossless merging
   - Command: `ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.wav`
   - Verifies merge success via ffprobe
   - Cleans up temporary concat list file

3. **Clip Timing Update** (`_update_clip_timings`)
   - Calculates cumulative start/end times for each clip
   - Ensures no gaps or overlaps
   - Updates NarrationClip objects in-place

4. **Audio Transcription** (`_transcribe_audio`)
   - Calls OpenAISTTProvider on merged audio
   - Extracts word-level timestamps
   - Gracefully handles transcription failures

5. **Subtitle Generation** (`_generate_subtitles`)
   - Converts word timestamps to SRT format using SRTGenerator
   - Line length limits: 42 characters per line, 3 lines max
   - Standard SRT formatting: index, timecode (HH:MM:SS,mmm), text

**Output Structure:**
```
projects/{run_id}/03_voice/
├── narration_contract.json     # NarrationContract in JSON
├── narration.wav               # Merged audio file
├── subtitles.srt               # SRT subtitle file
├── provenance.json             # Metadata about generation
├── concat_list.txt            # Temporary (cleaned up)
└── temp/
    └── tts/
        ├── tts_hash1_voice.wav # Segment 1 audio
        ├── tts_hash2_voice.wav # Segment 2 audio
        └── ...
```

#### 4. SRT Utilities (`app/utils/srt.py`)

Provides SRT file format handling with word-level subtitle generation.

**Key Classes:**

- **SRTSubtitle** - Single subtitle entry with timing and text
  ```python
  subtitle = SRTSubtitle(
      index=1,
      start_sec=0.0,
      end_sec=5.5,
      text="자막 텍스트"
  )
  ```

- **SRTGenerator** - Utility for generating and reading SRT files
  ```python
  # Generate from words
  subtitles = SRTGenerator.generate_from_words(
      words=[
          {"word": "안녕하세요", "start_sec": 0.0, "end_sec": 1.0},
          ...
      ]
  )

  # Write to file
  SRTGenerator.write_srt_file(subtitles, "subtitles.srt")

  # Read from file
  subtitles = SRTGenerator.read_srt_file("subtitles.srt")
  ```

**SRT Format Example:**
```
1
00:00:00,000 --> 00:00:05,500
자막 첫 번째 줄
두 번째 줄

2
00:00:05,500 --> 00:00:12,000
다음 자막
```

## Data Contracts

### NarrationContract (Output)

```python
class NarrationContract(ContractEnvelope):
    script_id: str                      # Reference to Stage 2 script
    language: str                       # "ko-KR"
    narration_audio_uri: str            # "artifacts/audio/narration.wav"
    subtitles_uri: str                  # "artifacts/subtitles/subtitles.srt"
    total_duration_sec: float           # Total merged audio duration
    voice: dict[str, Any]               # TTS config (provider, voice_id, speaking_rate)
    audio_format: str                   # "wav"
    sample_rate_hz: int                 # 24000
    clips: list[NarrationClip]          # ★ Timing baseline for all downstream stages
```

### NarrationClip

```python
class NarrationClip(BaseModel):
    clip_id: str                        # "clip_001"
    segment_id: str                     # Reference to ScriptSegment
    text: str                           # Narration text
    start_sec: float                    # Cumulative start time in merged audio
    end_sec: float                      # Cumulative end time in merged audio
    actual_duration_sec: float          # Actual segment duration
    ssml: Optional[str] = None          # For future SSML support
```

## Error Handling

### Synthesis Errors
- **Missing edge_tts library**: Raises RuntimeError with installation instructions
- **TTS API failures**: Logs error and raises ValueError with context
- **Audio duration detection**: Falls back to file-size estimation

### Merge Errors
- **ffmpeg not available**: Raises RuntimeError
- **Concat file issues**: Cleaned up in finally block
- **No clips to merge**: Raises ValueError

### Transcription Errors
- **Missing OPENAI_API_KEY**: Falls back to placeholder transcription
- **API rate limits**: Raises ValueError (caller should implement retry)
- **Audio file issues**: Logs error, continues with empty word list

## Testing Recommendations

### Unit Tests
1. Test EdgeTTSProvider with different speaking rates
2. Test OpenAISTTProvider with mock API responses
3. Test SRTGenerator with various word lists
4. Test VoiceStage with minimal 1-segment script

### Integration Tests
1. Full pipeline with test script contract
2. Verify clip timings add up correctly
3. Verify SRT file readability with ffmpeg
4. Test concurrent segment synthesis (safe due to file hashing)

### Edge Cases
1. Empty script (0 segments)
2. Single segment script
3. Very long segment text (> 1000 chars)
4. Very short segment text (< 5 chars)
5. Non-ASCII characters (Korean, emoji, etc.)
6. Missing OpenAI API key (fallback mode)
7. ffmpeg not installed (graceful fallback)

## Performance Characteristics

### Timing (Typical)
- Single segment TTS: 0.5-2s (dependent on text length)
- N-segment synthesis (parallel): ~2s (cacheable)
- Audio merge: 0.5-1s
- STT on full audio: 10-30s (dependent on duration)
- SRT generation: <0.1s

### Caching
- Edge TTS caches by text hash (same text = same file)
- Allows re-running stage without regenerating all audio
- Cache location: `{workspace_root}/temp/tts/`

### Resource Usage
- Disk: ~200KB per minute of audio (WAV format at 24kHz)
- Memory: Streaming for ffmpeg merge (constant ~50MB)
- Network: Only OpenAI STT calls (occasional, not per-segment)

## Configuration

### Default Settings (default.yaml)
```yaml
audio:
  tts_provider: edge_tts              # Only provider implemented
  tts_voice: ko-KR-SunHiNeural        # Korean female voice
  speaking_rate: 1.0                  # Normal speed
  audio_format: wav                   # Uncompressed WAV
  sample_rate_hz: 24000               # 24kHz sample rate

stt:
  provider: openai                    # Required
  model: gpt-4o-transcribe            # Primary (Korean-optimized)
  fallback_model: whisper-1           # Fallback
```

### Environment Variables
```bash
OPENAI_API_KEY=sk-...                 # Required for STT
WORKSPACE_ROOT=/path/to/workspace     # Optional, defaults to "workspace"
```

## API Examples

### Complete Pipeline

```python
from app.stages.stage3_voice import VoiceStage, VoiceStageInput
from app.domain.contracts import ScriptContract

# Load script contract from Stage 2
script_contract = ...

# Prepare input
input_data = VoiceStageInput(
    script_contract=script_contract,
    workspace_root="/workspace",
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    tts_voice="ko-KR-SunHiNeural",
    speaking_rate=1.0
)

# Execute stage
stage = VoiceStage()
narration_contract = await stage.execute(input_data)

# Access outputs
print(f"Audio: {narration_contract.narration_audio_uri}")
print(f"Subtitles: {narration_contract.subtitles_uri}")
print(f"Duration: {narration_contract.total_duration_sec}s")
print(f"Clips: {len(narration_contract.clips)}")
```

### Direct Provider Usage

```python
from app.providers.tts import EdgeTTSProvider
from app.providers.stt import OpenAISTTProvider
from app.domain.schemas import TTSRequest, STTRequest
from app.providers.base import ProviderCallContext

# TTS
tts_provider = EdgeTTSProvider()
tts_request = TTSRequest(
    text="테스트 텍스트",
    voice_id="ko-KR-SunHiNeural",
    language="ko-KR",
    speaking_rate=1.0
)
ctx = ProviderCallContext(
    run_id="test_run",
    stage_run_id="stg_test_1",
    attempt_no=1,
    idempotency_key="key123"
)
result = await tts_provider.synthesize(tts_request, ctx)

# STT
stt_provider = OpenAISTTProvider()
stt_request = STTRequest(
    audio_path=result.audio_path,
    language="ko-KR"
)
transcript = await stt_provider.transcribe(stt_request, ctx)
```

## Known Limitations

1. **Single audio track**: Stage 3 only produces one merged narration track
2. **No background music mixing**: Audio is pure narration, no BGM
3. **No voice effects**: Pitch/tone adjustments not supported
4. **Korean-language focused**: Tested primarily with Korean, other languages untested
5. **No SSML support yet**: edge_tts supports SSML but not exposed in current implementation
6. **No speaker diarization**: All audio from single voice
7. **STT confidence**: Word-level confidence scores not extracted (available in OpenAI response)

## Future Enhancements

1. **SSML Support**: Allow prosody/emphasis markup in script text
2. **Multiple Voice Synthesis**: Support for dialogue/multi-speaker narration
3. **Local STT**: Add faster-whisper for offline/privacy-preserving transcription
4. **Audio effects**: Normalizing, compression, reverb
5. **Background music**: Ducking/mixing with BGM track
6. **Timestamp precision**: Sub-word or grapheme-level timestamps
7. **Confidence scoring**: Return confidence for subtitle accuracy
8. **Caching**: Implement Redis/DynamoDB for cross-run cache

## Debugging

### Common Issues

**Edge TTS fails with "module not found"**
```bash
pip install edge-tts
```

**ffmpeg not found**
```bash
# Linux
sudo apt-get install ffmpeg ffprobe

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**OpenAI API rate limit**
- Implement exponential backoff in caller
- Consider `max_calls_per_run: 3` from config guardrails

**Merged audio has clicks/pops**
- Edge TTS clips may have silence at boundaries
- Consider fade-in/out in post-processing (future enhancement)

### Logs to Check

```
# Success
"Starting voice generation" (script_id, segment_count)
"Segment synthesized" (segment_id, duration_sec)
"Audio clips merged" (clip_count, total_duration_sec)
"Audio transcribed" (text_length, word_count, confidence)
"Subtitles generated" (output_path, subtitle_count)
"Voice generation completed" (narration_id, clip_count)

# Failures
"TTS synthesis failed" (segment_id, error)
"Audio merge failed" (error)
"Audio transcription failed" (error)
"Subtitle generation failed" (error)
```

## Production Checklist

- [ ] Edge TTS library installed: `pip install edge-tts`
- [ ] ffmpeg/ffprobe installed on system
- [ ] OPENAI_API_KEY configured (or fallback mode acceptable)
- [ ] Workspace directory has write permissions
- [ ] Korean voice model tested (ko-KR-SunHiNeural)
- [ ] SRT output validated with subtitle player
- [ ] Cost tracking working (OpenAI API calls logged)
- [ ] Clip timings verified: no gaps, no overlaps
- [ ] Error handling tested for missing dependencies
- [ ] Concurrent execution safe (file hashing prevents collisions)
