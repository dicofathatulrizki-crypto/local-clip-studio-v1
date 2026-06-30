"""Unit tests for provider interfaces."""

from __future__ import annotations

from backend.infrastructure.plugins.interfaces import (
    BaseProvider,
    CaptionProvider,
    CaptionStyle,
    ExportFormat,
    ExportProvider,
    LLMProvider,
    ModelInfo,
    ProviderResult,
    STTProvider,
    TranslationProvider,
    VisionProvider,
)


class TestBaseProvider:
    """Test the BaseProvider abstract class."""

    def test_provider_version_default(self) -> None:
        assert BaseProvider.PROVIDER_VERSION == "1.0.0"

    def test_cannot_instantiate_base(self) -> None:
        with pytest.raises(TypeError):
            BaseProvider()  # type: ignore[abstract]


class TestSTTProvider:
    """Test STTProvider interface."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            STTProvider()  # type: ignore[abstract]

    def test_default_methods(self) -> None:
        class MinimalSTT(STTProvider):
            def load(self, config=None):
                return ProviderResult()
            def unload(self):
                return ProviderResult()
            def health_check(self):
                return {"status": "ok"}
            def transcribe(self, audio_path, language=None, model=None, **kwargs):
                return ProviderResult(data={"text": "hello"})
            def get_available_models(self):
                return [ModelInfo(id="base")]

        provider = MinimalSTT()
        assert provider.get_supported_languages() == []


class TestVisionProvider:
    """Test VisionProvider interface."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            VisionProvider()  # type: ignore[abstract]

    def test_default_methods(self) -> None:
        class MinimalVision(VisionProvider):
            def load(self, config=None):
                return ProviderResult()
            def unload(self):
                return ProviderResult()
            def health_check(self):
                return {"status": "ok"}
            def detect(self, image_path, **kwargs):
                return ProviderResult(data={"detections": []})
            def detect_batch(self, image_paths, **kwargs):
                return [ProviderResult()]
            def get_available_models(self):
                return [ModelInfo(id="yolo")]

        provider = MinimalVision()
        assert provider.get_provider_info()["class"] == "MinimalVision"


class TestLLMProvider:
    """Test LLMProvider interface."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_default_methods(self) -> None:
        class MinimalLLM(LLMProvider):
            def load(self, config=None):
                return ProviderResult()
            def unload(self):
                return ProviderResult()
            def health_check(self):
                return {"status": "ok"}
            def generate(self, prompt, system_prompt=None, temperature=0.7,
                         max_tokens=2048, **kwargs):
                return ProviderResult(data={"text": "response"})
            def get_available_models(self):
                return [ModelInfo(id="gpt-4")]

        provider = MinimalLLM()
        assert provider.count_tokens("hello world") == 2
        assert provider.count_tokens("") == 0


class TestCaptionProvider:
    """Test CaptionProvider interface."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            CaptionProvider()  # type: ignore[abstract]

    def test_default_methods(self) -> None:
        class MinimalCaption(CaptionProvider):
            def load(self, config=None):
                return ProviderResult()
            def unload(self):
                return ProviderResult()
            def health_check(self):
                return {"status": "ok"}
            def generate_captions(self, media_path, language="en", **kwargs):
                return ProviderResult(data={"captions": []})
            def get_styles(self):
                return [CaptionStyle()]

        provider = MinimalCaption()
        assert provider.get_supported_formats() == ["srt", "vtt"]


class TestTranslationProvider:
    """Test TranslationProvider interface."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            TranslationProvider()  # type: ignore[abstract]

    def test_default_methods(self) -> None:
        class MinimalTranslation(TranslationProvider):
            def load(self, config=None):
                return ProviderResult()
            def unload(self):
                return ProviderResult()
            def health_check(self):
                return {"status": "ok"}
            def translate(self, text, source_language, target_language, **kwargs):
                return ProviderResult(data={"translated_text": "hola"})
            def get_supported_languages(self):
                return [{"code": "es", "name": "Spanish"}]

        provider = MinimalTranslation()
        assert provider.detect_language("hello") == ""
        batch = provider.translate_batch(["hi"], "en", "es")
        assert len(batch) == 1


class TestExportProvider:
    """Test ExportProvider interface."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            ExportProvider()  # type: ignore[abstract]

    def test_default_methods(self) -> None:
        class MinimalExport(ExportProvider):
            def load(self, config=None):
                return ProviderResult()
            def unload(self):
                return ProviderResult()
            def health_check(self):
                return {"status": "ok"}
            def export(self, input_path, output_path, format="mp4", **kwargs):
                return ProviderResult(data={"output_path": output_path})
            def get_supported_formats(self):
                return [ExportFormat(name="MP4", extension="mp4", mime_type="video/mp4")]

        provider = MinimalExport()
        assert provider.estimate_output_size("/input.mp4") == 0


class TestProviderResult:
    """Test ProviderResult dataclass."""

    def test_success_default(self) -> None:
        result = ProviderResult()
        assert result.success is True
        assert result.data is None
        assert result.error == ""

    def test_with_data(self) -> None:
        result = ProviderResult(data={"text": "hello"}, metadata={"duration": 10.5})
        assert result.data["text"] == "hello"
        assert result.metadata["duration"] == 10.5

    def test_failure(self) -> None:
        result = ProviderResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_defaults(self) -> None:
        info = ModelInfo()
        assert info.id == ""
        assert info.size_mb == 0

    def test_with_values(self) -> None:
        info = ModelInfo(id="whisper-large", name="Whisper Large",
                         size_mb=3000, performance="high")
        assert info.id == "whisper-large"
        assert info.size_mb == 3000


class TestCaptionStyle:
    """Test CaptionStyle dataclass."""

    def test_defaults(self) -> None:
        style = CaptionStyle()
        assert style.name == "default"
        assert style.font_size == 24
        assert style.position == "bottom"

    def test_custom_style(self) -> None:
        style = CaptionStyle(name="custom", font_size=36, font_color="#FF0000")
        assert style.name == "custom"
        assert style.font_color == "#FF0000"


class TestExportFormat:
    """Test ExportFormat dataclass."""

    def test_defaults(self) -> None:
        fmt = ExportFormat()
        assert fmt.name == ""
        assert fmt.supports_gpu is False

    def test_with_values(self) -> None:
        fmt = ExportFormat(name="MP4", extension="mp4", mime_type="video/mp4",
                           supports_gpu=True)
        assert fmt.name == "MP4"
        assert fmt.supports_gpu is True
