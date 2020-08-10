# -*- coding: utf-8 -*-

import json
import requests
import sys
import time
import traceback

from configparser import ConfigParser
from datetime import datetime
from enum import Enum
from http.cookiejar import CookieJar
from html.parser import HTMLParser
from logging import basicConfig, getLogger, StreamHandler, INFO
from pathlib import Path
from typing import Dict, Iterable, List, Set
from urllib.parse import urljoin, urlparse
from urllib.request import build_opener, HTTPCookieProcessor

# 定数宣言
FANTIA_URL_PREFIX = 'https://fantia.jp/'
FANTIA_API_ENDPOINT = urljoin(FANTIA_URL_PREFIX, '/api/v1')
POSTED_AT_FORMAT = '%a, %d %b %Y %H:%M:%S %z'

# logger
script_file_path = Path(__file__)
basicConfig(filename=script_file_path.with_suffix('.log'), level=INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = getLogger(__name__)
logger.addHandler(StreamHandler(sys.stdout))

# config読み込み
ini_file_path = script_file_path.with_suffix('.ini')
config: ConfigParser = ConfigParser()
config.read(ini_file_path.absolute(), encoding='UTF-8')
fantia_config = config['fantia']

cookies = {'_session_id': fantia_config['session_id'].strip()}
fan_club_id: str = fantia_config['fan_club_id'].strip()
download_interval_seconds: int = int(
    fantia_config['download_interval_seconds'])
download_root_dir_path: Path = Path(fantia_config['download_root_dir'])
download_root_dir: Path = download_root_dir_path if download_root_dir_path.is_absolute(
) else (script_file_path.parent / download_root_dir_path).absolute()


def get_attr_value_by_name(attrs: List[tuple], attr_name: str) -> str:
    attr = tuple(filter(lambda attr: attr[0] == attr_name, attrs))
    return attr[0][1] if attr else None


def get_url_last_path(url: str) -> str:
    return urlparse(url).path.split('/')[-1]


def download_interval() -> None:
    time.sleep(download_interval_seconds)


class FantiaFanClubsParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.posts_urls: List[str] = []
        self.max_page_number: int = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def handle_starttag(self, tag, attrs):
        self.page_link = False

        if tag == 'a':
            for attr in attrs:
                if attr[0] != 'class':
                    continue

                if attr[1] == 'link-block':
                    self.posts_urls.append(
                        get_attr_value_by_name(attrs, 'href'))
                    break
                elif attr[1] == 'page-link':
                    page_link_url = get_attr_value_by_name(attrs, 'href')
                    if page_link_url:
                        self.max_page_number = int(page_link_url.split('=')[1])
                        break


class FantiaPostsParser:
    def __init__(self):
        self.download_dir_name: str = None
        self.original_uris: Set[str] = set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def feed(self, data: str):
        '''
        {
            post: {
                id: '<POST_ID>'
                posted_at: 'Wed, 1 Jan 2020 9:00:00 +0900',
                post_contents: [{
                        post_content_photos: [{
                                show_original_uri: '/posts/<POST_ID>/post_content_photo/<CONTENT_ID>'
                        },]
                },]
            }
        }
        '''
        posts: Dict[any] = json.loads(data)['post']

        # download_dir_name
        posted_at = datetime.strptime(posts['posted_at'], POSTED_AT_FORMAT)
        self.download_dir_name = '{}_{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(
            posts['id'],
            posted_at.year, posted_at.month, posted_at.day,
            posted_at.hour, posted_at.minute, posted_at.second
        )

        # original_uri
        post_contents: List[dict] = posts['post_contents']
        for post_content in post_contents:
            post_content_photos: List[dict] = post_content.get(
                'post_content_photos')
            if post_content_photos:
                for post_content_photo in post_content_photos:
                    self.original_uris.add(
                        post_content_photo['show_original_uri'])

    def close(self):
        None


class FantiaOriginalUriParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.src = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.src = get_attr_value_by_name(attrs, 'src')


def original_url_parse(download_dir_name: str, original_uri: str) -> None:
    download_interval()
    original_uri_response = requests.get(
        urljoin(FANTIA_URL_PREFIX, original_uri), cookies=cookies)

    with FantiaOriginalUriParser() as original_uri_parser:
        original_uri_parser.feed(original_uri_response.text)
        original_uri_response = requests.get(
            original_uri_parser.src, cookies=cookies)

        # filename などがヘッダーから取得できないため、URLから名前を取得する
        original_file_extension: Path = Path(
            get_url_last_path(original_uri_parser.src)).suffix
        download_file_name: str = get_url_last_path(
            original_uri) + original_file_extension

        # デフォルトのファイル名はUUIDのため、original_uriの末尾をファイル名とする
        download_dir: Path = download_root_dir / fan_club_id / download_dir_name

        if not download_dir.is_dir():
            download_dir.mkdir(parents=True)

        download_file_path: str = str(download_dir / download_file_name)

        with open(download_file_path, 'wb') as download_file:
            download_file.write(original_uri_response.content)
            logger.info(
                f'image [{original_uri}] download to [{download_file_path}].')


def posts_parse(posts_url: str) -> None:
    # 直接開くと動的ページとなるが、APIでJSONを呼び出し可能
    posts_api_url = FANTIA_API_ENDPOINT + posts_url
    posts_response = requests.get(posts_api_url, cookies=cookies)

    with FantiaPostsParser() as posts_parser:
        posts_parser.feed(posts_response.text)
        original_uris = posts_parser.original_uris

        if original_uris:
            original_uri_count = len(original_uris)
            download_dir_name = posts_parser.download_dir_name

            for i, original_uri in enumerate(original_uris, 1):
                original_url_parse(download_dir_name, original_uri)
        else:
            logger.info(f'original uri empty. posts url [posts_url] ')


def fan_clubs_page_parse(fan_clubs_url: str, page_number: int) -> None:
    fan_clubs_params = {'page': page_number}
    fan_clubs_response = requests.get(
        fan_clubs_url, params=fan_clubs_params, cookies=cookies)

    with FantiaFanClubsParser() as fan_clubs_parser:
        fan_clubs_parser.feed(fan_clubs_response.text)
        posts_urls = fan_clubs_parser.posts_urls
        posts_count = len(posts_urls)

        for i, posts_url in enumerate(posts_urls, 1):
            log_message = f'post {i}/{posts_count}: [{posts_url}] parse '
            logger.info(log_message + 'start.')
            posts_parse(posts_url)
            logger.info(log_message + 'end.')


def fan_clubs_parse(fan_club_id: str) -> None:
    fan_clubs_url: str = urljoin(
        FANTIA_URL_PREFIX, f'/fanclubs/{fan_club_id}/posts')
    fan_clubs_response = requests.get(fan_clubs_url, cookies=cookies)

    with FantiaFanClubsParser() as fan_clubs_parser:
        fan_clubs_parser.feed(fan_clubs_response.text)
        max_page_number = fan_clubs_parser.max_page_number

    for i in range(max_page_number):
        page_number = i + 1
        log_message = f'page {page_number}/{max_page_number} parse '
        logger.info(log_message + 'start.')
        fan_clubs_page_parse(fan_clubs_url, page_number)
        logger.info(log_message + 'end.')


def main():
    log_message = f'fan club [{fan_club_id}] parse '
    logger.info(log_message + 'start.')
    fan_clubs_parse(fan_club_id)
    logger.info(log_message + 'end.')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        sys.exit(0)
