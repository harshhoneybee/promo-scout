"""Regression cases mirror observed API structure, without copying private responses."""
import copy
import json
import unittest
from unittest.mock import MagicMock, patch
from promo_finder.providers import ChatProvider
from promo_finder.parser import Event, Episode
from promo_finder.engine import run

GROQ_URL='https://api.groq.com/openai/v1/chat/completions'


def result(content='',reason='stop',**message):
    return {'choices':[{'finish_reason':reason,'message':{'content':content,**message}}]}


class ModelOutputTests(unittest.TestCase):
    def test_groq_reasoning_has_budget_low_effort_and_strict_json(self):
        p=ChatProvider(GROQ_URL,'openai/gpt-oss-120b')
        config=p.settings()
        self.assertEqual(config['max_completion_tokens'],4096)
        self.assertEqual(config['reasoning_effort'],'low')
        self.assertFalse(config['include_reasoning'])
        self.assertTrue(config['response_format']['json_schema']['strict'])
        schema=config['response_format']['json_schema']['schema']
        for obj in [schema,schema['properties']['candidates']['items'],schema['properties']['candidates']['items']['properties']['scores']]:
            self.assertFalse(obj['additionalProperties'])
            self.assertEqual(set(obj['required']),set(obj['properties']))

    def test_other_providers_do_not_receive_groq_only_parameters(self):
        p=ChatProvider('https://example.com/v1/chat/completions','openai/gpt-oss-120b')
        self.assertEqual(p.settings(),{'temperature':0.2,'max_tokens':4096})
        p=ChatProvider('http://localhost:11434/api/chat','test',style='ollama')
        self.assertEqual(p.settings()['options']['num_predict'],4096)

    def test_request_uses_new_settings_and_still_preserves_raw_response(self):
        p=ChatProvider(GROQ_URL,'openai/gpt-oss-120b',api_key='SECRET')
        response=result('{"candidates":[]}')
        stream=MagicMock();stream.__enter__.return_value.read.return_value=json.dumps(response).encode()
        opener=MagicMock();opener.open.return_value=stream
        with patch('promo_finder.providers.urllib.request.build_opener',return_value=opener):
            self.assertEqual(p.complete('Return JSON',{}),response)
        sent=json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(sent['max_completion_tokens'],4096)
        self.assertIn('response_format',sent)
        self.assertNotIn('SECRET',json.dumps(p.settings()))

    def test_empty_length_limited_answer_gets_specific_error_and_preserves_raw(self):
        p=ChatProvider(GROQ_URL,'openai/gpt-oss-120b')
        raw=result('', 'length')
        raw['usage']={'completion_tokens':1800,'completion_tokens_details':{'reasoning_tokens':1798}}
        ep=Episode(1,'synthetic.txt','','',30,[Event('e001','action','',0,30,'A courier arrives.')])
        before=copy.deepcopy(raw)
        with patch.object(p,'complete',return_value=raw):
            report=run([ep],mode='ai',provider=p)
        self.assertIn('output token limit',report['episodes'][0]['error'])
        self.assertEqual(report['raw_responses'][0]['response'],before)
        self.assertEqual(report['meta']['episodes_succeeded'],0)
        self.assertEqual(report['raw_responses'][0]['request']['generation']['max_completion_tokens'],4096)

    def test_valid_looking_but_truncated_answer_is_not_accepted(self):
        p=ChatProvider(GROQ_URL,'openai/gpt-oss-120b')
        with self.assertRaisesRegex(ValueError,'output token limit'):
            p.content(result('{"candidates":[]}', 'length'))

    def test_empty_refusal_and_malformed_shape_are_distinct(self):
        p=ChatProvider(GROQ_URL,'openai/gpt-oss-120b')
        for response,pattern in [(result(''),'no final answer'),(result('',refusal='Declined'),'declined'),({'choices':[]},'expected format')]:
            with self.subTest(pattern=pattern), self.assertRaisesRegex(ValueError,pattern):
                p.content(response)

    def test_complete_answer_is_unchanged(self):
        p=ChatProvider(GROQ_URL,'openai/gpt-oss-120b')
        text=' {"candidates": []} '
        self.assertEqual(p.content(result(text)),text)

    def test_bad_token_limit_is_rejected(self):
        for limit in [True,0,1800.5,100000]:
            with self.subTest(limit=limit),self.assertRaises(ValueError):
                ChatProvider(GROQ_URL,'openai/gpt-oss-120b',max_output_tokens=limit)


if __name__=='__main__':unittest.main()
