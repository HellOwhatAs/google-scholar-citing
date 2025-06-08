from main import browser, BeautifulSoup, show_messages
from tqdm import tqdm
import pyfilecache
import json
import urllib.parse


@pyfilecache.file_cache
def find_author(author_url: str):
    browser.get(author_url)

    soup = BeautifulSoup(browser.page_source, "lxml")
    while soup.select_one("#gsc_prf_i") is None:
        show_messages()
        soup = BeautifulSoup(browser.page_source, "lxml")

    name = soup.select_one("#gsc_prf_in").text

    _cited_cnt = soup.select_one(
        "#gsc_rsb_st > tbody > tr:nth-child(1) > td:nth-child(2)"
    )
    cited_cnt = _cited_cnt.text if _cited_cnt is not None else "0"

    affliation = soup.select_one("#gsc_prf_i > div:nth-child(2)").text

    _ivh = soup.select_one("#gsc_prf_ivh")
    domain = _ivh.text
    _a = _ivh.select_one("a")
    profile = _a.get("href") if _a is not None else None

    return {
        "name": name,
        "cited_cnt": cited_cnt,
        "affliation": affliation,
        "domain": domain,
        "profile": profile,
        "url": author_url,
    }


if __name__ == "__main__":
    with open("./citing_papers.json", "rb") as f:
        citing_papers: list[
            tuple[str, str, str | dict[str, str | list[dict[str, str]]]]
        ] = json.load(f)

    citing_authors = sorted(
        set(
            urllib.parse.urljoin("https://scholar.google.com", author["href"])
            for _, _, papers in citing_papers
            for paper in papers
            if not isinstance(paper, str)
            for author in paper["authors"]
        )
    )

    status404 = {
        "https://scholar.google.com/citations?user=MD61m08AAAAJ&hl=zh-CN&oi=sra",
    }

    citing_authors_result = {}
    for author_url in tqdm(citing_authors):
        if author_url in status404:
            continue

        citing_authors_result[
            {
                i[: i.find("=")]: i[i.find("=") + 1 :]
                for i in urllib.parse.urlparse(author_url).query.split("&")
            }["user"]
        ] = find_author(author_url)

    with open("./citing_authors.json", "w", encoding="utf-8") as f:
        json.dump(citing_authors_result, f, ensure_ascii=False, indent=4)
