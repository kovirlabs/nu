# Contributing

The full contribution guide lives in
[`CONTRIBUTING.md`](https://github.com/kovirlabs/nu/blob/master/CONTRIBUTING.md)
at the repository root. In short:

* Contributions are welcome from anyone. Act in accordance with the
  [Code of Conduct](code_of_conduct.md).
* Start with the [developer setup](setup.md) (`uv sync --extra dev`) and,
  if you're new, the [first steps](first-steps.md).
* Open an issue or a pull request at
  [github.com/kovirlabs/nu](https://github.com/kovirlabs/nu).
* Before you submit: `make check` passes (ruff formatting and lint, and the
  [tests](tests.md) with coverage), new code has tests that cover it, and
  docs you changed build with `uv run --no-sync mkdocs build --strict`.
* Write comments, docstrings and docs in plain English (British spelling).
  Every class, method and function has a docstring written for humans; they
  become the [API reference](api.md).
* If your change involves a non-obvious technical decision, record it in the
  [design decisions](design.md).
