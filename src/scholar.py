from selenium.webdriver import Edge as Driver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.microsoft import EdgeChromiumDriverManager as DriverManager
from bs4 import BeautifulSoup
import time
import shelve
import functools
import json
import urllib.parse
import tkinter as tk
from tkinter import messagebox
from functools import partial


def shelved_method_cache(func, path: str):
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


class Scholar:
    def __init__(self, cache_path: str = "__google-scholar-citing"):
        self.cache_path = cache_path
        self.root = tk.Tk()
        self.root.wm_attributes("-topmost", 1)
        self.root.withdraw()

        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.browser = Driver(
            options=options,
            service=Service(DriverManager().install()),
        )
        self.browser.implicitly_wait(30)

        cache_func = partial(shelved_method_cache, path=self.cache_path)
        self.get_published_papers = cache_func(self.get_published_papers)
        self.cur_citing_papers = cache_func(self.cur_citing_papers)
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

    def show_messages(self, msg: str = "队友呢队友呢，救一下啊"):
        return messagebox.askretrycancel("来人啊", msg, parent=self.root)

    def get_published_papers(self, user_id: str):
        self.browser.get(f"https://scholar.google.com/citations?user={user_id}")

        while True:
            soup = BeautifulSoup(self.browser.page_source, "lxml")
            if soup.select_one("#gsc_prf_i") is not None:
                break
            if not self.show_messages():
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

    def cur_citing_papers(self, current_url: str):
        self.browser.get(current_url)

        while True:
            soup = BeautifulSoup(self.browser.page_source, "lxml")
            if soup.select_one("#gs_res_ccl_mid") is not None:
                break
            if not self.show_messages():
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
            cur_page: list = self.cur_citing_papers(cur_url)
            citing_papers.extend(cur_page)
            if len(cur_page) < 10:
                break
            cur_url = self._next_citing_page_url(cur_url)
        return citing_papers

    def get_author(self, author_url: str):
        self.browser.get(author_url)

        while True:
            soup = BeautifulSoup(self.browser.page_source, "lxml")
            if soup.select_one("#gsc_prf_i") is not None:
                break
            if not self.show_messages():
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

        while True:
            soup = BeautifulSoup(self.browser.page_source, "lxml")
            if soup.select_one("#gs_res_ccl_mid") is not None:
                break
            if not self.show_messages():
                return None

        result_papers: list[dict] = []
        for paper in soup.select("#gs_res_ccl_mid > div > div.gs_ri"):
            title_h3 = paper.select_one("h3.gs_rt")
            title_a = title_h3.select_one("a")
            authors = [
                {"name": author.text, "href": author.get("href")}
                for author in (
                    paper.select("div.gs_fmaa > a")
                    or paper.select_one("h3.gs_rt").next_sibling.select("div > a")
                )
            ]
            pdot = paper.select_one("span.gs_pdot")
            cited_count: str = paper.select_one(
                "div.gs_fl.gs_flb > a:nth-child(3)"
            ).text

            result_papers.append(
                {
                    "title": title_h3.text,
                    "href": title_a.get("href") if title_a is not None else None,
                    "authors": authors,
                    "metadata": (
                        [pdot.previous_sibling.text, pdot.next_sibling.text]
                        if pdot is not None
                        else list(paper.select_one("div.gs_a").children)[-1]
                    ),
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
