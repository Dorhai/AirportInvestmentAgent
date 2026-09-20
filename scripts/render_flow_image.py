"""Render the dark flow diagram SVG to PNG.

Run:
    uv run --with playwright scripts/render_flow_image.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "docs" / "assets" / "airportiq-system-flow.svg"
OUT_PNG = ROOT / "AirportIQ-System-Flow.png"
OUT_ASSETS_PNG = ROOT / "docs" / "assets" / "airportiq-system-flow.png"


async def main() -> None:
    html = f"""<!DOCTYPE html>
<html><head><style>
  html, body {{ margin: 0; background: #2b303b; }}
  svg {{ display: block; width: 1100px; height: auto; }}
</style></head>
<body>{SVG.read_text(encoding="utf-8")}</body></html>"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1100, "height": 920},
            device_scale_factor=2,
        )
        await page.set_content(html, wait_until="load")
        await page.locator("svg").screenshot(path=str(OUT_PNG), type="png")
        await page.locator("svg").screenshot(path=str(OUT_ASSETS_PNG), type="png")
        await browser.close()
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    asyncio.run(main())
