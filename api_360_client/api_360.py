import logging
from http import HTTPStatus
import time

import requests
from tqdm import tqdm

from .exceptions import API360Error
from .models.user import User, Users, TwoFAStatus
from .models.mail_user_settings import SenderInfo


class API360:
    BASE_URL = 'https://api360.yandex.net'
    TIMEOUT = 1
    USERS_PER_PAGE = 1000

    def __init__(self, token: str, org_id: int):
        self.org_id = org_id
        self.sess = requests.Session()
        self.sess.headers.update({'Authorization': f'OAuth {token}'})

    @staticmethod
    def raise_for_status(response: requests.Response):
        match response.status_code:
            case HTTPStatus.UNAUTHORIZED:
                raise API360Error(f'Unauthorized. {response.text}')
            case HTTPStatus.FORBIDDEN:
                raise API360Error(f'Forbidden. {response.text}')
        response.raise_for_status()

    def _get_users_page(self, page: int) -> str:
        url = f'{self.BASE_URL}/directory/v1/org/{self.org_id}/users'
        params = {'page': page, 'perPage': self.USERS_PER_PAGE}
        resp = self.sess.get(url, params=params)
        return resp.text

    def get_users(self) -> list[User]:
        current_page = 1

        resp_data = self._get_users_page(current_page)
        users_page = Users.model_validate_json(resp_data)
        users = users_page.users
        pages = users_page.pages
        current_page += 1

        for page in tqdm(
                range(current_page, pages + 1),
                initial=1,
                total=pages,
                desc='Getting users',
                unit='page'):
            resp_data = self._get_users_page(page)
            users_page = Users.model_validate_json(resp_data)
            users.extend(users_page.users)
            time.sleep(self.TIMEOUT)
        return users

    def get_two_fa_status(self, user: User) -> TwoFAStatus:
        url = f'https://api360.yandex.net/directory/v1/org/{self.org_id}/users/{user.id}/2fa'
        resp = self.sess.get(url)
        logging.debug(f'{resp.status_code} GET {url}: {resp.text}')
        self.raise_for_status(resp)
        two_fa_status = TwoFAStatus.model_validate_json(resp.text)
        return two_fa_status

    def get_sender_info(self, user: User) -> SenderInfo:
        url = f'{self.BASE_URL}/admin/v1/org/{self.org_id}/mail/users/{user.id}/settings/sender_info'
        resp = self.sess.get(url)
        logging.debug(f'{resp.status_code} GET {url}: {resp.text}')
        self.raise_for_status(resp)
        sender_info = SenderInfo.model_validate_json(resp.text)
        return sender_info

    def update_sender_info(self, user: User, sender_info: SenderInfo) -> SenderInfo:
        url = f'{self.BASE_URL}/admin/v1/org/{self.org_id}/mail/users/{user.id}/settings/sender_info'
        data = sender_info.model_dump(mode='json', by_alias=True)
        resp = self.sess.post(url, json=data)
        logging.debug(f'POST {url} {resp.request.body}\n{resp.status_code} {resp.text}')
        self.raise_for_status(resp)
        sender_info = SenderInfo.model_validate_json(resp.text)
        return sender_info
