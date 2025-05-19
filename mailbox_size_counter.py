import asyncio
import csv
import logging
import os
import re
import time
from dataclasses import dataclass

from aioimaplib import aioimaplib
from dotenv import load_dotenv
from tqdm.asyncio import tqdm

from api_360_client import API360, UserToken
from api_360_client.models.user import User

IMAP_FETCH_PAGE_SIZE = 100
IMAP_MAX_CONNS = 30


@dataclass
class Cfg:
    CLIENT_ID: str
    CLIENT_SECRET: str
    semaphore: asyncio.Semaphore
    csv_file_path: str


class IMAPError(Exception):
    pass


async def imap_mailbox_size_counter(user: User, cfg: Cfg):
    imap_server = "imap.yandex.ru"
    token = UserToken(cfg.CLIENT_ID, cfg.CLIENT_SECRET, user)

    imap = aioimaplib.IMAP4_SSL(host=imap_server, timeout=60)
    await imap.wait_hello_from_server()
    await imap.xoauth2(user.email, token.token)

    size_correct = True

    status, folders_data = await imap.list('""', "*")
    if status != "OK":
        logging.error(f"{user.email} - Не удалось получить список папок")
        size_correct = False
        raise IMAPError("Не удалось получить список папок")

    folders = []
    for folder_info in folders_data:
        if isinstance(folder_info, bytes):
            folder_match = re.search(
                r'^\(([^\)]+)\)\s"([\W])"\s(.+)$',
                folder_info.decode("utf-8"),
            )
            if folder_match:
                folder_name = folder_match.group(3)
                folders.append(folder_name)
            elif folder_info == b"LIST Completed.":
                continue
            else:
                size_correct = False
                logging.error(
                    f"{user.email} - Ошибка парсинга названия папки"
                    f": {folder_info}"
                )
        else:
            size_correct = False
            logging.error(
                f"{user.email} - Неверный тип данных ответа: {folder_info}"
            )

    total_size_all_folders = 0
    total_messages = 0
    for folder in folders:
        try:
            status, data = await imap.select(folder)
            if status != "OK":
                size_correct = False
                logging.error(
                    f"{user.email} - Не удалось выбрать папку '{folder}'"
                )
                continue

            if isinstance(data, list):
                for i in data:
                    if isinstance(i, bytes):
                        exists_match = re.search(
                            r"^(\d+) EXISTS$",
                            i.decode("utf-8"),
                        )
                        if exists_match:
                            total_folder_messages = int(exists_match.group(1))
                            total_messages += total_folder_messages
                            break
                else:
                    size_correct = False
                    logging.error(
                        f"{user.email} - Не удалось получить список писем "
                        f"'в папке '{folder}'"
                    )
                    continue
            else:
                size_correct = False
                logging.error(
                    f"{user.email} - Неверный тип данных ответа: {data}"
                )
                continue

            total_size = 0
            for page in range(1, total_folder_messages, IMAP_FETCH_PAGE_SIZE):
                status, fetch_data = await imap.fetch(
                    f"{page}:{page+IMAP_FETCH_PAGE_SIZE-1}",
                    "(RFC822.SIZE)",
                )
                if status != "OK":
                    size_correct = False
                    logging.error(
                        f"{user.email} - Не удалось получить размеры писем "
                        f"в папке '{folder}'"
                    )
                    continue

                for item in fetch_data:
                    if isinstance(item, bytes):
                        response = item.decode("utf-8")
                        size_match = re.search(r"RFC822\.SIZE (\d+)", response)
                        if size_match:
                            total_size += int(size_match.group(1))

            total_size_all_folders += total_size
        except Exception as e:
            size_correct = False
            logging.error(
                f"{user.email} - Ошибка при обработке папки '{folder}' {e}"
            )
            continue

    result = (
        user.email,
        total_messages,
        f"{total_size_all_folders / 1024 / 1024 / 1024:.2f}",
        size_correct,
    )
    append_csv(cfg.csv_file_path, result)

    try:
        await imap.logout()
    except Exception as e:
        logging.error(f"{user.email} - Ошибка завершения IMAP сессии {e}")
        print(f"{user.email} - Ошибка завершения IMAP сессии {e}")


async def mailbox_size_counter(user: User, cfg: Cfg):
    async with cfg.semaphore:
        try:
            await imap_mailbox_size_counter(user, cfg)
        except Exception as e:
            tqdm.write(
                f"{user.email} - Ошибка при обработке почтового ящика {e}"
            )
            logging.error(
                f"{user.email} - Ошибка при обработке почтового ящика {e}"
            )


def append_csv(file_path: str, row: list):
    with open(file_path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        writer.writerow(row)


def append_error(file_path: str, error: str):

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(error)


async def main():
    load_dotenv()
    TOKEN = os.getenv("TOKEN")
    ORG_ID = os.getenv("ORG_ID")
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")

    client = API360(token=TOKEN, org_id=ORG_ID)
    users = client.get_users()

    unix_time = round(time.time())
    csv_file_path = os.path.join(
        os.path.dirname(__file__),
        f"mailbox_sizes_{unix_time}.csv",
    )
    field_names = [
        "email",
        "messages_count",
        "mailbox_size_gb",
        "size_is_correct",
    ]
    append_csv(csv_file_path, field_names)

    semaphore = asyncio.Semaphore(IMAP_MAX_CONNS)
    cfg = Cfg(CLIENT_ID, CLIENT_SECRET, semaphore, csv_file_path)

    tasks = []
    for user in users:
        if user.id >= 1130000000000000 and user.is_enabled:
            tasks.append(
                asyncio.ensure_future(mailbox_size_counter(user, cfg))
            )
    await tqdm.gather(*tasks, desc="Getting mailbox sizes", unit="user")


if __name__ == "__main__":
    log_file = os.path.join(
        os.path.dirname(__file__),
        "mailbox_size_counter.log",
    )

    logging.basicConfig(
        filename=log_file,
        encoding="utf-8",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
    )

    asyncio.run(main())
