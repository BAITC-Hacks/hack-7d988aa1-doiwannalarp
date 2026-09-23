"""One-time renderer for the accompanying static solution diagram."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEST = Path(__file__).resolve().parents[1] / "docs" / "solution_diagram.png"
image = Image.new("RGB", (1840, 1060), "#f8fafc")
draw = ImageDraw.Draw(image)
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 24)

boxes = {
    "A": ((45, 285, 285, 425), "data/*.parquet", "2248 узлов · 3119 рёбер\n4840 переводов"),
    "B": ((345, 285, 585, 425), "io + quality", "схема · объёмы\nDATA_NOTES"),
    "C": ((645, 285, 885, 425), "graph.build_graph", "DiGraph\nсуммарная проекция"),
    "D": ((945, 285, 1185, 425), "features", "структура · seed\nвремя"),
    "E": ((1245, 100, 1485, 240), "roles", "правила\nrule_trace"),
    "F": ((1245, 470, 1485, 610), "clustering", "Louvain\nвзвешенная проекция"),
    "G": ((1545, 285, 1785, 425), "priority", "оценка · причины\nдействие"),
    "H": ((1510, 645, 1810, 785), "Результаты CSV", "роли · кластеры\nприоритеты"),
    "I": ((1130, 850, 1430, 990), "Streamlit UI", "сеть · карточка\nприоритеты · анализ"),
    "J": ((1510, 850, 1810, 990), "extras", "устойчивость · полнота\nмаршруты · чувствительность"),
}
for bounds, title, body in boxes.values():
    draw.rounded_rectangle(bounds, radius=20, fill="#ffffff", outline="#466788", width=3)
    x1, y1, x2, _ = bounds
    draw.text(((x1+x2)/2, y1+32), title, anchor="mm", fill="#183b56", font=bold)
    draw.multiline_text(((x1+x2)/2, y1+85), body, anchor="mm", align="center", spacing=5,
                        fill="#41576d", font=small)


def arrow(start, end):
    draw.line((start, end), fill="#1976d2", width=5)
    ex, ey = end
    sx, sy = start
    if abs(ex-sx) > abs(ey-sy):
        direction = 1 if ex > sx else -1
        tip = [(ex, ey), (ex-14*direction, ey-9), (ex-14*direction, ey+9)]
    else:
        direction = 1 if ey > sy else -1
        tip = [(ex, ey), (ex-9, ey-14*direction), (ex+9, ey-14*direction)]
    draw.polygon(tip, fill="#1976d2")


for x in (285, 585, 885):
    arrow((x, 355), (x+60, 355))
arrow((1185, 330), (1245, 170))
arrow((1185, 400), (1245, 540))
arrow((1485, 170), (1545, 330))
arrow((1485, 540), (1545, 400))
arrow((1665, 425), (1665, 645))
arrow((1540, 785), (1430, 885))
arrow((1665, 785), (1665, 850))
draw.text((920, 40), "Граф денег: от выгрузки к объяснимому приоритету", anchor="mm",
          font=ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 34), fill="#183b56")
DEST.parent.mkdir(parents=True, exist_ok=True)
image.save(DEST)
