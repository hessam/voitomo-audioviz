# Persian singing transcription and alignment

Primary sources checked 2026-09-20. These establish capabilities, not a Persian-singing accuracy ranking. No local audio benchmark was run.

## Practical model choice

- **Whisper large-v3 is a reasonable quality-first baseline; compare turbo on representative songs.** Turbo is a fine-tuned, pruned large-v3 with 4 decoder layers instead of 32, trading some quality for speed. This does not establish that large-v3 wins on every Persian song. [OpenAI model card](https://huggingface.co/openai/whisper-large-v3-turbo)
- **Persian is supported:** Whisper maps `fa` to `persian`. Set the known language explicitly and use transcription rather than translation to retain Persian text. [Whisper tokenizer](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py), [model usage](https://huggingface.co/openai/whisper-large-v3)
- Whisper documents hallucinations, repetition, and uneven performance across languages. Its speech benchmarks are not evidence of Persian singing accuracy. [Model limitations](https://huggingface.co/openai/whisper-large-v3-turbo)

## Forced alignment options

**WhisperX already has a Persian default.** Its current source maps `fa` to `jonatasgrosman/wav2vec2-large-xlsr-53-persian`; Persian alignment is not categorically unsupported. It loads a language-specific CTC model and tokenizer vocabulary. The implementation averages character scores for word scores and can interpolate timestamps for words lacking alignable characters. Preserve whether a timestamp is acoustically aligned or inferred; a timestamp alone is not proof of alignment. [Alignment source](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py)

The Persian model was fine-tuned on Common Voice 6.1 speech and expects 16 kHz audio. Its reported Common Voice WER is an ASR result, not a lyric-timing benchmark. [Model card](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-persian)

WhisperX documents dictionary coverage and overlapping speech limitations. Inference for songs: backing vocals and overlapping singers need special review; language support does not establish singing robustness. [WhisperX limitations](https://github.com/m-bain/whisperX#limitations-%EF%B8%8F)

**MMS forced alignment is an alternative to evaluate, not a proven upgrade.** The documented MMS_FA vocabulary uses Latin letters and special symbols, not native Persian script. Non-Latin transcripts require compatible normalization/romanization. The model was trained on 23,000 hours from more than 1,100 languages; that breadth does not quantify Persian singing performance. TorchAudio's tutorial warns these APIs were deprecated in 2.8 and scheduled for removal in 2.9, so do not assume a current unpinned installation supports its example. [TorchAudio multilingual alignment tutorial](https://docs.pytorch.org/audio/main/tutorials/forced_alignment_for_multilingual_data_tutorial.html)

Uroman explicitly supports Persian-specific romanization when given the language identity. Engineering recommendation: keep original Persian words and stable IDs, romanize an alignment-only copy, and map spans back to those IDs. Reject empty/unsupported results instead of dropping words. Romanization is not an English translation and must not replace display lyrics. [Uroman documentation](https://github.com/isi-nlp/uroman)

## Singing and confidence

Music source separation has been evaluated with Whisper for lyric transcription, but such experiments do not establish a universal benefit on Persian songs. Compare the original mixture and a vocal stem; review sustained vowels, repeated refrains, instrumental gaps, and separation artifacts. [Primary research](https://arxiv.org/abs/2506.15514)

Alignment scores summarize acoustic model outputs along a selected path; neither WhisperX's score calculation nor the MMS tutorial establishes calibration as the probability that both the word and its boundaries are correct. Do not label a raw score as a percentage accuracy. [WhisperX scoring implementation](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py), [MMS score calculation](https://docs.pytorch.org/audio/main/tutorials/forced_alignment_for_multilingual_data_tutorial.html)

Recommended acceptance procedure (engineering judgment): manually label a held-out Persian singing set; measure normalized WER/CER separately from word-boundary error and alignment coverage. Define the acceptable boundary tolerance before measuring it. Fit and validate confidence thresholds on that domain; until then call scores heuristic, flag missing/interpolated spans, and provide manual correction. When verified lyrics exist, align those lyrics rather than treating ASR guesses as ground truth. No reviewed primary source establishes a universally highest-quality Persian singing pipeline.
