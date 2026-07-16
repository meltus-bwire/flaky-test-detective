from threading import Thread


def test_background_worker_completes() -> None:
    result: list[str] = []
    worker = Thread(target=lambda: result.append("complete"))

    worker.start()

    assert result == ["complete"]
