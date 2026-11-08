"""Private local checkpoints of complete model responses, without API credentials."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ResponseCheckpoints:
    def __init__(self, directory):
        self.directory = Path(directory)

    @classmethod
    def from_env(cls):
        if os.environ.get('PROMO_CACHE', '1') == '0':
            return None
        return cls(Path(__file__).resolve().parent.parent / 'outputs' / 'ai-checkpoints')

    def key(self, provider, system, payload):
        # Endpoint affects identity but is hashed, never written verbatim. Keys are omitted.
        return digest({'version': 1, 'endpoint': provider.url, 'style': provider.style,
                       'model': provider.model, 'settings': provider.settings(),
                       'system': system, 'input': payload})

    def get(self, key):
        try:
            saved = json.loads((self.directory / (key + '.json')).read_text(encoding='utf-8'))
            if (isinstance(saved, dict) and saved.get('key') == key
                    and isinstance(saved.get('response'), dict)
                    and isinstance(saved.get('saved_at'), str)
                    and digest(saved['response']) == saved.get('response_sha256')):
                return saved
        except (OSError, ValueError):
            pass  # Missing, interrupted or corrupt checkpoint: request again.
        return None

    def put(self, key, response):
        saved = {'key': key, 'saved_at': datetime.now(timezone.utc).isoformat(),
                 'response': response, 'response_sha256': digest(response)}
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory,
                                             suffix='.tmp', delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(saved, handle, ensure_ascii=False)
            os.replace(temp_path, self.directory / (key + '.json'))
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return saved
