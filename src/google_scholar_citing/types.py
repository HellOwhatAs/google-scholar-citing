from typing import TypedDict


class Author(TypedDict):
    name: str
    href: str


class DetailedAuthor(TypedDict):
    name: str
    cited_cnt: str
    affliation: str
    domain: str
    profile: str
    url: str


class PublishedPaper(TypedDict):
    title: str
    href: str
    metadata: list[str]
    cited_count: str
    citing_href: str
    year: str


class CitingPaper(TypedDict):
    title: str
    href: str
    id: str
    authors: list[Author]


class SearchedPaper(TypedDict):
    title: str
    href: str
    authors: list[Author]
    authors_raw: str
    metadata: list[str]
    cited_count: str
