"""A knowingly unsafe pattern, here to be refused and then removed.

Issue #76 asks for a file with a knowingly unsafe pattern, a run that refuses
it, and its removal once that run is recorded. This is that file. It is not
imported by anything and it does not survive the commit after the one that
adds it.

The mistake is one character. The dot in the host pattern is not escaped, so it
matches any character rather than a literal dot, and a check written to admit
one photo library also admits `photosXexample.com` on a host somebody else
controls. It is the mistake somebody writes while thinking about the anchors.

Nothing else in this repository sees it. ruff's bandit family matches a call by
its name and there is no call here to match, mypy types it without complaint,
and a reviewer reads the line as what its author meant. That is the whole
argument for a second analyser, and this file is where the argument is tested
rather than asserted.
"""

from __future__ import annotations

import re

_LIBRARY_HOST = re.compile(r"^photos.example.com$")


def is_configured_library(host: str) -> bool:
    """Whether a host is the photo library this deployment was pointed at."""
    return _LIBRARY_HOST.match(host) is not None
