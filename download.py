from typing import List, Optional, Any, Dict
import json
import logging
import dataclasses
import time
import pathlib
import copy

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from languages import language

logging.basicConfig(
    format="[%(asctime)s]\t%(levelname)s\t|\t%(message)s", level=logging.INFO
)

book_main_url = "https://www.lds.org/scriptures/bofm"


@dataclasses.dataclass
class ChapterEntry:
    url: str
    name: str
    summary: List[str]
    verses: List[str]

    def _asdict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "name": self.name,
            "summary": copy.copy(self.summary),
            "verses": copy.copy(self.verses),
        }


@dataclasses.dataclass
class BookEntry:
    url: str
    id: str
    full_localized_name: str
    has_chapters: bool = True
    chapters: Optional[List[ChapterEntry]] = None
    summary: Optional[List[str]] = None
    text: Optional[List[str]] = None

    def _asdict(self) -> Dict[str, Any]:
        chapters = (
            [chapter._asdict() for chapter in self.chapters] if self.chapters else None
        )
        return {
            "url": self.url,
            "id": self.id,
            "full_localized_name": self.full_localized_name,
            "has_chapters": self.has_chapters,
            "chapters": chapters,
            "summary": copy.copy(self.summary),
            "text": copy.copy(self.text),
        }


class NoPrimaryContentFoundError(Exception):
    pass


class NoRetriesLeftError(Exception):
    pass


class NoTranslationAvailableError(Exception):
    pass


def get_primary_content(url: str) -> Tag:
    logging.info(f"Requesting {url}...")
    retries = 5
    while retries:
        try:
            response: requests.Response = requests.get(url)
            html_doc = response.text
            soup = BeautifulSoup(html_doc, "html5lib")
            primary_content = soup.find(id="primary")
            if primary_content is None:
                raise NoPrimaryContentFoundError
            return primary_content
        except NoPrimaryContentFoundError:
            logging.warning(f"Retrying to make a request to {url}...")
            retries -= 1
            time.sleep(2)
            continue
    raise NoRetriesLeftError(html_doc)


def _get_striped_paragraphs(text: str) -> List[str]:
    return [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]


def book_has_chapters(book_url: str, book_main_content: Tag) -> bool:
    book_url = book_url.split("?lang")[0]
    book_url_last_section = book_url.split("/")[-1]
    book_url_contains_chapter_number = True
    try:
        int(book_url_last_section)
    except ValueError:
        book_url_contains_chapter_number = False
    return (
        book_main_content.find("div", class_="chapters") is not None
        or book_url_contains_chapter_number
    )


def get_books(lang: language, excluded_books=["illustrations"]) -> List[Dict[str, Any]]:
    logging.info(f"Getting books for {lang} language...")
    primary_content: Tag = get_primary_content(f"{book_main_url}?lang={lang.value}")
    toc: Tag = primary_content.find(class_="table-of-contents")
    book_entries = []
    for link in toc.select("li > a.tocEntry"):
        li: Tag = link.parent
        book_url: str = link["href"]

        # check if book is available in lang
        book_url_lang: str = book_url.split("lang=")[1]
        if book_url_lang.lower() != lang.value:
            raise NoTranslationAvailableError(lang)

        # check if link is a valid book
        try:
            book_id: str = li["id"]
        except AttributeError:
            logging.warning(f"Book at {book_url} has no id, skipping.")
            continue

        # do not save books in excluded books list
        if book_id in excluded_books:
            continue

        book_name: str = link.string
        book_contents: Tag = get_primary_content(book_url)
        if book_has_chapters(book_url, book_contents):
            # Here should go any scripture text.
            # Text will be considered to contain chapters and verses.
            book_chapters: List[ChapterEntry] = get_chapters(book_url, book_contents)
            book_summary_tag: Tag = book_contents.select_one("div.bookSummary")
            book_summary: List[str] = _get_striped_paragraphs(
                book_summary_tag.text
            ) if book_summary_tag else []
            book_entries.append(
                BookEntry(
                    url=book_url,
                    id=book_id,
                    full_localized_name=book_name,
                    has_chapters=True,
                    chapters=book_chapters,
                    summary=book_summary,
                )
            )
        else:
            # Here should go any auxiliary text.
            # Text will be considered to contain paragraphs.
            text = book_contents.text
            paragraphs: List[str] = _get_striped_paragraphs(text)
            book_entries.append(
                BookEntry(
                    url=book_url,
                    id=book_id,
                    full_localized_name=book_name,
                    has_chapters=False,
                    text=paragraphs,
                )
            )
    books = [book._asdict() for book in book_entries]
    return books


def get_chapters(book_url: str, book_contents: Tag) -> List[ChapterEntry]:
    logging.info(f"Getting chapters for {book_url}...")
    book_url_without_lang = book_url.split("?lang")[0]
    book_url_last_section = book_url_without_lang.split("/")[-1]
    book_url_contains_chapter_number = True
    try:
        int(book_url_last_section)
    except ValueError:
        book_url_contains_chapter_number = False

    if book_url_contains_chapter_number:
        return [get_chapter_data(url=book_url, chapter_contents=book_contents)]

    chapters_list: Tag = book_contents.select_one("ul.jump-to-chapter")
    assert chapters_list
    chapters: List[ChapterEntry] = []
    for link in chapters_list.find_all("a"):
        chapter_url: str = link["href"]
        chapter_contents = get_primary_content(chapter_url)
        chapters.append(get_chapter_data(chapter_url, chapter_contents))

    return chapters


def get_chapter_data(url: str, chapter_contents: Tag) -> ChapterEntry:
    logging.info(f"Getting verses for chapter on {url}...")
    try:
        chapter_name_tag: Tag = chapter_contents.select_one(".title-number")
        chapter_name: str = chapter_name_tag.text
        chapter_summary: List[str] = _get_striped_paragraphs(
            chapter_contents.select_one(".study-summary").text
        )
        article: Tag = chapter_contents.select_one("div.article")
        for tag in article.find_all("sup", class_="studyNoteMarker"):
            tag.clear()
        for tag in article.find_all("span", class_="verse-number"):
            tag.clear()

        verses = _get_striped_paragraphs(article.text)
        return ChapterEntry(
            url=url, name=chapter_name, summary=chapter_summary, verses=verses
        )
    except AttributeError:
        logging.error(f"Some attributes are missing on page: {str(chapter_contents)}")
        raise


if __name__ == "__main__":
    logging.info("Starting...")
    output_dir = pathlib.Path("output")
    output_dir.mkdir(exist_ok=True)
    for lang in language:
        retries = 3
        while retries:
            try:
                logging.info("=" * 40)
                logging.info(f"Downloading {lang}...")
                output_json: pathlib.Path = output_dir / f"bom-{lang.value}.json"
                if output_json.exists():
                    logging.info(f"File already exists, skipping.")
                    break
                books = get_books(lang)
                with output_json.open("w") as f:
                    json.dump(books, f, ensure_ascii=False, indent=4)
            except Exception as e:
                if isinstance(e, NoTranslationAvailableError):
                    logging.error(f"No translation available for {lang}, skipping.")
                    break
                else:
                    retries -= 1
                    time.sleep(10)
            else:
                break
        else:
            raise NoRetriesLeftError
