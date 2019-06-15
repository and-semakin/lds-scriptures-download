# LDS scriptures in JSON #

In this repo you can find standard work of The Church of Jesus Christ of Latter-day Saints in machine-readable JSON format:
* Book of Mormon;
* Doctrine and Covenants;
* Pearl of Great Price.

Text was scraped from [official church site](https://www.churchofjesuschrist.org/study/scriptures?lang=eng).

Also in this repo you can find scripts to download texts again.

Installation:

1. Clone repo
2. `pipenv install`
3. `pipenv shell`
4. Run `python download.py ...` (see next section).

## Usage: ##

```sh
usage: download.py [-h] [-l [LANG [LANG ...]]]
                   [-s [SCRIPTURE [SCRIPTURE ...]]] [-o] [-t THREADS]
                   destination

Download standard works of the Church of Jesus Christ of Latter-day Saints in
machine-readable JSON format.

positional arguments:
  destination           path to save JSON files

optional arguments:
  -h, --help            show this help message and exit
  -l [LANG [LANG ...]], --languages [LANG [LANG ...]]
                        list of languages to download; allowed values are
                        3-letters language key-codes: eng, spa, rus, fra...
  -s [SCRIPTURE [SCRIPTURE ...]], --scriptures [SCRIPTURE [SCRIPTURE ...]]
                        list of scriptures to download; allowed values: bofm,
                        dc-testament, pgp
  -o, --overwrite       overwrite files if they exist
  -t THREADS, --threads THREADS
                        number of threads to download in parallel
```

## Examples: ##

Download all scriptures in all available languages, then save it to `output` folder:

```sh
python download.py output
```

Download all scriptures in Russian and Ukrainian languages:

```sh
python download.py output -l rus ukr
```

Download only Book of Mormon and D&C in Turkish language:

```sh
python download.py output -l tur -s bofm dc-testament
```

The same but overwrite existing file:

```sh
python download.py output -l tur -s bofm --overwrite
```

Optionally you can specify how many parallel threads will work (default: 30):

```sh
python download.py output -t 50
```

## JSON structure ##

Root object of output JSON file has following keys:

* `title` - localized title of the book;
* `uri` - unique identifier of the book;
* `structure` - book structure tree, array of nested `StructureRecord`'s (will be described later);
* `contents` - mapping (unordered, may be in some random order) from content's `uri` to `ContentRecord` (will be described later).

Each `StructureRecord` is an object with following keys:

* `type` - may be `section` or `content`;
* `title` - localized title of book, section or chapter;
* `entries` - child objects, array of `StructureRecord`; may be only when `type` is `section`;
* `uri` - unique identifier of the content (this `uri`s are keys in `contents` mapping).

Each `ContentRecord` is an object with following keys:

* `uri` - unique identifier of content (the same as key);
* `title` - localized title of section or chapter;
* `data_type` - may be `book`, `chapter` or `figure`;
* `book_title` - localized title of book, usually appears in first chapter of any book;
* `subtitle` - localized subtitle of book, usually appears in first chapter of some books; array of strings;
* `book_intro` - book summary, usually appears in first chapter of any book; array of strings;
* `chapter_name` - localized chapter name, i.e. "Chapter 1";
* `chapter_summary` - localized summary of chapter; array of strings;
* `text` - if content doesn't have verses, text will be placed here, each paragraph in separate string; array of strings;
* `verses` - if content has verses, text will be placed here, each verse in separate object; array of `Verse` objects.

Each `Verse` is an object with following keys:

* `number` - sequential number of verse in chapter, starting from 1;
* `text` - text of the verse; string;


Example:

```json
{
    "title": "Test Book",
    "uri": "/scriptures/test-book",
    "structure": [
        {
            "type": "section",
            "title": "The Book of Nephi",
            "entries": [
                {
                    "type": "content",
                    "title": "Chapter 1",
                    "uri": "/scriptures/test-book/ne/1"
                },
                {
                    "type": "content",
                    "title": "Chapter 2",
                    "uri": "/scriptures/test-book/ne/2"
                },
            ],
        },
        {
            "type": "content",
            "title": "Official Declaration",
            "uri": "/scriptures/test-book/od"
        }
    ],
    "contents": {
        "/scriptures/test-book/ne/1": {
            "uri": "/scriptures/test-book/ne/1",
            "title": "Chapter 1",
            "data_type": "chapter",
            "book_title": "The Book of Nephi",
            "subtitle": ["His Reign and Ministry"],
            "chapter_name": "Chapter 1",
            "chapter_summary": [
                "summary",
                "summary"
            ],
            "verses": [
                {
                    "number": 1,
                    "text": "Therefore...",
                }
            ]
        },
        "/scriptures/test-book/ne/2": {
            "uri": "/scriptures/test-book/ne/2",
            "title": "Chapter 2",
            "data_type": "chapter",
            "chapter_name": "Chapter 2",
            "chapter_summary": [
                "summary",
                "summary"
            ],
            "verses": [
                {
                    "number": 1,
                    "text": "Therefore...",
                }
            ]
        },
        "/scriptures/test-book/od": {
            "uri": "/scriptures/test-book/od",
            "title": "Official Declaration",
            "data_type": "chapter",
            "chapter_name": "Chapter 2",
            "text": [
                "Official Declaration",
                "of the First Presidency of the Church...",
                "We declare to the world that..."
            ],
        }
    }
}
```
