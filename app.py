"""Serve the three game pages, check a category, and classify one item."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI
from fastapi.responses import FileResponse

import classify

load_dotenv()

app = FastAPI()
ROOT = Path(__file__).parent
PAGES = ROOT / "pages"


@app.get("/favicon.png")
def show_icon():
    """Open the page icon."""
    return FileResponse(ROOT / "assets" / "favicon.png")


@app.get("/")
def show_intro():
    """Open the intro page."""
    return FileResponse(PAGES / "index.html")


@app.get("/categories")
def show_categories():
    """Open the category page."""
    return FileResponse(PAGES / "categories.html")


@app.get("/play")
def show_play():
    """Open the play page."""
    return FileResponse(PAGES / "play.html")


@app.post("/check")
def check_category(name: str = Body(), others: list[str] = Body()):
    """Check one category name against the other filled names."""
    if not name.strip():
        return {"error": "Type a category first."}
    try:
        return classify.check_category(name, others)
    except Exception as error:
        return {"error": str(error)}


@app.post("/classify")
def classify_item(item: str = Body(), categories: list[str] = Body()):
    """Run both engines and return both answers."""
    item = item.strip()
    if not item:
        return {"error": "Type an item first."}
    answers = {"categories": classify.add_other(categories)}
    try:
        answers["jev"] = classify.classify_with_jev(item, categories)
    except Exception as error:
        answers["jev"] = {"error": str(error)}
    try:
        answers["gpt"] = classify.classify_with_gpt(item, categories)
    except Exception as error:
        answers["gpt"] = {"error": str(error)}
    return answers
