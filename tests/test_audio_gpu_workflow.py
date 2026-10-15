"""GPU audio orchestration tests with all inference/transport mocked."""

import asyncio
import os
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

from bot.services.audio_adapter import AudioIntelligenceAdapter
from bot.services import lyric_transcriber
from bot.services.vast_lifecycle import VastLifecycleManager, VAST_WARM_INSTANCE_ID


class TestAudioGpuWorkflow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        self.master = os.path.join(self.files.name, "master.wav")
        self.vocal = os.path.join(self.files.name, "vocals.wav")
        for path in (self.master, self.vocal):
            with open(path, "wb") as stream:
                stream.write(b"mock inference input")
        self.manager = VastLifecycleManager()
        # These lease tests exercise the Vast backend; Modal is the default provider.
        env = patch.dict(os.environ, {"GPU_PROVIDER": "vast"})
        env.start()
        self.addCleanup(env.stop)

        async def api(method, endpoint, data=None):
            if method == "GET":
                return {"instances": [{
                    "id": VAST_WARM_INSTANCE_ID, "actual_status": "running",
                    "ssh_host": "test.invalid", "ssh_port": 1234,
                }]}
            return {"success": True}

        self.manager._api_request = AsyncMock(side_effect=api)
        self.manager.ensure_tunnel = AsyncMock(return_value=True)
        for target, kwargs in (
            ("bot.services.vast_lifecycle.VastLifecycleManager.get_instance", {"return_value": self.manager}),
            ("bot.services.vast_lifecycle.subprocess.run", {}),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def assert_gpu_active(self):
        self.assertGreater(self.manager._active_jobs, 0)
        self.assertFalse(any(call.args[0] == "PUT" for call in self.manager._api_request.call_args_list))

    async def test_preparation_keeps_gpu_through_separation_and_transcription(self):
        async def separate(*args):
            self.assert_gpu_active()
            return {"vocals": self.vocal, "instrumental": self.master}

        def transcribe(*args):
            self.assert_gpu_active()
            return {"words": [{"word": "hello", "confidence": 0.07}]}

        with (
            patch.object(AudioIntelligenceAdapter, "separate_stems_gpu", side_effect=separate),
            patch.object(lyric_transcriber, "transcribe_lyrics_gpu", side_effect=transcribe),
        ):
            result = await AudioIntelligenceAdapter.prepare_visualizer_audio(self.master, language="fa")
        self.assertEqual(result["stems"]["vocals"], self.vocal)
        self.assertEqual(result["words"][0]["confidence"], 0.07)
        self.assertEqual(self.manager._active_jobs, 0)
        stops = [call for call in self.manager._api_request.call_args_list if call.args[0] == "PUT"]
        self.assertEqual(len(stops), 1)

    async def test_unavailable_transcription_preserves_stems(self):
        with (
            patch.object(AudioIntelligenceAdapter, "separate_stems_gpu", new_callable=AsyncMock, return_value={"vocals": self.vocal}),
            patch.object(lyric_transcriber, "transcribe_lyrics_gpu", side_effect=RuntimeError("ASR unavailable")),
        ):
            result = await AudioIntelligenceAdapter.prepare_visualizer_audio(self.master)
        self.assertEqual(result["stems"], {"vocals": self.vocal})
        self.assertEqual(result["words"], [])
        self.assertEqual(self.manager._active_jobs, 0)

    async def test_empty_vocal_transcript_retries_master_under_same_lease(self):
        paths = []

        def transcribe(path, *args):
            self.assert_gpu_active()
            paths.append(path)
            return {"words": [] if path == self.vocal else [{"word": "master"}]}

        with (
            patch.object(AudioIntelligenceAdapter, "separate_stems_gpu", new_callable=AsyncMock, return_value={"vocals": self.vocal}),
            patch.object(lyric_transcriber, "transcribe_lyrics_gpu", side_effect=transcribe),
        ):
            result = await AudioIntelligenceAdapter.prepare_visualizer_audio(self.master)
        self.assertEqual(paths, [self.vocal, self.master])
        self.assertEqual(result["words"], [{"word": "master"}])

    async def test_missing_input_does_not_wake_gpu(self):
        with self.assertRaises(FileNotFoundError):
            await AudioIntelligenceAdapter.prepare_visualizer_audio(os.path.join(self.files.name, "missing.wav"))
        self.manager._api_request.assert_not_awaited()

    async def test_sync_transcription_error_is_explicit(self):
        with patch.object(lyric_transcriber, "transcribe_lyrics_gpu", side_effect=RuntimeError("ASR unavailable")):
            with self.assertRaisesRegex(RuntimeError, "ASR unavailable"):
                lyric_transcriber.transcribe_lyrics(self.vocal)

    async def test_forced_alignment_has_a_gpu_lease(self):
        async def align(*args):
            self.assert_gpu_active()
            return {"words": [{"word": "aligned"}]}

        with patch.object(AudioIntelligenceAdapter, "_align_lyrics_ready", side_effect=align):
            result = await AudioIntelligenceAdapter.align_lyrics_gpu(self.vocal, "aligned", "http://test.invalid")
        self.assertEqual(result["words"], [{"word": "aligned"}])
        self.assertEqual(self.manager._active_jobs, 0)

    async def test_stem_failure_does_not_start_transcription(self):
        with (
            patch.object(AudioIntelligenceAdapter, "separate_stems_gpu", new_callable=AsyncMock, side_effect=RuntimeError("separation failed")),
            patch.object(lyric_transcriber, "transcribe_lyrics_gpu") as transcribe,
        ):
            with self.assertRaisesRegex(RuntimeError, "separation failed"):
                await AudioIntelligenceAdapter.prepare_visualizer_audio(self.master)
            transcribe.assert_not_called()
        self.assertEqual(self.manager._active_jobs, 0)

    async def test_cancellation_keeps_lease_until_sync_request_finishes(self):
        started = threading.Event()
        release = threading.Event()

        def transcribe(*args):
            started.set()
            release.wait(2)
            self.assert_gpu_active()
            return {"words": []}

        with patch.object(lyric_transcriber, "transcribe_lyrics_gpu", side_effect=transcribe):
            task = asyncio.create_task(lyric_transcriber.transcribe_lyrics_managed(self.vocal))
            try:
                for _ in range(100):
                    if started.is_set() or task.done():
                        break
                    await asyncio.sleep(0.001)
                self.assertTrue(started.is_set())
                task.cancel()
                await asyncio.sleep(0)
                self.assert_gpu_active()
                task.cancel()
                for _ in range(5):
                    await asyncio.sleep(0)
                self.assert_gpu_active()
            finally:
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 1)
        self.assertEqual(self.manager._active_jobs, 0)


if __name__ == "__main__":
    unittest.main()
