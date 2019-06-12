from typing import List, Any, Dict
import json
import logging
import time
import pathlib
import concurrent.futures
import re
import base64
import itertools

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from languages import language

logging.basicConfig(
    format="[%(asctime)s]\t%(levelname)s\t|\t%(message)s", level=logging.INFO
)

pool = concurrent.futures.ThreadPoolExecutor(max_workers=20)

LDS_BASE_URL = "https://www.churchofjesuschrist.org"
SCRIPTURES_BASE_URL = f"{LDS_BASE_URL}/study/scriptures"


class NoPrimaryContentFoundError(Exception):
    pass


class NoRetriesLeftError(Exception):
    pass


class NoTranslationAvailableError(Exception):
    pass


def get_reader_store(url: str) -> Dict[str, Any]:
    logging.info(f"Requesting {url}...")
    retries = 5
    html_doc = None
    while retries:
        try:
            response: requests.Response = requests.get(url)
            html_doc = response.text
            soup = BeautifulSoup(html_doc, "html5lib")
            scripts = soup.find_all("script")

            initial_state_script = None
            for script in scripts:
                if "__INITIAL_STATE__" in str(script):
                    initial_state_script = str(script)
                    break
            if not initial_state_script:
                raise NoPrimaryContentFoundError

            match = re.search(
                r'window.__INITIAL_STATE__ = "(.*?)";', initial_state_script
            )
            if not match:
                raise NoPrimaryContentFoundError

            groups = match.groups()
            if not groups:
                raise NoPrimaryContentFoundError

            initial_state_b64 = groups[0]
            assert isinstance(initial_state_b64, str)
            initial_state_json = base64.b64decode(initial_state_b64)
            initial_state = json.loads(initial_state_json)
            return initial_state["reader"]
        except NoPrimaryContentFoundError:
            logging.warning(f"Retrying to make a request to {url}...")
            retries -= 1
            time.sleep(2)
            continue
    raise NoRetriesLeftError(html_doc)


def _get_striped_paragraphs(text: str) -> List[str]:
    return [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]


def get_entries(store: Dict[str, Any], excluded: List[str]) -> List[Dict[str, Any]]:
    entries = []

    for item in store["entries"]:
        if "section" in item:
            sub_entries = get_entries(item["section"], excluded)
            entries.append(
                {
                    "type": "section",
                    "title": item["section"]["title"],
                    "entries": sub_entries,
                }
            )
        elif "content" in item:
            if item["content"]["uri"] in excluded:
                continue
            entries.append(
                {
                    "type": "content",
                    "title": item["content"]["title"],
                    "uri": item["content"]["uri"],
                }
            )
        else:
            raise NotImplementedError

    return entries


def get_uris_from_entries(entries: List[Dict[str, Any]]) -> List[str]:
    uris = []

    for entry in entries:
        if "uri" in entry:
            uris.append(entry["uri"])
        if "entries" in entry:
            uris.extend(get_uris_from_entries(entry["entries"]))

    return uris


def get_books(
    scripture_main_url: str, lang: language, excluded_books: List[str]
) -> Dict[str, Any]:
    logging.info(f"Getting books for {lang} language...")
    reader: Dict[str, Any] = get_reader_store(f"{scripture_main_url}?lang={lang.value}")

    active_book = reader["activeBook"]
    book_store = reader["bookStore"][active_book]
    scripture_title = book_store["title"]
    scripture_uri = book_store["uri"]
    scripture_structure = get_entries(book_store, excluded_books)

    scripture_uris = get_uris_from_entries(scripture_structure)

    contents = list(pool.map(get_content, scripture_uris, itertools.repeat(lang)))

    contents_dict = {content["uri"]: content for content in contents}

    return {
        "title": scripture_title,
        "uri": scripture_uri,
        "structure": scripture_structure,
        "contents": contents_dict,
    }


def get_content(uri: str, lang: language) -> Dict[str, Any]:
    logging.info(f"Getting contents for {uri}...")
    reader = get_reader_store(f"{LDS_BASE_URL}{uri}?lang={lang.value}")

    active_content = reader["activeContent"]

    content_store = reader["contentStore"][active_content]

    content_title = content_store["meta"]["title"]
    content_data_type = content_store["meta"]["pageAttributes"]["data-content-type"]

    data = {"uri": uri, "title": content_title, "data_type": content_data_type}

    soup = BeautifulSoup(content_store["content"]["body"], "html5lib")

    chapter_name = soup.select_one("p.title-number")
    if chapter_name:
        data["chapter_name"] = chapter_name.text.strip()

    chapter_summary = soup.select_one("p.study-summary")
    if chapter_summary:
        data["chapter_summary"] = _get_striped_paragraphs(chapter_summary.text)

    book_title = soup.select_one("h1#title1")
    if book_title and book_title != content_title:
        data["book_title"] = book_title.text.strip()

    book_intro = soup.select_one("p.intro")
    if book_intro:
        data["book_intro"] = _get_striped_paragraphs(book_intro.text)

    subtitle = soup.select_one("p.subtitle")
    if subtitle:
        data["subtitle"] = _get_striped_paragraphs(subtitle.text)

    body_block: Tag = soup.select_one("div.body-block")
    assert body_block is not None

    verses = body_block.select("p.verse")
    if verses:
        verses_data = []

        for verse in verses:
            verse_number: int = int(
                verse.find("span", class_="verse-number").text.strip()
            )
            for tag in verse.find_all("sup", class_="marker"):
                tag.clear()
            for tag in verse.find_all("span", class_="verse-number"):
                tag.clear()
            verses_data.append({"number": verse_number, "text": verse.text.strip()})

        data["verses"] = verses_data
    else:
        paragraphs = body_block.select("p")
        data["text"] = [p.text.strip() for p in paragraphs]

    return data


if __name__ == "__main__":
    scripture = "bofm"
    default_excluded = {"bofm": ["/study/scriptures/bofm/illustrations"]}
    logging.info(f"Starting {scripture}...")
    output_dir = pathlib.Path("output")
    output_dir.mkdir(exist_ok=True)

    for lang in language:
        scripture_main_url = f"{SCRIPTURES_BASE_URL}/{scripture}"
        logging.info("=" * 40)
        logging.info(f"Downloading {lang}...")
        output_json: pathlib.Path = output_dir / f"{scripture}-{lang.value}.json"
        if output_json.exists():
            logging.info(f"File already exists, skipping.")
            continue

        retries = 3
        while retries:
            try:
                books = get_books(
                    scripture_main_url, lang, default_excluded.get(scripture, [])
                )
            except Exception as e:
                if isinstance(e, NoTranslationAvailableError):
                    logging.error(f"No translation available for {lang}, skipping.")
                    break
                else:
                    logging.exception(f"Some error occured, retrying...")
                    retries -= 1
                    time.sleep(10)
            else:
                logging.info(f"Saving JSON data for {lang}...")
                with output_json.open("w") as f:
                    json.dump(books, f, ensure_ascii=False, indent=4)
                break
        else:
            raise NoRetriesLeftError
