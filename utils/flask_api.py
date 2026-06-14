"""
Generate the Flask API data used for Mu's autocomplete/calltips.

Requires the `beautifulsoup4` and `requests` packages (the `utils` extra).

Usage:

    python flask_api.py [output.json]

Fetches the Flask API reference and writes a JSON list of API entries
(default: flask.json).
"""

import json
import sys

import requests
from bs4 import BeautifulSoup


# The `en/stable/` alias always tracks the current stable Flask release, so
# this keeps working across Flask versions without a hard-coded version path.
URL = "https://flask.palletsprojects.com/en/stable/api/"


def to_dict(name, args, description):
    """
    Returns a dictionary representation of the API element if valid, else
    returns None.
    """
    if name.endswith("__"):
        return None
    return {"name": name, "args": args, "description": description}


def descname(spec):
    """Returns the bare API name from a dt signature (its ``descname`` span)."""
    name = spec.select_one("span.descname")
    return name.get_text() if name else ""


def sig_params(spec):
    """Returns the list of parameter strings from a dt signature."""
    return [em.get_text() for em in spec.select("em.sig-param")]


def parse(soup):
    """
    Yields the API elements scraped from a parsed Flask API documentation page.

    Targets the modern Sphinx markup (``dl.py.function``, ``span.descname``,
    ``em.sig-param``) used by the current Flask docs.
    """
    # Find all the function definitions on the page:
    for func in soup.select("dl.py.function"):
        # Spec and doc are always the first dt/dd in the dl.
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


def main(output="flask.json"):
    response = requests.get(URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    entries = list(parse(soup))
    with open(output, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


if __name__ == "__main__":
    main(*sys.argv[1:])
