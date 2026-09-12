# Performance and quality audit — 2026-09-12

## 1. Core Task & Goal Alignment Audit

Scope: targeted source inspection of the audio-to-video pipeline, followed by localized renderer refactoring. This is not certification of every core function or elimination of every defect. Existing edits in six Python files were preserved. No dependencies, configuration, commits, or external services were changed.

Authoritative context: README, ADR-0009, AUDIO_VISUALIZER_IMPLEMENTATION_PLAN.md, current Python/TypeScript contracts, renderer composition registration, and existing manifest tests.

| Core task / entry point | Required outcome | Finding and disposition |
|---|---|---|
| Telegram intake and delivery: `bot/routers/audioviz.py` | Audio produces an accessible completed MP4 | Render output existence is checked. Remote vault copying is synchronous; upload/compression/vault failure behavior needs integration verification. |
| Transcription: `transcriber.py`, `lyric_transcriber.py` | Accurate Persian text and acoustic timing | External/model-backed quality was not measured. Source scanning cannot establish transcript accuracy. |
| Feature compilation: `audio_features.py` | Complete normalized arrays aligned to video frames | Failed duration probes default to ten seconds; failed band extraction defaults to zeros. These can hide degraded inputs. Renderer now rejects malformed arrays, but cannot distinguish valid silence from substituted zeros. |
| Render boundary: `renderer/server.ts` | Exact manifest timeline and explicit errors | Fixed manifest-only jobs using the default 300 frames, conflicting duration overrides, invalid feature/timeline acceptance, and silent missing local audio. |
| Contract: `contracts/manifest.py`, `src/types/manifest.ts` | Producer/consumer agreement | Current producer emits 1920×1080 and nullable stems; reference documents and an existing Python test expect square video. TypeScript now represents both existing widths and nullable stems. No format policy was changed. |
| Visualizers: four components under `src/visualizers` | Deterministic frame evaluation | Iris uses `Math.random()`. Neural, Iris, and Monolith render before effect initialization without an initial render inside that effect; initial-frame capture requires browser verification. Seeds are not consistently driven by the manifest. Unresolved. |
| Typography: `TypographyOverlay.tsx` | Persian alignment, three-line clamp, safe padding | Three-entry FIFO and 160px padding exist. Ellipsis can suppress long text; CSS transitions can depend on capture history. Pixel fidelity remains unverified. |
| Legacy voice/music: `voice.py`, `music.py`, `Root.tsx` | Swiss typography, grounding, contrast | Legacy clients target port 4000. This server uses 4001 and its root does not register the legacy composition IDs accepted by the handler. Separate deployment behavior and semantic/brand validators were not certified. |

## 2. Performance Bottleneck Analysis

Ranked by likely operational impact; only the conversion row has local timing measurements.

1. **GPU/CPU rendering and admission:** two Chromium workers per job, with no global job limit. Multiple jobs can multiply resource usage. Full MP4 latency and GPU memory are unmeasured.
2. **Python DSP and model work:** six sequential FFmpeg band decodes, Python sample tuples/RMS loops, and synchronous feature extraction inside an async compiler. Source indicates event-loop blocking and avoidable allocations; no timing claim is made.
3. **Node conversion I/O/CPU:** synchronous FFmpeg blocked the event loop. Replaced with bounded asynchronous `execFile`, literal arguments, explicit conversion failure, and cleanup of owned WAV artifacts.
4. **Concurrent startup bundling:** ten cold requests previously initiated ten bundle operations. A shared in-flight promise now initiates one, and resets after failure. This measures avoided work using a Remotion stub, not production bundle latency.
5. **Visualizer setup/frame scans:** Neural initialization checks 1,124,250 pairs for 1,500 nodes and sorts neighbor lists. Sphere scans beat/transient histories; typography filters all lines per frame. These remain unprofiled.

No database bottleneck was identified in the inspected path. Disk growth from final/failed MP4s and synchronous vault copies remains an operational concern.

## 3. Refactored Code Diffs

Full implementations are in [server.ts](../renderer/server.ts), [render_contract.ts](../renderer/render_contract.ts), [render_audio.ts](../renderer/render_audio.ts), and [manifest.ts](../renderer/src/types/manifest.ts).

Essential timing correction:

```diff
- composition: { ...composition, durationInFrames: durationInFrames || composition.durationInFrames },
+ composition: {
+   ...composition,
+   durationInFrames: renderDuration,
+   ...(manifest ? {
+     width: manifest.video.width,
+     height: manifest.video.height,
+     fps: manifest.video.fpsNumerator / manifest.video.fpsDenominator,
+   } : {}),
+ },
```

Other changes: validate manifests before bundling; reject conflicting duration overrides with HTTP 400; use UUID output names; share bundling across concurrent calls; convert local audio without a shell or event-loop blocking; remove converted WAVs in `finally`; return explicit failures for missing/corrupt local audio. Validation checks normalized finite samples, exact required curve lengths, ordered event frames, valid lyric intervals, known presets, and the existing 30 FPS contract.

## 4. Benchmark & Quality Verification Evidence

Local macOS/Node/FFmpeg benchmark: synthesized 60-second 440 Hz WAV, seven measured sequential conversions per mode after one warm-up. Baseline uses synchronous FFmpeg with the original conversion settings; after uses production `prepareAudio`. It excludes Remotion, ASR, network, and GPU rendering.

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Median pending 1 ms timer delay | 126.686 ms | 0.859 ms | 147.5× lower event-loop delay |
| Median conversion wall time | 126.612 ms | 106.053 ms | 1.19× speedup in this run |
| Conversion throughput | 7.898/s | 9.429/s | 1.19×; sequential workload |
| Node peak RSS | 340.89 MiB | 325.55 MiB | Includes ts-node; excludes FFmpeg; no reliable memory-gain claim |
| Bundle invocations for ten cold requests | 10 | 1 | 10× less duplicated invocation work, mocked bundler |
| Initial six renderer regression checks | 1/6 | 6/6 | Targeted defect coverage; not overall product quality |

Two additional real-FFmpeg tests pass: literal shell characters and duration preservation with cleanup; corrupt input rejection with no converted artifact. Invalid-manifest coverage includes thirteen mutations. Render calls in HTTP-handler tests are stubbed, so no MP4 pixel/codec/SSIM claim follows from them.

Commands run from `renderer/`:

```sh
./node_modules/.bin/ts-node test_server.ts
./node_modules/.bin/ts-node test_render_audio.ts
./node_modules/.bin/ts-node benchmark_render_audio.ts before
./node_modules/.bin/ts-node benchmark_render_audio.ts after
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/tsc --noEmit --strict --target ES2020 --module commonjs --esModuleInterop --skipLibCheck server.ts render_audio.ts render_contract.ts
git diff --check
```

All listed checks passed after refactoring. No global test sweep ran. Python/model/external-service suites and GPU golden-frame tests were not run because the changes target the renderer boundary and those environments were not exercised.

## 5. Remaining Risks & Operational Safeguards

- The requested 10× end-to-end latency, throughput, memory, and quality targets are **not established**. Measured improvements apply to Node responsiveness and duplicate bundle work.
- Enforce a process-wide render admission limit before load testing; monitor active Chromium contexts, queued jobs, event-loop p95/p99 delay, RSS, GPU memory, and temporary disk usage.
- Strict validation may expose existing producer defects previously hidden by defaults. Monitor HTTP 400 causes, DSP fallback frequency, and lyric interval failures; fix producers rather than weakening validators.
- SHA-256 syntax is checked; audio content integrity is not verified. HTTP audio remains remotely fetched and is not pinned into an immutable local bundle.
- Missing audio receives HTTP 400; corrupt audio/conversion failures receive HTTP 500. Local conversion has a 120-second timeout. Long inputs require operational assessment against that bound.
- Final and failed MP4 retention, request cancellation, remote audio failure handling, and global job concurrency remain unresolved.
- Qualify deterministic frame capture, seed handling, Persian text completeness, font availability, and golden-frame SSIM on the deployment GPU. Confirm the format/brand contract before changing square versus widescreen or Swiss versus 3D behavior.
