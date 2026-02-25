"""Anthropic SDK wrapper for AI-assisted sketch analysis and prompt enhancement."""

import json
import logging

import anthropic

from .config import settings

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def is_enabled() -> bool:
    """Check if AI assist is available (API key configured or dev mode with mocks)."""
    return bool(settings.anthropic_api_key) or settings.dev_mode


def get_client() -> anthropic.AsyncAnthropic:
    """Lazy-init and return the async Anthropic client."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from Claude's response."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = text.index("\n") if "\n" in text else len(text)
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _mock_vision_response() -> dict:
    """Return mock vision response for dev mode (no API key required)."""
    return {
        "subject": "sketch",
        "suggested_prompt": "a colorful illustration with vibrant details, creative composition, artistic style",
        "composition_tips": [
            "Add more detail to key areas for richer output",
            "Consider balancing light and shadow",
        ],
    }


async def analyze_sketch_vision(image_base64: str) -> dict:
    """Send a sketch image to Haiku vision and get subject + prompt suggestions.

    Returns: {subject: str, suggested_prompt: str, composition_tips: list[str]}
    """
    if settings.dev_mode:
        return _mock_vision_response()

    client = get_client()

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "You are analyzing a hand-drawn sketch that will be used as input for an AI image generator. "
                            "Identify what the sketch depicts and suggest a detailed prompt that would produce a beautiful image from it.\n\n"
                            "Return ONLY a JSON object with these fields:\n"
                            '- "subject": what the sketch appears to be (1-5 words)\n'
                            '- "suggested_prompt": a detailed, creative prompt for image generation (10-30 words)\n'
                            '- "composition_tips": array of 1-3 short tips to improve the sketch\n\n'
                            "Return only the JSON object, no other text."
                        ),
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text
    try:
        parsed = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        logger.warning("Vision response not valid JSON: %s", raw[:200])
        raise ValueError("AI returned an unparseable response")
    return {
        "subject": str(parsed.get("subject", "unknown")),
        "suggested_prompt": str(parsed.get("suggested_prompt", "")),
        "composition_tips": [str(t) for t in parsed.get("composition_tips", [])],
    }


def _mock_enhance_response(prompt: str) -> dict:
    """Return mock prompt enhance response for dev mode (no API key required)."""
    return {
        "enhanced": f"{prompt}, vibrant colors, detailed shading, high quality illustration",
        "alternatives": [
            f"artistic interpretation of {prompt}, creative style, vivid imagery",
            f"stylized version of {prompt}, professional illustration, rich details",
        ],
    }


async def enhance_prompt(prompt: str) -> dict:
    """Enhance a user's prompt using Haiku.

    Returns: {enhanced: str, alternatives: list[str]}
    """
    if settings.dev_mode:
        return _mock_enhance_response(prompt)

    client = get_client()

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        messages=[
            {
                "role": "user",
                "content": (
                    f'The user wants to generate an image from a sketch with this prompt: "{prompt}"\n\n'
                    "Create an enhanced version and two creative alternatives. "
                    "Each should be 10-30 words, vivid and detailed, suitable for an AI image generator.\n\n"
                    "Return ONLY a JSON object with these fields:\n"
                    '- "enhanced": an improved version of their prompt with more detail and artistic direction\n'
                    '- "alternatives": array of exactly 2 creative alternative prompts\n\n'
                    "Return only the JSON object, no other text."
                ),
            }
        ],
    )

    raw = response.content[0].text
    try:
        parsed = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        logger.warning("Enhance response not valid JSON: %s", raw[:200])
        raise ValueError("AI returned an unparseable response")
    return {
        "enhanced": str(parsed.get("enhanced", prompt)),
        "alternatives": [str(a) for a in parsed.get("alternatives", [])][:2],
    }
