import subprocess
import sys


def test_read_api_does_not_import_asr():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import call_summary.api
import call_summary.db.models
assert not {'torch','sherpa_onnx','faster_whisper','deepgram'} & sys.modules.keys()
""",
        ],
        check=True,
    )
