from pathlib import Path
import re
from html import unescape

html = Path(r"c:/arm_gs/scripts/_tmp_oes_check.html").read_text(encoding="utf-8", errors="replace")
text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
text = re.sub(r"</t[dh]>", " || ", text, flags=re.I)
text = re.sub(r"<[^>]+>", " ", text)
text = unescape(re.sub(r"\s+", " ", text))

for label in [
    "Первая синхронная зона с НТ с зарядом ГАЭС",
    "Первая синхронная зона с НТ без заряда ГАЭС",
    "Первая синхронная зона без НТ с зарядом ГАЭС",
    "Первая синхронная зона без НТ без заряда ГАЭС",
    "Первая синхронная зона с НТ (заряд ГАЭС)",
    "Первая синхронная зона без НТ (заряд ГАЭС)",
    "Зеленчукская",
    "Загорская",
    "Кубанская",
]:
    idx = text.find(label)
    print("\n===", label, "OK" if idx >= 0 else "MISSING")
    if idx < 0:
        continue
    chunk = text[idx : idx + 1400]
    nums = re.findall(r"\d(?:\s?\d){2,}(?:,\d+)?", chunk)
    print("first15:", nums[:15])
    print("last10:", nums[-10:])

# explicit 2025 diffs from known pattern
for a, b in [
    ("1 110 746,4", "1 108 723,9"),
    ("1 110 746,4", "1 108 710"),
    ("1 087 532,4", "1 085 509,9"),
    ("1 087 532,4", "1 085 496"),
]:
    print(a, "in page", a in text, ";", b, "in page", b in text)
