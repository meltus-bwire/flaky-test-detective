import pytest

seen_items: list[str] = []


def test_a_starts_with_no_shared_items() -> None:
    assert seen_items == []


def test_b_adds_a_shared_item() -> None:
    seen_items.append("item")
    assert seen_items == ["item"]

@pytest.fixture(autouse=True)
def reset_shared_items() -> None:
    seen_items.clear()
