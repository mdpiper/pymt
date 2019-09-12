import os

import pytest

from pymt.framework.bmi_metadata import find_model_metadata
from pymt.framework.bmi_setup import _parse_author_info


@pytest.mark.parametrize("key", ("author", "authors"))
def test_author(key):
    assert _parse_author_info({key: "John Cleese"}) == ("John Cleese",)


def test_author_empty_list():
    assert _parse_author_info({}) == ("",)


@pytest.mark.parametrize("key", ("author", "authors"))
@pytest.mark.parametrize("iter", (tuple, list))
def test_author_as_list(key, iter):
    assert _parse_author_info({key: iter(("John Cleese",))}) == ("John Cleese",)


@pytest.mark.parametrize("key", ("author", "authors"))
@pytest.mark.parametrize("iter", (tuple, list))
def test_author_multiple_authors(key, iter):
    assert _parse_author_info({key: iter(("John Cleese", "Eric Idle"))}) == (
        "John Cleese",
        "Eric Idle",
    )


@pytest.mark.parametrize("path_to_meta", ("", ".", "meta", "/usr/local/share"))
def test_find_metadata(path_to_meta):
    expected = os.path.abspath(os.path.join(os.path.dirname(__file__), path_to_meta))
    if expected.endswith(os.path.sep):
        expected = expected[:-1]

    class _MyBmi:
        METADATA = path_to_meta

    assert find_model_metadata(_MyBmi).lower() == expected.lower()
