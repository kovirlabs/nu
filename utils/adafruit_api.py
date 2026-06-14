"""
Generate the CircuitPython (Adafruit) API data used for Mu's autocomplete.

Requires the `beautifulsoup4` and `requests` packages (the `utils` extra).

Usage:

    python adafruit_api.py [output.json]

Fetches the CircuitPython shared-bindings index, follows the per-module doc
links, and writes a JSON list of API entries (default: adafruit.json).
"""

import json
import sys
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup


# The `en/stable/` alias always tracks the current stable CircuitPython
# release, so this keeps working without a hard-coded version path.
URL = "https://docs.circuitpython.org/en/stable/shared-bindings/index.html"


def to_dict(name, args, description):
    """
    Returns a dictionary representation of the API element if valid, else
    returns None.
    """
    if name.endswith("__"):
        return None
    return {"name": name, "args": args, "description": description}


def fetch(url):
    """Fetches a URL and returns its parsed BeautifulSoup document."""
    response = requests.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def descname(spec):
    """
    Returns the dotted name for an API element from its dt signature, joining
    the optional ``descclassname`` prefix to the ``descname``.
    """
    prefix = spec.select_one("span.descclassname")
    name = spec.select_one("span.descname")
    return (prefix.get_text() if prefix else "") + (name.get_text() if name else "")


def sig_params(spec):
    """Returns the list of parameter strings from a dt signature."""
    return [em.get_text() for em in spec.select("em.sig-param")]


def parse_api(soup):
    """
    Yields the API elements scraped from a *potential* API documentation page.

    Targets the modern Sphinx markup (``dl.py.function``, ``span.descname``,
    ``em.sig-param``) used by the current CircuitPython docs.
    """
    # Find all the function definitions on the page:
    for func in soup.select("dl.py.function"):
        func_spec = func.select_one("dt")
        func_doc = func.select_one("dd")
        d = to_dict(descname(func_spec), sig_params(func_spec), func_doc.get_text())
        if d:
            yield d
    # Find all the class definitions on the page:
    for classes in soup.select("dl.py.class"):
        class_spec = classes.select_one("dt")
        class_doc = classes.select_one("dd")
        class_name = descname(class_spec)
        # Class description: the leading paragraphs, up to the first nested
        # definition list (members) or field list (params/returns).
        description = ""
        for child in class_doc.contents:
            name = getattr(child, "name", None)
            if name == "p":
                description += child.get_text() + "\n\n"
            if name in ("dl", "table"):
                break
        d = to_dict(class_name, sig_params(class_spec), description)
        if d:
            yield d
        # Members: methods, then attributes / properties / data.
        for method in classes.select("dl.py.method"):
            method_name = descname(method.select_one("dt"))
            if method_name.startswith("__"):
                continue
            method_name = class_name + "." + method_name
            method_args = sig_params(method.select_one("dt"))
            d = to_dict(method_name, method_args, method.select_one("dd").get_text())
            if d:
                yield d
        for member in classes.select("dl.py.attribute, dl.py.property, dl.py.data"):
            name = class_name + "." + descname(member.select_one("dt"))
            d = to_dict(name, None, member.select_one("dd").get_text())
            if d:
                yield d


def parse(index):
    """
    Follows the per-module links from the shared-bindings index and yields the
    API elements found on each linked page (each page fetched only once).
    """
    seen = set()
    for link in index.select("div.toctree-wrapper li a"):
        href = link.get("href")
        if not href:
            continue
        # The toctree lists per-symbol anchors as well as module pages; strip
        # the fragment so each module page is fetched and parsed only once.
        page = urldefrag(urljoin(URL, href)).url
        if page in seen:
            continue
        seen.add(page)
        yield from parse_api(fetch(page))


def main(output="adafruit.json"):
    entries = list(parse(fetch(URL)))
    with open(output, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


if __name__ == "__main__":
    main(*sys.argv[1:])
