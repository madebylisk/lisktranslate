# LiskTranslate

A small Windows app that reads on-screen text. Draw a region, and the text shows up with furigana. It does not run LunaTranslator.

OCR uses the Snipping Tool engine already installed with Windows 11 (`oneocr.dll`). If that engine cannot load, the app falls back to Windows OCR.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
lisktranslate
```

## Use

- Right-click a box, or use **Remove**, to delete a region. **Remove** still works when the frames are hidden.
- **Bind window** then click the game. The boxes follow that window. Click **Unbind** to stop. Esc cancels the click.
- **Pause** stops recognition.
- **Furigana** shows kana above kanji. The text in the window can be selected.
- **Click through** lets the mouse reach the game. **Hide frames** does that and hides the boxes. Turn them off from this window.

Regions are saved in `%APPDATA%\lisktranslate\config.json`. The OCR files are copied once to `%LOCALAPPDATA%\lisktranslate\oneocr`.

The Windows OCR fallback needs the Japanese OCR language pack. OneOCR does not.
