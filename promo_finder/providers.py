"""Small swappable model adapter. Credentials come from environment, never outputs."""
import json
import os
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import urllib.error
import urllib.request
from urllib.parse import urlparse


class RateLimitError(RuntimeError):
    """Pause new requests; completed episodes can be resumed from checkpoints."""


def retry_delay(headers, attempt):
    """Honor Retry-After seconds or HTTP date; never retry before the stated time."""
    value = headers.get('Retry-After') if headers else None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            seconds = 30 * (attempt + 1)
    if not math.isfinite(seconds):
        return 121
    return max(1, math.ceil(seconds))


def promo_response_format():
    """Strict output shape; semantic and timestamp checks remain in Python."""
    properties = {key: {'type': 'string'} for key in (
        'start_event', 'end_event', 'hook_event', 'cliffhanger_event',
        'hook', 'cliffhanger', 'why')}
    properties['scores'] = {
        'type': 'object', 'properties': {key: {'type': 'number'} for key in ('hook', 'cliffhanger', 'clarity')},
        'required': ['hook', 'cliffhanger', 'clarity'], 'additionalProperties': False,
    }
    candidate = {'type': 'object', 'properties': properties,
                 'required': list(properties), 'additionalProperties': False}
    return {'type': 'json_schema', 'json_schema': {
        'name': 'promo_candidates', 'strict': True,
        'schema': {'type': 'object', 'properties': {'candidates': {'type': 'array', 'items': candidate}},
                   'required': ['candidates'], 'additionalProperties': False},
    }}


def http_error_message(exc):
    """Map known error codes to safe diagnostics; never echo provider text or keys."""
    try:
        raw = exc.read(16_384).decode('utf-8', errors='replace')
    except (OSError, ValueError):
        raw = ''
    try:
        parsed = json.loads(raw)
        error = parsed.get('error', {}) if isinstance(parsed, dict) else {}
        error = error if isinstance(error, dict) else {}
        code, kind = error.get('code'), error.get('type')
    except ValueError:
        code, kind = None, None
    prefix = f'Provider HTTP {exc.code}. '
    if code == 'model_permission_blocked_org':
        return prefix + 'Model blocked by organization permissions. Check the selected model under Groq Settings > Organization > Limits.'
    if code == 'model_permission_blocked_project':
        return prefix + 'Model blocked by project permissions. Check the selected model under Groq Settings > Projects > Limits.'
    if exc.code == 403 and ('error code: 1010' in raw.lower() or 'error 1010' in raw.lower()):
        return prefix + 'Provider gateway rejected the API client (1010). Contact provider support with this code; changing the key may not help.'
    if exc.code == 403 and kind == 'permissions_error':
        return prefix + 'Provider permissions error. Check organization and project model access.'
    if exc.code == 401:
        return prefix + 'Authentication failed. Check PROMO_API_KEY locally; never share the key.'
    if exc.code == 429:
        return prefix + 'Rate limit reached. Check your provider quota and retry after its reset time.'
    if exc.code == 413:
        return prefix + 'Request is too large for the provider limit. Waiting alone will not reduce its size. Use the latest compact-request update; if it persists, a smaller input or higher request limit is needed. Your API key is not the cause of this error.'
    if exc.code == 403:
        return prefix + 'Access denied; no recognized detailed error code. Check model permissions in the provider console, then contact provider support if access is allowed.'
    return prefix + 'Check model availability and endpoint configuration. Provider response text was withheld to protect credentials and scripts.'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to an unexpected host.


class ChatProvider:
    def __init__(self, url, model, api_key='', style='compatible', timeout=120, max_output_tokens=4096):
        parsed = urlparse(url)
        if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Set a valid API endpoint URL without embedded credentials')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost','127.0.0.1','::1'):
            raise ValueError('Remote providers require HTTPS')
        if style not in ('compatible','ollama'):
            raise ValueError('API style must be compatible or ollama')
        if not model.strip():
            raise ValueError('Set PROMO_MODEL')
        if type(max_output_tokens) is not int or not 256 <= max_output_tokens <= 32768:
            raise ValueError('PROMO_MAX_OUTPUT_TOKENS must be an integer between 256 and 32768')
        self.url, self.model, self.api_key, self.style, self.timeout = url,model,api_key,style,timeout
        self.max_output_tokens = max_output_tokens
        self.groq_gpt_oss = (style == 'compatible' and parsed.hostname == 'api.groq.com'
                            and model in ('openai/gpt-oss-120b', 'openai/gpt-oss-20b'))

    @classmethod
    def from_env(cls):
        url = os.environ.get('PROMO_API_URL','')
        model = os.environ.get('PROMO_MODEL','')
        if not url or not model:
            raise ValueError('AI mode requires PROMO_API_URL and PROMO_MODEL; see README')
        try:
            limit = int(os.environ.get('PROMO_MAX_OUTPUT_TOKENS', '4096'))
        except ValueError:
            raise ValueError('PROMO_MAX_OUTPUT_TOKENS must be an integer between 256 and 32768') from None
        return cls(url,model,os.environ.get('PROMO_API_KEY',''),os.environ.get('PROMO_API_STYLE','compatible'),max_output_tokens=limit)

    def settings(self):
        """Safe, reproducible generation settings; excludes URL and credentials."""
        if self.style == 'ollama':
            return {'format': 'json', 'options': {'temperature': 0.2, 'num_predict': self.max_output_tokens}}
        if self.groq_gpt_oss:
            return {'temperature': 0.2, 'max_completion_tokens': self.max_output_tokens,
                    'reasoning_effort': 'low', 'include_reasoning': False,
                    'response_format': promo_response_format()}
        return {'temperature': 0.2, 'max_tokens': self.max_output_tokens}

    def complete(self, system, payload):
        self.last_request = {'attempts': 0, 'rate_limit_wait_seconds': 0}
        messages = [{'role':'system','content':system},
                    {'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}]
        body = {'model':self.model,'messages':messages,'stream':False}
        body.update(self.settings())
        headers = {'Content-Type':'application/json', 'Accept':'application/json',
                   'User-Agent':'PromoScout/0.1 (+https://github.com/harshhoneybee/promo-scout)'}
        if self.api_key:
            headers['Authorization'] = 'Bearer ' + self.api_key
        request = urllib.request.Request(self.url,json.dumps(body,ensure_ascii=False,separators=(',',':')).encode(),headers,method='POST')
        for attempt in range(3):
            self.last_request['attempts'] += 1
            try:
                with urllib.request.build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                    data = response.read(2_000_001)
                    if len(data)>2_000_000:
                        raise RuntimeError('Provider response exceeds 2 MB limit')
                    return json.loads(data)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    delay = retry_delay(exc.headers, attempt)
                    exc.close()
                    if attempt < 2 and self.last_request['rate_limit_wait_seconds'] + delay <= 120:
                        self.last_request['rate_limit_wait_seconds'] += delay
                        time.sleep(delay)
                        continue
                    hint = ''
                    try:
                        seconds = float(exc.headers.get('Retry-After', ''))
                        if math.isfinite(seconds) and seconds >= 0:
                            seconds = math.ceil(seconds)
                            self.last_request['retry_after_seconds'] = seconds
                            hint = f'Provider asks you to wait at least {seconds} seconds before retrying. '
                    except (TypeError, ValueError, AttributeError):
                        pass
                    raise RateLimitError('Provider HTTP 429. Rate limit persists. ' + hint + 'New requests paused; completed episodes are checkpointed when enabled. Wait for your provider quota to reset, then rerun the same file.') from None
                raise RuntimeError(http_error_message(exc)) from None
            except (urllib.error.URLError,TimeoutError,OSError):
                raise RuntimeError('Provider connection failed or timed out. No baseline was substituted.') from None
            except (ValueError,UnicodeError):
                raise RuntimeError('Provider response was not valid JSON') from None

    def content(self, response):
        try:
            choice = response if self.style == 'ollama' else response['choices'][0]
            reason = choice.get('done_reason') if self.style == 'ollama' else choice.get('finish_reason')
            message = choice['message']
            result = message.get('content')
            refused = message.get('refusal') or reason == 'content_filter'
        except (KeyError,IndexError,TypeError,AttributeError):
            raise ValueError('Provider response does not contain text in the expected format') from None
        if reason == 'length':
            raise ValueError('Model reached its output token limit before completing the answer. Increase PROMO_MAX_OUTPUT_TOKENS, restart, and rerun the demo. The original response is preserved in Full run JSON.')
        if refused:
            raise ValueError('The model declined this request. Inspect the original response in Full run JSON.')
        if not isinstance(result,str):
            raise ValueError('Provider response does not contain text in the expected format')
        if not result.strip():
            raise ValueError('Model returned no final answer. Inspect finish_reason and usage in Full run JSON.')
        return result
