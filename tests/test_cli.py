import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import call, patch

import yt_transcript
from yt_transcript import cli, core


VIDEO_A = 'dQw4w9WgXcQ'
VIDEO_B = 'abcdefghijk'
VIDEO_C = 'lmnopqrstuv'
VIDEO_D = '12345678901'
PLAYLIST = 'https://www.youtube.com/playlist?list=example'


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'transcripts'
        self.output.mkdir()
        self.segments = [
            {'text': '¡Hola, 世界!', 'start': 1.25, 'duration': 2.5, 'speaker': 'Ana'},
            {'text': 'Next sentence.', 'start': 4.0, 'duration': 1.75},
        ]
        self.fetch = self.enterContext(patch.object(cli, 'fetch_transcript', return_value=self.segments))
        self.playlist = self.enterContext(patch.object(cli, 'fetch_playlist_video_ids', return_value=[VIDEO_B, VIDEO_C]))
        self.sleep = self.enterContext(patch.object(cli.time, 'sleep'))

    def run_main(self, *args, inputs=()):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['yt-transcript-cli', '-o', str(self.output), *args]), \
                patch('builtins.input', side_effect=inputs), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                cli.main()
                status = 0
            except SystemExit as error:
                status = error.code
        return status, stdout.getvalue(), stderr.getvalue()

    def run_video(self, *args, **kwargs):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli.process_video(*args, **kwargs)
        return status, stdout.getvalue(), stderr.getvalue()

    def path(self, video_id=VIDEO_A, output_format='text'):
        suffix = 'txt' if output_format == 'text' else 'json'
        return self.output / f'transcript_{video_id}.{suffix}'

    def test_json_round_trip_through_parser(self):
        status, stdout, stderr = self.run_main('--format', 'json', '--quiet', VIDEO_A)
        self.assertEqual(status, 0, stderr)
        self.assertEqual(stdout, f'{self.path(output_format="json")}\n')
        self.assertEqual(stderr, '')
        content = self.path(output_format='json').read_text(encoding='utf-8')
        self.assertEqual(json.loads(content), self.segments)
        self.assertIn('¡Hola, 世界!', content)
        self.fetch.assert_called_once_with(VIDEO_A, None)

    def test_cached_text_prints_path_without_fetching(self):
        path = self.path()
        path.write_bytes(b'cached text\n')
        status, stdout, stderr = self.run_video(VIDEO_A, None, self.output, True)
        self.assertEqual((status, stdout, stderr), ('skipped', f'{path}\n', ''))
        self.assertEqual(path.read_bytes(), b'cached text\n')
        self.fetch.assert_not_called()

    def test_default_and_explicit_text(self):
        for options in [(), ('--format', 'text')]:
            with self.subTest(options=options):
                status, stdout, stderr = self.run_main(*options, '--quiet', VIDEO_A)
                self.assertEqual(status, 0, stderr)
                self.assertEqual(stdout, f'{self.path()}\n')
                self.assertEqual(self.path().read_text(encoding='utf-8'), '¡Hola, 世界! Next sentence.')
                self.path().unlink()

    def test_same_format_cache_preserves_bytes_and_prints_once(self):
        for output_format in ('text', 'json'):
            for quiet in (False, True):
                with self.subTest(output_format=output_format, quiet=quiet):
                    path = self.path(output_format=output_format)
                    path.write_bytes(b'existing bytes are trusted\n')
                    status, stdout, stderr = self.run_video(
                        VIDEO_A, 'es', self.output, quiet, output_format=output_format)
                    self.assertEqual(status, 'skipped')
                    self.assertEqual(stdout, f'{path}\n')
                    self.assertEqual(path.read_bytes(), b'existing bytes are trusted\n')
                    if quiet:
                        self.assertEqual(stderr, '')
                    else:
                        self.assertIn(f'Skipped (already exists): {path}', stderr)
        self.fetch.assert_not_called()

    def test_forced_rewrite_preserves_skip_existing_positional_argument(self):
        for output_format in ('text', 'json'):
            with self.subTest(output_format=output_format):
                path = self.path(output_format=output_format)
                path.write_bytes(b'old')
                status, stdout, stderr = self.run_video(
                    VIDEO_A, None, self.output, True, False, output_format)
                self.assertEqual((status, stdout, stderr), ('success', f'{path}\n', ''))
                content = path.read_text(encoding='utf-8')
                if output_format == 'json':
                    self.assertEqual(json.loads(content), self.segments)
                else:
                    self.assertEqual(content, '¡Hola, 世界! Next sentence.')
        self.assertEqual(self.fetch.call_count, 2)

    def test_cross_format_cache_requires_fetch(self):
        for requested, existing in [('json', 'text'), ('text', 'json')]:
            with self.subTest(requested=requested):
                existing_path = self.path(output_format=existing)
                existing_path.write_bytes(b'other representation')
                status, stdout, stderr = self.run_main('--quiet', '--format', requested, VIDEO_A)
                self.assertEqual(status, 0, stderr)
                self.assertEqual(stdout, f'{self.path(output_format=requested)}\n')
                self.assertEqual(existing_path.read_bytes(), b'other representation')
                self.assertTrue(self.path(output_format=requested).exists())
                self.path(output_format=requested).unlink()
                existing_path.unlink()
        self.assertEqual(self.fetch.call_count, 2)

    def test_quiet_mixed_fresh_and_cached_batch(self):
        for output_format in ('text', 'json'):
            with self.subTest(output_format=output_format):
                self.path(VIDEO_B, output_format).write_bytes(b'cached')
                status, stdout, stderr = self.run_main(
                    '--quiet', '--format', output_format, VIDEO_A, VIDEO_B, VIDEO_C)
                self.assertEqual(status, 0, stderr)
                self.assertEqual(stdout, ''.join(f'{self.path(video, output_format)}\n'
                                               for video in (VIDEO_A, VIDEO_B, VIDEO_C)))
                self.assertEqual(stderr, '')
        self.assertEqual(self.fetch.call_args_list,
                         [call(VIDEO_A, None), call(VIDEO_C, None)] * 2)

    def test_all_cached_batch_succeeds_without_fetching(self):
        for output_format in ('text', 'json'):
            with self.subTest(output_format=output_format):
                for video in (VIDEO_A, VIDEO_B):
                    self.path(video, output_format).write_bytes(b'cached')
                status, stdout, stderr = self.run_main('--quiet', '--format', output_format, VIDEO_A, VIDEO_B)
                self.assertEqual((status, stderr), (0, ''))
                self.assertEqual(stdout, ''.join(f'{self.path(video, output_format)}\n'
                                               for video in (VIDEO_A, VIDEO_B)))
        self.fetch.assert_not_called()
        self.sleep.assert_not_called()

    def test_video_playlist_and_file_propagate_format_and_language(self):
        url_file = self.root / 'urls.txt'
        url_file.write_text(f'# A comment\n\nhttps://youtu.be/{VIDEO_D}\n', encoding='utf-8')
        status, stdout, stderr = self.run_main(
            '--quiet', '--format', 'json', '--lang', 'es',
            f'https://www.youtube.com/watch?v={VIDEO_A}', PLAYLIST, '-f', str(url_file))
        self.assertEqual(status, 0, stderr)
        videos = (VIDEO_A, VIDEO_B, VIDEO_C, VIDEO_D)
        self.assertEqual(stdout, ''.join(f'{self.path(video, "json")}\n' for video in videos))
        for video in videos:
            self.assertEqual(json.loads(self.path(video, 'json').read_text(encoding='utf-8')), self.segments)
        self.assertEqual(self.fetch.call_args_list, [call(video, 'es') for video in videos])
        self.playlist.assert_called_once_with(PLAYLIST)

    def test_duplicates_preserve_occurrences_and_counters(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            counts = cli.process_urls([VIDEO_A, PLAYLIST, VIDEO_A, VIDEO_B],
                                      None, self.output, True, 0, 'json')
        self.assertEqual(counts, (3, 2, 5, 0))
        self.assertEqual(stdout.getvalue(), ''.join(f'{self.path(video, "json")}\n'
                                                  for video in (VIDEO_A, VIDEO_B, VIDEO_C, VIDEO_A, VIDEO_B)))
        self.assertEqual(stderr.getvalue(), '')
        self.assertEqual(self.fetch.call_count, 3)

    def test_delays_follow_fresh_failed_skipped_and_final_results(self):
        self.path(VIDEO_C, 'json').write_bytes(b'cached')
        self.fetch.side_effect = [self.segments, RuntimeError('unavailable'), self.segments]
        status, stdout, stderr = self.run_main(
            '--quiet', '--format', 'json', '--delay', '0.2', VIDEO_A, VIDEO_B, VIDEO_C, VIDEO_D)
        self.assertEqual(status, 2)
        self.assertEqual(stdout, ''.join(f'{self.path(video, "json")}\n'
                                       for video in (VIDEO_A, VIDEO_C, VIDEO_D)))
        self.assertIn('unavailable', stderr)
        self.assertEqual(self.sleep.call_args_list, [call(0.1)] * 4)

    def test_interactive_explicit_and_implicit_entry(self):
        for options, video in [(('-i',), VIDEO_A), ((), VIDEO_B)]:
            with self.subTest(options=options):
                status, stdout, stderr = self.run_main(
                    *options, '--quiet', '--format', 'json', '--lang', 'es',
                    inputs=[f'https://youtu.be/{video}', '/process', '/quit'])
                self.assertEqual(status, 0, stderr)
                self.assertIn(f'{self.path(video, "json")}\n', stdout)
                self.assertEqual(json.loads(self.path(video, 'json').read_text(encoding='utf-8')), self.segments)
        self.assertEqual(self.fetch.call_args_list, [call(VIDEO_A, 'es'), call(VIDEO_B, 'es')])

    def test_existing_positional_helpers_default_to_text(self):
        status, stdout, _ = self.run_video(VIDEO_A, None, self.output, True, False)
        self.assertEqual((status, stdout), ('success', f'{self.path()}\n'))
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.process_urls([VIDEO_B], None, self.output, True, 0), (1, 0, 1, 0))
        with patch('builtins.input', side_effect=[VIDEO_C, '', '/q']), redirect_stdout(stdout):
            cli.run_repl(None, self.output, True, 0)
        for video in (VIDEO_A, VIDEO_B, VIDEO_C):
            self.assertEqual(self.path(video).read_text(encoding='utf-8'), '¡Hola, 世界! Next sentence.')

    def test_python_library_contracts_remain_available(self):
        api = self.enterContext(patch.object(core, 'YouTubeTranscriptApi'))
        api.return_value.fetch.return_value.to_raw_data.return_value = self.segments
        self.assertEqual(yt_transcript.fetch_transcript(VIDEO_A), self.segments)
        api.return_value.fetch.assert_called_once_with(VIDEO_A)
        api.return_value.fetch.reset_mock()
        self.assertEqual(yt_transcript.fetch_transcript(VIDEO_A, 'es'), self.segments)
        api.return_value.fetch.assert_called_once_with(VIDEO_A, languages=['es'])
        self.assertEqual(yt_transcript.to_text(self.segments), '¡Hola, 世界! Next sentence.')
        self.assertEqual(set(yt_transcript.__all__), {
            'parse_youtube_url', 'fetch_transcript', 'to_text', 'is_playlist_url', 'fetch_playlist_video_ids'})
        for name in yt_transcript.__all__:
            self.assertIs(getattr(yt_transcript, name), getattr(core, name))

    def test_invalid_format_fails_before_fetch_or_directory_creation(self):
        invalid_output = self.root / 'not-created'
        status, stdout, stderr = self.run_main(
            '--format', 'xml', '-o', str(invalid_output), VIDEO_A)
        self.assertEqual(status, 2)
        self.assertEqual(stdout, '')
        self.assertIn('invalid choice', stderr)
        self.assertFalse(invalid_output.exists())
        self.fetch.assert_not_called()

    def test_empty_transcripts_fail_without_paths_or_files(self):
        for output_format in ('text', 'json'):
            for segments in ([], [{'text': ''}], [{'text': ' \t\n', 'start': 0, 'duration': 1}]):
                with self.subTest(output_format=output_format, segments=segments):
                    self.fetch.return_value = segments
                    status, stdout, stderr = self.run_main('--quiet', '--format', output_format, VIDEO_A)
                    self.assertEqual(status, 1)
                    self.assertEqual(stdout, '')
                    self.assertIn('Transcript is empty', stderr)
                    self.assertFalse(self.path(output_format=output_format).exists())

    def test_fetch_failures_emit_no_paths_and_exit_one(self):
        self.fetch.side_effect = RuntimeError('upstream unavailable')
        for output_format in ('text', 'json'):
            with self.subTest(output_format=output_format):
                status, stdout, stderr = self.run_main('--quiet', '--format', output_format, VIDEO_A, VIDEO_B)
                self.assertEqual(status, 1)
                self.assertEqual(stdout, '')
                self.assertIn('upstream unavailable', stderr)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_partial_success_exits_two_and_only_prints_usable_paths(self):
        self.fetch.side_effect = [self.segments, RuntimeError('unavailable')]
        status, stdout, stderr = self.run_main('--quiet', '--format', 'json', VIDEO_A, VIDEO_B)
        self.assertEqual(status, 2)
        self.assertEqual(stdout, f'{self.path(output_format="json")}\n')
        self.assertIn('unavailable', stderr)
        self.assertFalse(self.path(VIDEO_B, 'json').exists())

    def test_unresolved_url_preserves_partial_and_all_failed_exit_statuses(self):
        status, stdout, stderr = self.run_main('--quiet', '--format', 'json', VIDEO_A, 'invalid')
        self.assertEqual(status, 2)
        self.assertEqual(stdout, f'{self.path(output_format="json")}\n')
        self.assertIn('Could not extract video ID', stderr)
        status, stdout, stderr = self.run_main('--quiet', '--format', 'json', 'invalid')
        self.assertEqual((status, stdout), (1, ''))
        self.assertIn('Could not extract video ID', stderr)

    def test_nonquiet_summary_stays_on_stderr(self):
        self.path(output_format='json').write_bytes(b'cached')
        status, stdout, stderr = self.run_main('--format', 'json', VIDEO_A)
        self.assertEqual(status, 0, stderr)
        self.assertEqual(stdout.splitlines(), [str(self.path(output_format='json')), ''])
        self.assertIn('Skipped (already exists):', stderr)
        self.assertIn('Completed: 1 skipped', stderr)

    def test_relative_output_paths_stay_relative(self):
        relative = Path('relative-transcripts')
        relative_path = relative / f'transcript_{VIDEO_A}.json'
        cached = self.root / relative_path
        cached.parent.mkdir()
        cached.write_bytes(b'cached')
        result = subprocess.run(
            [sys.executable, '-m', 'yt_transcript.cli', '--quiet', '--format', 'json',
             '-o', str(relative), VIDEO_A],
            cwd=self.root, env={**os.environ, 'PYTHONPATH': str(Path(cli.__file__).resolve().parents[1])},
            capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, f'{relative_path}\n', ''))



if __name__ == '__main__':
    unittest.main()
