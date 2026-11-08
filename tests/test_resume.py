import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from promo_finder.checkpoints import ResponseCheckpoints
from promo_finder.engine import run
from promo_finder.parser import Episode, Event
from promo_finder.providers import ChatProvider, RateLimitError, retry_delay


def episode(number=1):
    return Episode(number, 'synthetic.txt', '', '', 30,
                   [Event('e001', 'action', '', 0, 30, 'A courier arrives.')])


def response():
    return {'id': 'original', 'choices': [{'finish_reason': 'stop',
             'message': {'content': '{"candidates":[]}'}}], 'usage': {'total_tokens': 100}}


def limited(delay='2'):
    return urllib.error.HTTPError('https://example.com/api', 429, 'limit',
                                 {'Retry-After': delay}, io.BytesIO(b'SECRET'))


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = ResponseCheckpoints(self.temp.name)
        self.provider = ChatProvider('https://example.com/api', 'model', api_key='SECRET')

    def test_resume_uses_exact_response_without_call_and_revalidates(self):
        with patch.object(self.provider, 'complete', return_value=response()) as call:
            first = run([episode()], 'ai', provider=self.provider, checkpoints=self.cache)
            second = run([episode()], 'ai', provider=self.provider, checkpoints=self.cache)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(second['meta']['episodes_reused'], 1)
        self.assertEqual(second['raw_responses'][0]['response'], first['raw_responses'][0]['response'])
        self.assertEqual(second['meta']['episodes_succeeded'], 1)
        self.assertNotIn('SECRET', ''.join(p.read_text() for p in Path(self.temp.name).glob('*.json')))

    def test_changes_to_model_prompt_settings_endpoint_or_input_invalidate(self):
        p = self.provider
        original = self.cache.key(p, 'prompt', {'episode': 1})
        self.assertNotEqual(original, self.cache.key(p, 'new prompt', {'episode': 1}))
        self.assertNotEqual(original, self.cache.key(p, 'prompt', {'episode': 2}))
        for field, value in [('model', 'other'), ('url', 'https://other.example/api'), ('max_output_tokens', 8192)]:
            with patch.object(p, field, value):
                self.assertNotEqual(original, self.cache.key(p, 'prompt', {'episode': 1}))

    def test_corrupt_checkpoint_is_ignored(self):
        self.cache.put('example', response())
        path = Path(self.temp.name) / 'example.json'
        saved = json.loads(path.read_text())
        saved['response']['id'] = 'tampered'
        path.write_text(json.dumps(saved))
        self.assertIsNone(self.cache.get('example'))
        path.write_text('{')
        self.assertIsNone(self.cache.get('example'))

    def test_incomplete_answer_is_not_checkpointed(self):
        raw = response()
        raw['choices'][0]['finish_reason'] = 'length'
        with patch.object(self.provider, 'complete', return_value=raw):
            report = run([episode()], 'ai', provider=self.provider, checkpoints=self.cache)
        self.assertEqual(report['raw_responses'][0]['response'], raw)
        self.assertFalse(list(Path(self.temp.name).iterdir()))

    def test_limit_pauses_new_requests_but_still_reuses_later_checkpoint(self):
        with patch.object(self.provider, 'complete', return_value=response()):
            run([episode(3)], 'ai', provider=self.provider, checkpoints=self.cache)
        with patch.object(self.provider, 'complete', side_effect=RateLimitError('Rate limit')) as call:
            report = run([episode(1), episode(2), episode(3)], 'ai', provider=self.provider, checkpoints=self.cache)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(report['meta']['episodes_not_attempted'], 1)
        self.assertEqual(report['meta']['episodes_reused'], 1)
        self.assertEqual(report['meta']['episodes_succeeded'], 1)
        self.assertIn('Not attempted', report['episodes'][1]['error'])

    def test_checkpoint_write_failure_keeps_valid_result(self):
        with patch.object(self.provider, 'complete', return_value=response()), patch.object(self.cache, 'put', side_effect=OSError):
            report = run([episode()], 'ai', provider=self.provider, checkpoints=self.cache)
        self.assertEqual(report['meta']['episodes_succeeded'], 1)
        self.assertIn('could not be saved', report['episodes'][0]['warnings'][0])

    def test_environment_can_disable_checkpoints(self):
        with patch.dict('os.environ', {'PROMO_CACHE': '0'}):
            self.assertIsNone(ResponseCheckpoints.from_env())


class RateLimitTests(unittest.TestCase):
    def test_wait_then_success_keeps_exact_provider_output(self):
        p = ChatProvider('https://example.com/api', 'model')
        stream = MagicMock()
        stream.__enter__.return_value.read.return_value = json.dumps(response()).encode()
        opener = MagicMock()
        opener.open.side_effect = [limited('2.2'), stream]
        with patch('promo_finder.providers.urllib.request.build_opener', return_value=opener), patch('promo_finder.providers.time.sleep') as sleep:
            self.assertEqual(p.complete('prompt', {}), response())
        sleep.assert_called_once_with(3)
        self.assertEqual(p.last_request, {'attempts': 2, 'rate_limit_wait_seconds': 3})

    def test_long_reset_does_not_wait_or_hammer_provider(self):
        p = ChatProvider('https://example.com/api', 'model')
        opener = MagicMock()
        opener.open.side_effect = limited('3600')
        with patch('promo_finder.providers.urllib.request.build_opener', return_value=opener), patch('promo_finder.providers.time.sleep') as sleep:
            with self.assertRaisesRegex(RateLimitError, '3600 seconds'):
                p.complete('prompt', {})
        sleep.assert_not_called()
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(p.last_request['retry_after_seconds'],3600)

    def test_rate_limit_message_never_echoes_arbitrary_header_or_body(self):
        p = ChatProvider('https://example.com/api', 'model')
        opener = MagicMock()
        opener.open.side_effect = [limited('SECRET'),limited('SECRET'),limited('SECRET')]
        with patch('promo_finder.providers.urllib.request.build_opener', return_value=opener), patch('promo_finder.providers.time.sleep'):
            with self.assertRaises(RateLimitError) as caught:
                p.complete('prompt', {})
        self.assertNotIn('SECRET',str(caught.exception))
        self.assertNotIn('Provider asks',str(caught.exception))

    def test_repeated_limits_stop_after_two_retries(self):
        p = ChatProvider('https://example.com/api', 'model')
        opener = MagicMock()
        opener.open.side_effect = [limited(), limited(), limited()]
        with patch('promo_finder.providers.urllib.request.build_opener', return_value=opener), patch('promo_finder.providers.time.sleep'):
            with self.assertRaises(RateLimitError):
                p.complete('prompt', {})
        self.assertEqual(opener.open.call_count, 3)

    def test_authentication_failure_is_never_retried(self):
        p = ChatProvider('https://example.com/api', 'model')
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError('https://example.com/api', 401, 'auth', {}, io.BytesIO(b'SECRET'))
        with patch('promo_finder.providers.urllib.request.build_opener', return_value=opener), patch('promo_finder.providers.time.sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'Authentication failed'):
                p.complete('prompt', {})
        self.assertEqual(opener.open.call_count, 1)
        sleep.assert_not_called()

    def test_retry_header_fallbacks_and_non_finite_are_bounded(self):
        self.assertEqual(retry_delay({}, 0), 30)
        self.assertEqual(retry_delay({'Retry-After': 'invalid'}, 1), 60)
        self.assertGreater(retry_delay({'Retry-After': 'NaN'}, 0), 120)
        self.assertGreater(retry_delay({'Retry-After': 'Wed, 01 Jan 2100 00:00:00 GMT'}, 0), 120)


if __name__ == '__main__':
    unittest.main()
