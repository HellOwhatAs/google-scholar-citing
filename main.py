from selenium.webdriver import Edge as Driver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.microsoft import EdgeChromiumDriverManager as DriverManager
from bs4 import BeautifulSoup
import pyfilecache
import time
import json
import os
import urllib.parse
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.wm_attributes("-topmost", 1)
root.withdraw()


def show_messages(msg: str = "队友呢队友呢，救一下啊"):
    messagebox.showinfo("来人啊", msg, parent=root)


options = Options()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
browser = Driver(options=options, service=Service(DriverManager().install()))
browser.implicitly_wait(30)


@pyfilecache.file_cache
def published_papers(user_id: str):
    browser.get(f"https://scholar.google.com/citations?user={user_id}")

    soup = BeautifulSoup(browser.page_source, "lxml")
    while soup.select_one("#gsc_prf_i") is None:
        show_messages()
        soup = BeautifulSoup(browser.page_source, "lxml")

    more_button = browser.find_element(By.ID, "gsc_bpf_more")
    while more_button.get_attribute("disabled") is None:
        more_button.click()
        time.sleep(2)

    citing_hrefs: list = [
        {
            "count": a.text,
            "href": a.get_attribute("href"),
        }
        for a in browser.find_elements(
            By.CSS_SELECTOR, "#gsc_a_b > tr > td.gsc_a_c > a"
        )
    ]
    return citing_hrefs


def next_page_url(url: str, step: int = 10):
    parsed_url = urllib.parse.urlparse(url)
    queries = [
        [i[: i.find("=")], i[i.find("=") + 1 :]] for i in parsed_url.query.split("&")
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


@pyfilecache.file_cache
def get_cur_citing_papers(current_url: str):
    browser.get(current_url)

    soup = BeautifulSoup(browser.page_source, "lxml")
    while soup.select_one("#gs_res_ccl_mid") is None:
        show_messages()
        soup = BeautifulSoup(browser.page_source, "lxml")

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


@pyfilecache.file_cache
def func_cited_paper(citing_href: str):
    citing_papers = []
    cur_url = citing_href
    while True:
        cur_page: list = get_cur_citing_papers(cur_url)
        citing_papers.extend(cur_page)
        if len(cur_page) < 10:
            break
        cur_url = next_page_url(cur_url)
    return citing_papers


if __name__ == "__main__":
    citing_hrefs = published_papers("mbGafk4AAAAJ")
    citing_papers = []
    for citing_href in citing_hrefs:
        href = citing_href["href"]
        if not href:
            continue

        count, citing = citing_href["count"], func_cited_paper(href)

        if int(count) != len(citing):
            print(f"Warning: {href} count {count} != {len(citing)}. Retrying...")
            os.remove(func_cited_paper.fp(href))
            get_cur_citing_papers.clear()
            citing = func_cited_paper(href)

        citing_papers.append((count, href, citing))
    print(f"Get {sum(len(i) for _, _, i in citing_papers)} citing papers in total.")

    browser.quit()

    with open("citing_papers.json", "w", encoding="utf-8") as f:
        json.dump(citing_papers, f, ensure_ascii=False, indent=4)
