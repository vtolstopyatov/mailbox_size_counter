import time

import requests

from .models.user import User


class UserToken:
    _token = None
    _expires = None

    def __init__(self, client_id: str, client_secret: str, user: User):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user = user

    def __repr__(self):
        return self.token

    def _get_token(self):
        payload = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
            'client_id': f'{self.client_id}',
            'client_secret': f'{self.client_secret}',
            'subject_token': f'{self.user.id}',
            'subject_token_type': 'urn:yandex:params:oauth:token-type:uid',
        }
        r = requests.post('https://oauth.yandex.ru/token', data=payload)
        self._expires_at = time.time() + r.json().get('expires_in')
        self._token = r.json().get('access_token')

    @property
    def token(self):
        if self._token and self._expires_at > time.time():
            return self._token
        else:
            self._get_token()
        return self._token
