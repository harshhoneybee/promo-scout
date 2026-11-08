"""Small swappable model adapter. Credentials come from environment, never outputs."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


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
        headers = {'Content-Type':'application/json'}
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
            # Provider error bodies can contain sensitive request or account information.
            raise RuntimeError(f'Provider HTTP {exc.code}. Check credentials, model availability, rate limits and endpoint configuration.') from None
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
