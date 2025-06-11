from selenium.webdriver.chromium.webdriver import ChromiumDriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import shelve
import functools
import json
import urllib.parse
import tkinter as tk
from tkinter import messagebox
from functools import partial
from typing import Callable


def shelved_cache(func, path: str):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with shelve.open(path) as cache:
            key = f"{func.__name__}:{args}:{kwargs}"
            if key in cache:
                return json.loads(cache[key])
            result = func(*args, **kwargs)
            if result is not None:
                cache[key] = json.dumps(result)
            return result

    return wrapper


def default_webdriver() -> ChromiumDriver:
    from selenium.webdriver import Edge as Driver
    from selenium.webdriver.edge.service import Service
    from selenium.webdriver.edge.options import Options
    from webdriver_manager.microsoft import EdgeChromiumDriverManager as DriverManager

    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = Driver(
        options=options,
        service=Service(DriverManager().install()),
    )
    driver.implicitly_wait(30)
    return driver


class default_page_error_handler:
    def __init__(self):
        self.root = tk.Tk()
        self.root.wm_attributes("-topmost", 1)
        self.root.withdraw()

    def __call__(self, soup: BeautifulSoup):
        return messagebox.askretrycancel(
            "来人啊",
            "队友呢队友呢，救一下啊",
            parent=self.root,
        )


class Scholar:
    def __init__(
        self,
        page_error_handler: Callable[
            [BeautifulSoup], bool
        ] = default_page_error_handler(),
        webdriver: ChromiumDriver = None,
        cache_path: str = "__google-scholar-citing",
        auto_reload: int = 2,
        reload_interval: float = 1.0,
    ):
        self.cache_path = cache_path
        self.page_error_handler = page_error_handler
        self.browser = default_webdriver() if webdriver is None else webdriver
        self.auto_reload = auto_reload
        self.reload_interval = reload_interval

        cache_func = partial(shelved_cache, path=self.cache_path)
        self.get_published_papers = cache_func(self.get_published_papers)
        self._cur_citing_papers = cache_func(self._cur_citing_papers)
        self.get_author = cache_func(self.get_author)
        self.get_papers = cache_func(self.get_papers)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        return self.browser.__exit__(*args, **kwargs)

    def quit(self):
        self.browser.quit()

    @staticmethod
    def _next_citing_page_url(url: str, step: int = 10):
        parsed_url = urllib.parse.urlparse(url)
        queries = [
            [i[: i.find("=")], i[i.find("=") + 1 :]]
            for i in parsed_url.query.split("&")
        ]
        for i in queries:
            if i[0] == "start":
                i[1] = str(int(i[1]) + step)
                break
        else:
            queries.insert(0, ["start", str(step)])
        return parsed_url._replace(
            query="&".join([f"{k}={v}" for k, v in queries])
        ).geturl()

    def get_page_soup(self, css_selector: str):
        reload_count = 0
        while True:
            page_source = self.browser.page_source
            soup = BeautifulSoup(page_source, "lxml")
            if soup.select_one(css_selector) is not None:
                return soup
            if reload_count >= self.auto_reload:
                if not self.page_error_handler(soup):
                    return None
            else:
                reload_count += 1
                time.sleep(self.reload_interval)

    def get_published_papers(self, user_id: str):
        self.browser.get(f"https://scholar.google.com/citations?user={user_id}")
        soup = self.get_page_soup("#gsc_prf_i")
        if soup is None:
            return None

        more_button = self.browser.find_element(By.ID, "gsc_bpf_more")
        while more_button.get_attribute("disabled") is None:
            more_button.click()
            time.sleep(2)

        citing_hrefs = []
        for paper in self.browser.find_elements(By.CSS_SELECTOR, "#gsc_a_b > tr"):
            title_a = paper.find_element(By.CSS_SELECTOR, "td.gsc_a_t > a")
            cited_a = paper.find_element(By.CSS_SELECTOR, "td.gsc_a_c > a")
            citing_hrefs.append(
                {
                    "title": title_a.text,
                    "href": title_a.get_attribute("href"),
                    "metadata": [
                        i.text
                        for i in paper.find_elements(
                            By.CSS_SELECTOR, "td.gsc_a_t > div"
                        )
                    ],
                    "cited_count": cited_a.text,
                    "citing_href": cited_a.get_attribute("href"),
                    "year": paper.find_element(By.CSS_SELECTOR, "td.gsc_a_y").text,
                }
            )

        return citing_hrefs

    def _cur_citing_papers(self, current_url: str):
        self.browser.get(current_url)
        soup = self.get_page_soup("#gs_res_ccl_mid")
        if soup is None:
            return None

        res = []
        papers = soup.select("#gs_res_ccl_mid > div")
        for paper in papers:
            a_paper = paper.select_one("div.gs_ri > h3 > a")
            if a_paper is None:
                res.append(paper.prettify())
                continue
            print(a_paper.text)
            res.append(
                {
                    "title": a_paper.text,
                    "href": a_paper.get("href"),
                    "id": a_paper.get("id"),
                    "authors": [
                        {"name": author.text, "href": author.get("href")}
                        for author in paper.select("div.gs_a > a")
                    ],
                }
            )
        return res

    def get_citing_papers(self, citing_href: str):
        citing_papers = []
        cur_url = citing_href
        while True:
            cur_page: list = self._cur_citing_papers(cur_url)
            citing_papers.extend(cur_page)
            if len(cur_page) < 10:
                break
            cur_url = self._next_citing_page_url(cur_url)
        return citing_papers

    def get_author(self, author_url: str):
        self.browser.get(author_url)
        soup = self.get_page_soup("#gsc_prf_i")
        if soup is None:
            return None

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

    def get_papers(self, title: str):
        url = "https://scholar.google.com/scholar?hl=zh-CN&q=" + urllib.parse.quote(
            title
        )
        self.browser.get(url)
        soup = self.get_page_soup("#gs_res_ccl_mid")
        if soup is None:
            return None

        result_papers: list[dict] = []
        for paper in soup.select("#gs_res_ccl_mid > div > div.gs_ri"):
            title_h3 = paper.select_one("h3.gs_rt")
            title_a = title_h3.select_one("a")

            if paper.select_one("div.gs_fmaa") is not None:
                authors = [
                    {"name": author.text, "href": author.get("href")}
                    for author in paper.select("div.gs_fmaa > a")
                ]
                gs_fmaa = paper.select_one("div.gs_fmaa")
                authors_raw = gs_fmaa.prettify()
                metadata = [i.text for i in gs_fmaa.next_siblings]
            else:
                authors = [
                    {"name": author.text, "href": author.get("href")}
                    for author in paper.select("div.gs_a > a")
                ]
                authors_raw = paper.select_one("div.gs_a").prettify()
                metadata = None

            cited_count: str = paper.select_one(
                "div.gs_fl.gs_flb > a:nth-child(3)"
            ).text

            result_papers.append(
                {
                    "title": title_h3.text,
                    "href": title_a.get("href") if title_a is not None else None,
                    "authors": authors,
                    "authors_raw": authors_raw,
                    "metadata": metadata,
                    "cited_count": cited_count,
                }
            )

        return result_papers


if __name__ == "__main__":
    from itertools import chain

    with Scholar() as scholar:
        papers = scholar.get_published_papers("zv2GUHEAAAAJ")

        for paper in papers:
            citing_href = paper["citing_href"]
            if not citing_href:
                continue

            paper["citing_papers"] = scholar.get_citing_papers(citing_href)

            for citing_paper in paper["citing_papers"]:
                citing_paper: dict
                if isinstance(citing_paper, str):
                    continue

                citing_paper["searched"] = scholar.get_papers(citing_paper["title"])

                for author in chain.from_iterable(
                    (
                        citing_paper["authors"],
                        *(i["authors"] for i in citing_paper["searched"]),
                    )
                ):
                    author: dict
                    author_url = urllib.parse.urljoin(
                        "https://scholar.google.com", author["href"]
                    )
                    author.update(scholar.get_author(author_url))

    with open("citing_papers.json", "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=4)
