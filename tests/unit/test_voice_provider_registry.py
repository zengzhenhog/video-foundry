from video_foundry.voice.mock_provider import MockTTSProvider
from video_foundry.voice.provider_registry import get_tts_provider, list_voice_providers


def test_provider_registry_defaults_to_mock() -> None:
    provider = get_tts_provider()

    assert isinstance(provider, MockTTSProvider)
    assert provider.provider_name == "mock"


def test_voice_providers_include_enabled_mock() -> None:
    providers = list_voice_providers()

    assert providers[0].id == "mock"
    assert providers[0].enabled is True
    assert providers[0].default is True

