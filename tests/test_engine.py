"""Behavioral tests use wholly synthetic source and model responses."""
import copy
import json
import unittest
from unittest.mock import patch

from promo_finder.engine import run, validate_candidate, rank_candidates
from promo_finder.parser import Event, Episode
from promo_finder.providers import ChatProvider


def episode(number=1):
    return Episode(number, 'synthetic.txt', '', '', 65.0, [
        Event('e001', 'dialogue', 'A', 0.0, 4.0, 'The letter was stolen.'),
        Event('e002', 'action', '', 4.0, 22.0, 'The messenger searches the room.'),
        Event('e003', 'dialogue', 'B', 22.0, 30.0, 'Who opened the locked drawer?'),
        Event('e004', 'dialogue', 'A', 35.0, 40.0, 'It was empty.'),
        Event('e005', 'action', '', 45.0, 65.0, 'A shadow waits outside.'),
    ])


def candidate():
    return {
        'start_event': 'e001', 'end_event': 'e003', 'hook_event': 'e001',
        'cliffhanger_event': 'e003', 'hook': 'A theft is revealed.',
        'cliffhanger': 'Who opened the drawer?', 'why': 'A compact mystery.',
        'scores': {'hook': 4, 'cliffhanger': 4, 'clarity': 4},
    }


class FakeProvider:
    model = 'synthetic-test-model'

    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, system, payload):
        self.calls.append((system, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return copy.deepcopy(self.response)

    def content(self, response):
        return response['choices'][0]['message']['content']


def response(candidates):
    return {'id': 'test-output', 'choices': [{'message': {'content': json.dumps({'candidates': candidates})}}]}


class EngineTests(unittest.TestCase):
    def test_duration_uses_wall_clock_not_sum_of_overlapping_events(self):
        ep = episode()
        ep.events.append(Event('e006', 'camera', '', 0, 30, 'A continuous camera shot.'))
        result, errors = validate_candidate(ep, candidate())
        self.assertEqual(errors, [])
        self.assertEqual(result['duration'], 30)
        self.assertEqual(result['score'], 80)
        self.assertEqual(result['segments'], [{'episode': 1, 'start': '00:00.00', 'end': '00:30.00'}])

    def test_invented_event_ids_are_rejected(self):
        for field in ['start_event', 'end_event', 'hook_event', 'cliffhanger_event']:
            proposed = candidate()
            proposed[field] = 'invented'
            with self.subTest(field=field):
                result, errors = validate_candidate(episode(), proposed)
                self.assertIsNone(result)
                self.assertIn('Unknown ' + field, errors)

    def test_cut_through_other_overlapping_dialogue_rejected(self):
        ep = episode()
        ep.events.append(Event('e006', 'dialogue', 'C', 28, 32, 'An overlapping complete sentence.'))
        result, errors = validate_candidate(ep, candidate())
        self.assertIsNone(result)
        self.assertIn('Boundary cuts a spoken line', errors)

    def test_start_cut_through_spoken_line_rejected(self):
        ep = episode()
        ep.events[0].start = 2
        ep.events.append(Event('e006', 'dialogue', 'C', 0, 3, 'An earlier line.'))
        result, errors = validate_candidate(ep, candidate())
        self.assertIsNone(result)
        self.assertIn('Boundary cuts a spoken line', errors)

    def test_late_hook_is_rejected(self):
        proposed = candidate()
        proposed['hook_event'] = 'e002'
        result, errors = validate_candidate(episode(), proposed)
        self.assertIsNone(result)
        self.assertTrue(any('first 3 seconds' in e for e in errors))

    def test_hook_that_extends_past_cut_is_rejected(self):
        ep = episode()
        ep.events.append(Event('e006', 'action', '', 1, 34, 'An action extending past the cut.'))
        proposed = candidate()
        proposed['hook_event'] = 'e006'
        result, errors = validate_candidate(ep, proposed)
        self.assertIsNone(result)
        self.assertTrue(any('Hook evidence' in e for e in errors))

    def test_cliffhanger_must_be_at_end(self):
        proposed = candidate()
        proposed['cliffhanger_event'] = 'e001'
        result, errors = validate_candidate(episode(), proposed)
        self.assertIsNone(result)
        self.assertTrue(any('final 5 seconds' in e for e in errors))

    def test_out_of_episode_cut_rejected(self):
        ep = episode()
        ep.duration = 29
        result, errors = validate_candidate(ep, candidate())
        self.assertIsNone(result)
        self.assertIn('Clip outside episode bounds', errors)

    def test_nonfinite_boolean_and_missing_scores_rejected(self):
        for invalid in [True, float('nan'), float('inf'), -1, 6, '5', None]:
            proposed = candidate()
            proposed['scores']['hook'] = invalid
            with self.subTest(invalid=invalid):
                result, errors = validate_candidate(episode(), proposed)
                self.assertIsNone(result)
                self.assertTrue(any('Invalid hook score' in e for e in errors))

    def test_duration_validation_precedes_display_rounding(self):
        for end in [19.996, 60.004]:
            ep = episode()
            ep.events = [Event('e001', 'dialogue', 'A', 0, 2, 'A theft.'),
                         Event('e002', 'action', '', end - 2, end, 'A mysterious arrival.')]
            proposed = candidate()
            proposed.update(end_event='e002', cliffhanger_event='e002')
            with self.subTest(end=end):
                result, errors = validate_candidate(ep, proposed)
                self.assertIsNone(result)
                self.assertIn('Duration must be 20-60 seconds', errors)

    def test_rejected_model_output_keeps_raw_response(self):
        bad = candidate()
        bad['start_event'] = 'imaginary'
        raw = response([bad, candidate()])
        provider = FakeProvider(raw)
        result = run([episode()], mode='ai', provider=provider)
        self.assertEqual(result['raw_responses'][0]['response'], raw)
        self.assertEqual(result['rejected'][0]['candidate'], bad)
        self.assertEqual(result['meta']['counts']['rejected'], 1)
        self.assertEqual(result['meta']['counts']['selected'], 1)
        self.assertEqual(result['meta']['model'], provider.model)

    def test_malformed_model_json_is_audited_and_not_replaced_with_baseline(self):
        raw = {'choices': [{'message': {'content': 'this is not JSON'}}]}
        with patch('promo_finder.engine.baseline_candidates', side_effect=AssertionError('must not run')):
            result = run([episode()], mode='ai', provider=FakeProvider(raw))
        self.assertEqual(result['promos'], [])
        self.assertEqual(result['meta']['episodes_succeeded'], 0)
        self.assertEqual(result['raw_responses'][0]['response'], raw)
        self.assertTrue(result['episodes'][0]['error'])

    def test_provider_error_is_audited_and_all_episodes_attempted(self):
        provider = FakeProvider(RuntimeError('Synthetic connection failure'))
        with patch('promo_finder.engine.baseline_candidates', side_effect=AssertionError('must not run')):
            result = run([episode(1), episode(2)], mode='ai', provider=provider)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(result['meta']['episodes_processed'], 2)
        self.assertEqual(result['meta']['episodes_succeeded'], 0)
        self.assertEqual(result['promos'], [])
        self.assertEqual(result['raw_responses'][0]['error'], 'Synthetic connection failure')

    def test_explicit_empty_model_selection_is_successful_abstention(self):
        result = run([episode()], mode='ai', provider=FakeProvider(response([])))
        self.assertEqual(result['meta']['episodes_succeeded'], 1)
        self.assertEqual(result['promos'], [])
        self.assertEqual(result['meta']['counts']['proposed'], 0)

    def test_near_duplicates_removed_within_episode_only(self):
        candidates = [
            {'episode': 1, 'start': 0, 'end': 30, 'duration': 30, 'score': 90},
            {'episode': 1, 'start': 5, 'end': 35, 'duration': 30, 'score': 80},
            {'episode': 1, 'start': 40, 'end': 65, 'duration': 25, 'score': 70},
            {'episode': 2, 'start': 0, 'end': 30, 'duration': 30, 'score': 85},
        ]
        selected = rank_candidates(candidates, 10)
        self.assertEqual([(c['episode'], c['start']) for c in selected], [(1, 0), (2, 0), (1, 40)])
        self.assertEqual([c['rank'] for c in selected], [1, 2, 3])
        self.assertNotIn('rank', candidates[0])

    def test_ai_requires_explicit_provider(self):
        with self.assertRaisesRegex(ValueError, 'configured provider'):
            run([episode()], mode='ai')

    def test_bad_top_count_rejected_before_model_calls(self):
        provider = FakeProvider(response([]))
        for top in [0, 101, True, 1.5]:
            with self.subTest(top=top), self.assertRaises(ValueError):
                run([episode()], mode='ai', provider=provider, top_k=top)
        self.assertEqual(provider.calls, [])


class ProviderTests(unittest.TestCase):
    def test_remote_http_and_embedded_credentials_rejected(self):
        for endpoint in ['http://example.com/chat', 'https://user:password@example.com/chat']:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                ChatProvider(endpoint, 'test')

    def test_response_shape_validation(self):
        provider = ChatProvider('http://localhost:11434/api/chat', 'test', style='ollama')
        self.assertEqual(provider.content({'message': {'content': '{}'}}), '{}')
        for malformed in [{}, {'message': {}}, {'message': {'content': None}}]:
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                provider.content(malformed)


if __name__ == '__main__':
    unittest.main()
