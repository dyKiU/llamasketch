"""Tests for the assist module (dev mode mock responses)."""

import pytest

from backend.assist import (
    is_enabled,
    _mock_vision_response,
    _mock_enhance_response,
    analyze_sketch_vision,
    enhance_prompt,
)


class TestAssistDevMode:
    def test_is_enabled_in_dev_mode(self):
        assert is_enabled() is True

    def test_mock_vision_response_shape(self):
        r = _mock_vision_response()
        assert "subject" in r
        assert "suggested_prompt" in r
        assert "composition_tips" in r
        assert isinstance(r["composition_tips"], list)

    def test_mock_enhance_response_shape(self):
        r = _mock_enhance_response("a cat")
        assert "enhanced" in r
        assert "alternatives" in r
        assert len(r["alternatives"]) == 2
        assert "a cat" in r["enhanced"]

    @pytest.mark.anyio
    async def test_analyze_sketch_vision_returns_mock(self):
        result = await analyze_sketch_vision("base64data")
        assert result["subject"] == "sketch"
        assert len(result["suggested_prompt"]) > 0

    @pytest.mark.anyio
    async def test_enhance_prompt_returns_mock(self):
        result = await enhance_prompt("a house on a hill")
        assert "a house on a hill" in result["enhanced"]
        assert len(result["alternatives"]) == 2
