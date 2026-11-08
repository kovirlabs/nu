# The interface modules use gettext's `_` at import time (in class
# attributes), so make sure it's installed first: then any of them can be
# imported on its own (by a plugin or a test), not only after mu.app.
from .. import i18n  # noqa: F401
from .main import Window


__all__ = ["Window"]
