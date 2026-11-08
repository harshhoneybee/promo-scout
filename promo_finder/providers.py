"""Small swappable model adapter. Credentials come from environment, never outputs."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


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
    if exc.code == 403:
        return prefix + 'Access denied; no recognized detailed error code. Check model permissions in the provider console, then contact provider support if access is allowed.'
    return prefix + 'Check model availability and endpoint configuration. Provider response text was withheld to protect credentials and scripts.'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to an unexpected host.


class ChatProvider:
    def __init__(self, url, model, api_key='', style='compatible', timeout=120):
        parsed = urlparse(url)
        if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Set a valid API endpoint URL without embedded credentials')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost','127.0.0.1','::1'):
            raise ValueError('Remote providers require HTTPS')
        if style not in ('compatible','ollama'):
            raise ValueError('API style must be compatible or ollama')
        if not model.strip():
            raise ValueError('Set PROMO_MODEL')
        self.url, self.model, self.api_key, self.style, self.timeout = url,model,api_key,style,timeout

    @classmethod
    def from_env(cls):
        url = os.environ.get('PROMO_API_URL','')
        model = os.environ.get('PROMO_MODEL','')
        if not url or not model:
            raise ValueError('AI mode requires PROMO_API_URL and PROMO_MODEL; see README')
        return cls(url,model,os.environ.get('PROMO_API_KEY',''),os.environ.get('PROMO_API_STYLE','compatible'))

    def complete(self, system, payload):
        messages = [{'role':'system','content':system},
                    {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
        body = {'model':self.model,'messages':messages,'stream':False}
        if self.style == 'ollama':
            body.update(format='json',options={'temperature':0.2})
        else:
            body.update(temperature=0.2,max_tokens=1800)
        headers = {'Content-Type':'application/json', 'Accept':'application/json',
                   'User-Agent':'PromoScout/0.1 (+https://github.com/harshhoneybee/promo-scout)'}
        if self.api_key:
            headers['Authorization'] = 'Bearer ' + self.api_key
        request = urllib.request.Request(self.url,json.dumps(body).encode(),headers,method='POST')
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                data = response.read(2_000_001)
                if len(data)>2_000_000:
                    raise RuntimeError('Provider response exceeds 2 MB limit')
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(http_error_message(exc)) from None
        except (urllib.error.URLError,TimeoutError,OSError):
            raise RuntimeError('Provider connection failed or timed out. No baseline was substituted.') from None
        except (ValueError,UnicodeError):
            raise RuntimeError('Provider response was not valid JSON') from None

    def content(self, response):
        try:
            result = response['message']['content'] if self.style=='ollama' else response['choices'][0]['message']['content']
            if not isinstance(result,str):
                raise TypeError()
            return result
        except (KeyError,IndexError,TypeError):
            raise ValueError('Provider response does not contain text in the expected format') from None
