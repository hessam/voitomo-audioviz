# Reliable Persian vocal transcription and synchronization

## Decision

Build a quality-gated pipeline with separate recognition, acoustic alignment, phrase segmentation, and rendering contracts. Keep the existing GPU Whisper large-v3 service as the baseline. Select additional recognition/alignment models through a Persian singing benchmark. A model's score alone cannot establish correct words or timing.

First alignment candidate: WhisperX with its configured Persian model `jonatasgrosman/wav2vec2-large-xlsr-53-persian`. Its current code supports `fa`, but can interpolate unalignable words; the integration must preserve that distinction and reject inferred spans from automatic acceptance. Its Persian checkpoint was trained on speech, so singing performance still requires validation. [WhisperX alignment implementation](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py), [Persian model card](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-persian).

MMS is a comparison candidate requiring romanized alignment text and careful runtime selection; the documented TorchAudio alignment APIs have a deprecation/removal notice. Further primary-source findings and limitations are in [PERSIAN_ASR_RESEARCH.md](PERSIAN_ASR_RESEARCH.md).

For the highest assurance, allow verified lyrics plus acoustic alignment and targeted human review. Fully automatic mode must expose uncertain spans and abstain from claiming exact synchronization when evidence is missing.

This document proposes implementation; it does not certify production accuracy or change runtime behavior. Current worktree changes were preserved.

## Confirmed code findings

| Location | Finding | Consequence |
|---|---|---|
| `vast_ai_service.py:get_whisper_model`, `/ai/transcribe` | GPU uses large-v3; returns rounded word probabilities and optional detected language | A larger-model switch alone will not repair the current pipeline. Word probability is not calibrated correctness. |
| `bot/services/lyric_transcriber.py` | Local default is medium; remote failures fall through broker/local paths | Different quality tiers can be delivered without a structured degradation status. Local output drops word scores. |
| `bot/routers/audioviz.py:handle_audio_message` | Language is omitted; master fallback runs only if the separated-vocal transcript is empty | Wrong but nonempty lyrics are accepted; Persian language preference is not carried through. |
| `bot/services/alignment.py:realign_transcript` | Text matching plus linear interpolation; never reads audio | Corrected words receive invented timing, especially repeated choruses and large edits. |
| `bot/routers/audioviz.py` full-text editing | Reports successful audio synchronization after that interpolation | User-facing confidence exceeds available evidence. |
| `bot/services/audio_features.py` lyric grouping | Five-word/punctuation grouping; the documented pause test is absent | Phrases can cross vocal pauses and be split at arbitrary positions. |
| `bot/services/transcriber.py:normalize_words_with_llm` | Mutates words without whole-response index/length validation or acoustic rechecking | Fluent changes can replace what was sung while retaining unrelated timestamps. |
| `bot/services/normalizer.py:normalize_persian_asr` | Rebuilds word dictionaries using only text/start/end | Scores and provenance disappear if supplied. |
| `bot/services/lyric_transcriber.py` local token filtering | Removes standalone words including آهنگ and موسیقی | Legitimate sung words can be discarded alongside artifacts. |
| `bot/services/music_director.py` | Scene boundaries may snap to downbeats | Appropriate for visual transitions; must not become the source of word timing. |
| `renderer/src/components/TypographyOverlay.tsx` | Displays phrase intervals and retains recent lines | Rendered phrase persistence is distinct from acoustic word synchronization. |

## Reproduced defects

Executed the existing `realign_transcript` directly without models or network:

1. Empty recognized words plus five Persian lyric tokens and a ten-second duration produces five equal two-second intervals. Those times have no acoustic evidence.
2. Original words `الف [0, 0.999]`, `ج [0.999, 1.0]`; replacement `الف یک دو سه ج`; audio duration 1.0 seconds. Output ends at **2.349 seconds**. The monotonic repair silently extends beyond the audio.

These are deterministic functional reproductions, not ASR accuracy measurements. No full test suite, live GPU calls, model downloads, or transcription benchmark was run.

## Proposed pipeline

### 1. Preserve a single audio clock

- Keep the original master immutable and record its checksum, decoded sample count, sample rate, duration, and channel handling.
- Derive ASR-rate PCM without deleting silence or changing speed. Retain source offsets for every crop.
- Validate separated-stem duration and alignment to the master. Measure and record any verified separation delay; do not assume all stems start at exactly the master origin.
- Use overlap-aware chunks around vocal regions with contextual padding. Validate vocal detection on sustained vowels, soft entries, rap, reverberation, and backing vocals; avoid treating speech VAD as ground truth for singing.

### 2. Recognize words with evidence

- In explicitly Persian mode, propagate `language="fa"` through router, broker, and GPU endpoint. Keep a mixed-language mode for genuine code-switching.
- Run the existing large-v3 baseline on separated vocals. Compare the master for uncertain spans or separation damage. For a maximum-quality tier, evaluate both views throughout the track.
- Compare a second independently evaluated Persian-capable recognizer on difficult spans. Two passes through the same recognizer are useful disagreement evidence, not independent votes proving correctness.
- Preserve raw text, complete word scores, model/version, input checksum, source interval, vocal activity evidence, and fallback status. Do not round scores before assessment.
- Retry bounded uncertain spans with alternate context/input views. Exhausted retries yield `needs_review`, not accepted guesses.

### 3. Normalize Persian conservatively

- Keep raw acoustic text and display text separately.
- Use a documented comparison normalization for Arabic/Persian ی and ک, optional diacritics, whitespace, and ZWNJ. Preserve an explicit mapping back to displayed words and original characters.
- Treat colloquial forms, names, poetic language, and repeated words as potentially intentional. Punctuation restoration must not change lexical content.
- LLM corrections may propose candidates. Lexical replacements require acoustic re-evaluation or user verification. Reject malformed/partial correction batches atomically.
- A supplied lyric sheet must correspond to the actual performance: repeats, omitted verses, ad-libs, and alternate wording matter. Retain explicit unperformed or unmatched spans instead of forcing every supplied word into the track.

### 4. Force-align accepted text to audio

- Replace interpolation for accepted results with a Persian-capable acoustic forced aligner. Evaluate a WhisperX-compatible Persian CTC checkpoint and a multilingual alignment alternative using the primary-source research note.
- Align within coarse verified vocal/phrase anchors. Preserve occurrence order through repeated choruses; avoid whole-song text matching as the only anchor.
- Record alignment score, coverage, out-of-vocabulary/unmapped characters, and method per word. Preserve gaps and unresolved words. Never invent accepted timestamps by interpolation.
- Corrected text invalidates affected alignment. Re-align that span with neighboring context before offering an updated render.
- Alignment locates proposed words; it does not prove those words were sung. Its confidence must remain separate from recognition confidence.

### 5. Derive phrases and render timing

- Derive phrases from aligned word intervals, actual pauses/breaths, verified lyric structure, and Persian syntax. Use display width limits after acoustic segmentation.
- Phrase start/end come from the first/last aligned word. Explicitly handle elongated vowels, overlapping backing vocals, and repeated lines.
- Preserve seconds or sample positions until manifest compilation; use the actual composition FPS for final conversion. Validate every interval after conversion.
- Keep word/phrase timing tied to vocals. Beat timing can control visual cuts or emphasis with a separate offset, without shifting the acoustic transcript.
- Retain word intervals in the rendering contract if karaoke-level highlighting is required; current line-only manifests cannot deliver word-level highlighting.

## Confidence and acceptance contract

Store separate fields for acoustic text, display text, start/end, recognition score, alignment score, source model/view, review reasons, and status (`accepted`, `needs_review`, `unavailable`). Do not label a raw model score as a percentage probability of correct lyrics.

Calibrate text and boundary confidence independently on held-out annotated Persian songs. Use singer/song-level splits, including repeats, dialects, code-switching, soft vocals, dense instruments, long vowels, and instrumental-only sections. Compute phrase-level confidence from labeled phrase correctness and its constituent evidence; a simple average of word scores can conceal one critical wrong word.

Hard deterministic gates:

- All times finite; `0 <= start < end <= master_duration`.
- Ordered spans within a single vocal stream; explicit handling of genuine overlapping voices.
- No unexplained loss/duplication across chunks; every displayed word maps to an accepted aligned interval.
- No accepted interpolated timing, unsupported characters silently dropped, or unreported model fallback.
- No lyrics during verified instrumental regions without contrary reviewed evidence.

Suggested release targets to validate, not existing guarantees:

- Report normalized WER and CER, phrase exact-match rate, insertion/hallucination rate, and performance by difficult subgroup.
- Measure word onset/offset median and p95 absolute error separately, with an explicit annotation policy for sustained vowels.
- Initial timing goal: median onset error at most 50 ms and p95 at most 150 ms on the labeled set. Adjust only through an explicit product decision informed by measurement.
- For automatically accepted phrases, target at least 99% exact lexical correctness on held-out data, report uncertainty intervals and accepted coverage. Do not achieve that number by concealing rejected cases.
- Review ambiguous spans with short synchronized audio excerpts and alternatives. Human review is part of the highest-assurance mode.

## Implementation order

1. **Stop false certainty:** structured degradation/review status, preserve evidence, validate timing, language selection, and truthful edit feedback. Add deterministic regressions for the reproduced defects.
2. **Add acoustic alignment:** one GPU endpoint with a replaceable alignment backend; capability-test Persian characters and singing before selecting the default. Reuse the current GPU lifecycle and broker architecture.
3. **Add phrase/word contracts:** preserve acoustic intervals into the manifest, implement pause-aware phrase segmentation, and expose localized review.
4. **Calibrate and compare:** annotated benchmark, input-view comparison, bounded retries, independent recognizer evaluation, and per-model release gates.

Model/backend dependencies and GPU requirements should be chosen only after the small Persian singing evaluation. There is no evidence in this audit that any candidate already satisfies the proposed accuracy or synchronization targets.
