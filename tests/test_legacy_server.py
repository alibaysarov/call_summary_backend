from pathlib import Path

from fastapi.testclient import TestClient

from call_summary import server


def test_legacy_transcribe_contract_and_cleanup(monkeypatch):
    paths = []

    class Processor:
        def process_ogg(self, path):
            assert Path(path).read_bytes() == b"synthetic"
            paths.append(Path(path))
            return "test transcript"

    monkeypatch.setitem(server.state, "processor", Processor())
    # No lifespan: ASR deliberately stubbed for the HTTP compatibility contract.
    client = TestClient(server.app)
    result = client.post("/transcribe", files={"file": ("test.ogg", b"synthetic")})
    assert result.status_code == 200
    assert result.json() == {"text": "test transcript"}
    assert not paths[0].exists()
    monkeypatch.setenv("MAX_AUDIO_BYTES", "1")
    assert (
        client.post(
            "/transcribe", files={"file": ("test.ogg", b"synthetic")}
        ).status_code
        == 413
    )
