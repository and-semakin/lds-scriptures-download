from typing import List, Optional
import json
import logging
import dataclasses

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


@dataclasses.dataclass
class BookEntry:
    url: str
    id: str
    full_localized_name: str
    has_chapters: bool = True
    chapters: Optional[List[ChapterEntry]] = None
    summary: Optional[List[str]] = None
    text: Optional[List[str]] = None


def dataclass_to_json(o):
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    raise TypeError


def get_primary_content(url: str) -> Tag:
    logging.info(f"Requesting {url}...")
    response: requests.Response = requests.get(url)
    html_doc = response.text
    soup = BeautifulSoup(html_doc, "html5lib")
    primary_content = soup.find(id="primary")
    return primary_content


def _get_striped_paragraphs(text: str) -> List[str]:
    return [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]


def book_has_chapters(book_url: str, book_main_content: Tag) -> bool:
    logging.info(f"Checking if book has chapters: {book_url}")
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


def get_books(lang: language) -> List[BookEntry]:
    logging.info(f"Getting books for {lang} language...")
    primary_content: Tag = get_primary_content(f"{book_main_url}?lang={lang.value}")
    toc: Tag = primary_content.find(class_="table-of-contents")
    book_entries = []
    for link in toc.select("li > a.tocEntry"):
        li: Tag = link.parent
        book_url: str = link["href"]
        book_id: str = li["id"]
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
    return book_entries


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
    chapter_name: str = chapter_contents.select_one(".title-number").text
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


if __name__ == "__main__":
    logging.info("Starting...")
    lang = language.RUS
    books = get_books(lang)
    # url = "https://www.lds.org/scriptures/bofm/1-ne?lang=rus"
    # book_contents = get_primary_content(url)
    # chapters = get_chapters(url, book_contents)
    with open("bom-rus.json", "w") as f:
        json.dump(books, f, default=dataclass_to_json, ensure_ascii=False)
