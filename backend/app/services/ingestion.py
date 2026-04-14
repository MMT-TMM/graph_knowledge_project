from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image
from pypdf import PdfReader

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.graph.prompts import IMAGE_TEXT_PROMPT


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        return ""

    reader = PdfReader(BytesIO(pdf_bytes))
    texts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            texts.append(text.strip())
    return "\n".join(texts).strip()


def extract_text_from_image_ocr(image_bytes: bytes) -> str:
    if not image_bytes or pytesseract is None:
        return ""

    try:
        image = Image.open(BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        if text.strip():
            return text.strip()
        return pytesseract.image_to_string(image, lang="eng").strip()
    except Exception:
        return ""


def extract_text_from_image_vision(
    image_bytes: bytes,
    model_name: str,
    api_key: str,
    base_url: str | None = None,
) -> str:
    if not image_bytes or not api_key:
        return ""

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url or None,
        temperature=0,
    )
    response = llm.invoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": IMAGE_TEXT_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ]
            )
        ]
    )
    if isinstance(response.content, str):
        return response.content.strip()
    return str(response.content).strip()
