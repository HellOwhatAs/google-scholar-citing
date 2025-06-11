# google-scholar-citing

## Install
```
pip install git+https://github.com/HellOwhatAs/google-scholar-citing --upgrade
```

## Features
- `Scholar.get_published_papers` get published paper (with citing papers url) list of the given user
  ```py
  [
      {
          "title": str,
          "href": str,
          "metadata": list[str],
          "cited_count": str,
          "citing_href": str,
          "year": str,
      }, ...
  ]
  ```
- `Scholar.get_citing_papers` get list of citing papers of each citing papers url
  ```py
  [
      {
          "title": str,
          "href": str,
          "id": str,
          "authors": [
              {
                  "name": str,
                  "href": str,
              }, ...
          ],
      }, ...
  ]
  ```
- `Scholar.get_papers` get matched papers by searching paper title (to get full authors)
  ```py
  [
      {
          "title": str,
          "href": str,
          "authors": [
              {
                  "name": str,
                  "href": str,
              }, ...
          ],
          "authors_raw": str,
          "metadata": list[str],
          "cited_count": str,
      }, ...
  ]
  ```
- `Scholar.get_author` get metadata of author
  ```py
  {
      "name": str,
      "cited_cnt": str,
      "affliation": str,
      "domain": str,
      "profile": str,
      "url": str,
  }
  ```

## Example
```py
from google_scholar_citing import Scholar
with Scholar() as scholar:
    # published papers
    papers = scholar.get_published_papers("zv2GUHEAAAAJ")

    for paper in papers:
        # url of citing papers
        citing_href = paper["citing_href"]
        if not citing_href:
            continue

        # list of citing papers
        paper["citing_papers"] = scholar.get_citing_papers(citing_href)

        for citing_paper in paper["citing_papers"]:
            citing_paper: dict
            if isinstance(citing_paper, str):
                continue

            # list of papers matched by searching the title of this citing paper
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
                # add more information of this author
                author.update(scholar.get_author(author_url))

with open("citing_papers.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=4)
```
