"""
Native Tool-Assisted Image Generation & Artifact Rendering Module for Raven CLI Agent.
Supports OpenRouter, OpenAI, and Google GenAI / Vertex AI image models.
"""

import base64
import os
import random
import re
import sys
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from agent.core.settings import settings
from agent.utils import use_vertex_ai


ASPECT_RATIO_DIMENSIONS = {
    "1:1": "1024x1024",
    "16:9": "1792x1024",
    "9:16": "1024x1792",
    "4:3": "1024x768",
    "3:4": "768x1024",
}

DEFAULT_IMAGE_MODEL = "black-forest-labs/flux-1-schnell"


def sanitize_image_name(name_or_prompt: str) -> str:
    """Sanitizes a string to be safely used as a filename."""
    if not name_or_prompt:
        return "generated_image"
    clean = re.sub(r'[^a-zA-Z0-9_\-]+', '_', name_or_prompt.strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    if len(clean) > 30:
        clean = clean[:30].rstrip('_')
    return clean or "generated_image"


def get_artifact_output_path(filename: str = "", prompt: str = "") -> Path:
    """
    Determines and creates the output directory for generated images.
    Falls back to ~/.raven/artifacts/images/ if workspace root is read-only.
    """
    base_name = sanitize_image_name(filename) if filename else sanitize_image_name(prompt)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{base_name}_{timestamp}.png"

    # Try local project artifacts directory first
    try:
        target_dir = Path.cwd() / "artifacts" / "images"
        target_dir.mkdir(parents=True, exist_ok=True)
        # Test writeability
        test_file = target_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        return target_dir / file_name
    except Exception:
        fallback_dir = Path.home() / ".raven" / "artifacts" / "images"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / file_name


def open_in_viewer(image_path: str | Path) -> bool:
    """
    Opens the image in the default system viewer non-blockingly.
    Safe across Windows, macOS, and Linux.
    """
    try:
        abs_path = os.path.abspath(str(image_path))
        if sys.platform == "win32" or os.name == "nt":
            os.startfile(abs_path)
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", abs_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        else:
            subprocess.Popen(["xdg-open", abs_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception:
        return False


def generate_ansi_thumbnail(image_path: str | Path, width: int = 40) -> str:
    """
    Generates a 24-bit ANSI half-block (▀) thumbnail preview for terminal display.
    """
    try:
        path = Path(image_path)
        if not path.exists():
            return ""

        with Image.open(path) as raw_img:
            img = raw_img.convert("RGB")
            orig_w, orig_h = img.size
            if orig_w == 0 or orig_h == 0:
                return ""

            aspect = orig_h / orig_w
            # Terminal cells are roughly 2:1 vertical-to-horizontal.
            # Using half-blocks allows 2 vertical pixels per text row.
            char_rows = max(1, int(round((width * aspect) / 2)))
            pixel_height = char_rows * 2

            img_resized = img.resize((width, pixel_height), Image.Resampling.BILINEAR)

            ansi_lines = []
            for y in range(0, pixel_height, 2):
                line_parts = []
                for x in range(width):
                    top_r, top_g, top_b = img_resized.getpixel((x, y))
                    if y + 1 < pixel_height:
                        bot_r, bot_g, bot_b = img_resized.getpixel((x, y + 1))
                        line_parts.append(f"\x1b[38;2;{top_r};{top_g};{top_b}m\x1b[48;2;{bot_r};{bot_g};{bot_b}m▀")
                    else:
                        line_parts.append(f"\x1b[38;2;{top_r};{top_g};{top_b}m\x1b[49m▀")
                line_parts.append("\x1b[0m")
                ansi_lines.append("".join(line_parts))

            return "\n".join(ansi_lines)
    except Exception:
        return ""


def _is_rate_limit_error(exc: Exception) -> bool:
    """Checks whether an exception indicates rate limit or quota exhaustion (429)."""
    code = getattr(exc, "code", None)
    if code == 429:
        return True
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    msg = str(exc).lower()
    return any(term in msg for term in (
        "429", "resource_exhausted", "resourceexhausted",
        "quota", "rate limit", "too many requests"
    ))


def _extract_retry_delay(exc: Optional[Exception], default_delay: float) -> float:
    """Extracts suggested retry delay from error message if available."""
    if not exc:
        return default_delay
    msg = str(exc)
    m = re.search(r'retry[- ]after[:\s]+(\d+(?:\.\d+)?)', msg, re.IGNORECASE)
    if not m:
        m = re.search(r'wait[:\s]+(\d+(?:\.\d+)?)\s*s', msg, re.IGNORECASE)
    if m:
        try:
            return min(float(m.group(1)), 25.0)
        except ValueError:
            pass
    return default_delay


def _generate_with_google_genai(
    prompt: str,
    target_model: str,
    aspect_ratio: str,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Helper to generate image using google-genai / Vertex AI with multi-region failover and backoff."""
    from agent.core.settings import settings
    try:
        from google import genai
        from google.genai import types
        from google.auth import default

        vertex_enabled = use_vertex_ai()

        # Handle model selection and deprecation
        model_name = target_model or "gemini-3.1-flash-image"
        if (
            not model_name
            or model_name == DEFAULT_IMAGE_MODEL
            or "imagen" in model_name.lower()
            or "imagegeneration" in model_name.lower()
        ):
            model_name = "gemini-3.1-flash-image"

        if vertex_enabled:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
            location = os.environ.get("GOOGLE_CLOUD_REGION") or os.environ.get("VERTEX_LOCATION")

            # Try to extract project/location from configured base URL
            if not project_id or not location:
                base_url = settings.RAVEN_BASE_URL or ""
                match = re.search(r'/projects/([^/]+)/locations/([^/]+)', base_url)
                if match:
                    if not project_id:
                        project_id = match.group(1)
                    if not location:
                        location = match.group(2)

            if not project_id:
                try:
                    _, project_id = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                except Exception:
                    pass

            if not location:
                location = "us-central1"

            # Quotas on Vertex AI are regional. Define candidate failover regions.
            preferred_regions = ["us-central1", "us-east4", "us-west1", "europe-west4", "europe-west1", "asia-northeast1"]
            candidate_regions = [location]
            for reg in preferred_regions:
                if reg not in candidate_regions:
                    candidate_regions.append(reg)
        else:
            project_id = None
            candidate_regions = [None]

        max_cycles = 3
        last_error = None

        for cycle in range(max_cycles):
            for current_region in candidate_regions:
                try:
                    client_kwargs = {"vertexai": vertex_enabled}
                    if vertex_enabled:
                        if project_id:
                            client_kwargs["project"] = project_id
                        if current_region:
                            client_kwargs["location"] = current_region

                    client = genai.Client(**client_kwargs)

                    effective_prompt = prompt
                    if negative_prompt:
                        effective_prompt += f"\nNegative prompt: {negative_prompt}"

                    aspect_ratio_str = aspect_ratio if aspect_ratio else "1:1"

                    response = client.models.generate_content(
                        model=model_name,
                        contents=effective_prompt,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(
                                aspect_ratio=aspect_ratio_str,
                            ),
                        ),
                    )
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            return part.inline_data.data
                    return None

                except Exception as exc:
                    last_error = exc
                    # Check for rate limit or quota exhaustion (429)
                    if not _is_rate_limit_error(exc):
                        # If location/region error (e.g. 404 or 503 unavailable for that region), try next region
                        if any(err_txt in str(exc).lower() for err_txt in ("not found", "unavailable", "503")):
                            continue
                        # Non-quota error (bad arguments, auth rejection): fail immediately
                        raise exc

                    # If 429 quota exhaustion hit on Vertex AI, immediately fail over to the next candidate region
                    if vertex_enabled and len(candidate_regions) > 1:
                        continue
                    else:
                        break

            # If all candidate regions were throttled in this cycle, back off with jitter before next cycle
            if cycle < max_cycles - 1:
                base_delay = (2.0 ** (cycle + 1)) + random.uniform(0.5, 2.0)
                delay = _extract_retry_delay(last_error, base_delay)
                time.sleep(delay)

        if last_error:
            raise last_error
        return None

    except Exception as e:
        raise RuntimeError(f"Google GenAI / Vertex AI image generation failed: {e}")


def _generate_with_openai_compatible(
    prompt: str,
    target_model: str,
    aspect_ratio: str,
    negative_prompt: str = ""
) -> bytes:
    """Helper to generate image using OpenAI / OpenRouter endpoints or active client with backoff."""
    from openai import OpenAI
    from agent.core.llm import get_genai_client

    try:
        client = get_genai_client()
    except Exception:
        base_url = getattr(settings, "RAVEN_BASE_URL", None) or "https://openrouter.ai/api/v1"
        api_key = getattr(settings, "RAVEN_API_KEY", None)

        if not api_key:
            raise ValueError(
                f"Active provider at '{base_url}' has no API key configured. "
                "Please configure an OpenRouter/OpenAI API key via `/connect` or switch `IMAGE_MODEL`."
            )

        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=60.0
        )

    size = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, "1024x1024")

    # Formulate prompt if negative prompt exists
    effective_prompt = prompt
    if negative_prompt and negative_prompt.strip():
        effective_prompt = f"{prompt} --no {negative_prompt.strip()}"

    kwargs = {
        "model": target_model,
        "prompt": effective_prompt,
        "n": 1,
        "size": size,
    }

    last_exc = None
    for attempt in range(3):
        try:
            # First attempt with b64_json response_format
            try:
                response = client.images.generate(
                    **kwargs,
                    response_format="b64_json"
                )
            except Exception:
                # Fallback without explicit response_format (some endpoints default to URL or b64)
                response = client.images.generate(**kwargs)

            if not response.data:
                raise RuntimeError("No image data returned from provider.")

            item = response.data[0]
            b64_val = getattr(item, "b64_json", None)
            if b64_val:
                return base64.b64decode(b64_val)

            url_val = getattr(item, "url", None)
            if url_val:
                req = urllib.request.Request(
                    url_val,
                    headers={"User-Agent": "Raven-CLI-Agent/1.0"}
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read()

            raise RuntimeError("Provider returned response with neither 'b64_json' nor 'url'.")

        except Exception as e:
            last_exc = e
            if _is_rate_limit_error(e) and attempt < 2:
                base_delay = (2.0 ** (attempt + 1)) + random.uniform(0.5, 1.5)
                delay = _extract_retry_delay(e, base_delay)
                time.sleep(delay)
                continue
            raise e

    if last_exc:
        raise last_exc


def generate_image(
    prompt: str,
    filename: str = "",
    aspect_ratio: str = "1:1",
    model: str = "",
    negative_prompt: str = ""
) -> str:
    """
    Generates an image from a detailed text prompt using the configured image generation model.
    Saves the output file locally in 'artifacts/images/' and opens it in the default viewer.

    Args:
        prompt: Detailed description of the image to generate.
        filename: Optional descriptive base filename (e.g. 'auth_flow_diagram').
        aspect_ratio: Aspect ratio ('1:1', '16:9', '9:16', '4:3', '3:4'). Defaults to '1:1'.
        model: Specific image model to override default IMAGE_MODEL setting.
        negative_prompt: Elements or styles to exclude (if supported by engine).

    Returns:
        A concise summary string with the saved file path, image metadata, and ANSI terminal preview.
    """
    if not prompt or not prompt.strip():
        return "Error: Prompt cannot be empty for image generation."

    clean_prompt = prompt.strip()
    configured_model = (model or getattr(settings, "IMAGE_MODEL", None) or "").strip()
    if use_vertex_ai():
        if not configured_model or configured_model == DEFAULT_IMAGE_MODEL or "imagen" in configured_model.lower():
            target_model = "gemini-3.1-flash-image"
        else:
            target_model = configured_model
    else:
        target_model = configured_model or DEFAULT_IMAGE_MODEL
    norm_aspect = aspect_ratio if aspect_ratio in ASPECT_RATIO_DIMENSIONS else "1:1"

    out_path = get_artifact_output_path(filename=filename, prompt=clean_prompt)

    try:
        is_vertex = (
            use_vertex_ai()
            or "imagen" in target_model.lower()
            or "gemini" in target_model.lower()
            or "imagegeneration" in target_model.lower()
        )
        if is_vertex:
            try:
                img_bytes = _generate_with_google_genai(
                    prompt=clean_prompt,
                    target_model=target_model,
                    aspect_ratio=norm_aspect,
                    negative_prompt=negative_prompt
                )
            except Exception as e:
                # Capture the inner exception to avoid silencing authentic authentication or SDK errors.
                # If running on Vertex AI or targeting a Google model, do not fall back to OpenAPI endpoint
                # (since Vertex AI OpenAPI does not support /v1/images/generations).
                if (
                    use_vertex_ai()
                    or any(k in target_model.lower() for k in ("imagen", "gemini", "imagegeneration"))
                ):
                    raise e
                # Fallback to OpenAI compatible endpoint if Google GenAI fails or credentials differ
                img_bytes = _generate_with_openai_compatible(
                    prompt=clean_prompt,
                    target_model=target_model,
                    aspect_ratio=norm_aspect,
                    negative_prompt=negative_prompt
                )
        else:
            img_bytes = _generate_with_openai_compatible(
                prompt=clean_prompt,
                target_model=target_model,
                aspect_ratio=norm_aspect,
                negative_prompt=negative_prompt
            )

        if not img_bytes:
            return f"Error: Failed to obtain image bytes from model '{target_model}'."

        out_path.write_bytes(img_bytes)

        # Inspect generated dimensions & size
        try:
            with Image.open(out_path) as im:
                w, h = im.size
        except Exception:
            w, h = (1024, 1024)

        file_size_bytes = out_path.stat().st_size
        if file_size_bytes >= 1024 * 1024:
            file_size_str = f"{file_size_bytes / (1024 * 1024):.1f} MB"
        else:
            file_size_str = f"{file_size_bytes / 1024:.1f} KB"

        # Open in default system viewer
        open_in_viewer(out_path)

        try:
            rel_path = out_path.relative_to(Path.cwd()).as_posix()
        except Exception:
            rel_path = out_path.as_posix()

        summary = (
            f"Image successfully generated and saved to `{rel_path}` "
            f"({w}x{h}, {file_size_str}, model: `{target_model}`).\n"
            f"Opened in default system viewer."
        )
        return summary

    except Exception as e:
        err_msg = str(e)
        if "safety" in err_msg.lower() or "moderation" in err_msg.lower() or "blocked" in err_msg.lower():
            return f"Error: Image generation was blocked by provider content moderation filters. Details: {err_msg}"
        if "429" in err_msg or "resource_exhausted" in err_msg.lower() or "quota" in err_msg.lower():
            return f"Error: Image generation quota exhausted or rate limit reached across regions. Details: {err_msg}"
        if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            return f"Error: Image generation request timed out after 60 seconds. The provider may be experiencing high load."
        return f"Error generating image with model '{target_model}': {err_msg}"
