from unittest.mock import MagicMock

from thai_voice_bridge.cli import build_parser
from thai_voice_bridge.config import config_from_dict
from thai_voice_bridge.tray import TrayApplication


def test_public_product_name_is_poodtype():
    assert build_parser().prog == "poodtype"
    tray = TrayApplication(
        MagicMock(),
        config_from_dict({"language": "th", "task": "transcribe"}),
    )
    assert tray._title().startswith("PoodType ")
