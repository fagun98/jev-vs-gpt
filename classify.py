"""Ask Jev and GPT to put one item into a category."""

import argparse
import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url, key, body):
    """Send JSON and return the reply plus the time in milliseconds."""
    data = json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            reply = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:180]
        raise RuntimeError(f"The model call failed ({error.code}). {detail}") from error
    milliseconds = round((time.perf_counter() - start) * 1000)
    return reply, milliseconds


def add_other(categories):
    """Append Other to the three category names."""
    labels = [name.strip() for name in categories if name.strip()]
    if "Other" not in labels:
        labels.append("Other")
    return labels


def read_label(text, categories):
    """Keep the reply only if it is one of the labels, otherwise Other."""
    cleaned = (text or "").strip().strip(".,\"'`")
    for label in categories:
        if cleaned.lower() == label.lower():
            return label
    return "Other"


def check_category(name, others):
    """Ask Jev if a category is valid and if it overlaps the other names."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Add TYPESAFE_API_KEY to the .env file.")
    name = name.strip()
    filled = [other.strip() for other in others if other and other.strip()]
    questions = {
        "valid": {
            "type": "noul",
            "instructions": f"Is '{name}' a real category, not a vague word?",
        }
    }
    for index, other in enumerate(filled):
        questions[f"overlap_{index}"] = {
            "type": "score",
            "instructions": f"How much does '{name}' overlap with '{other}'?",
            "criteria": ["does not overlap", "overlaps"],
        }
    reply, _milliseconds = post_json(
        "https://api.typesafe.ai/v1/systemone",
        key,
        {"model": "jev-latest", "state": name, "questions": questions},
    )
    answers = reply["answers"]
    valid = answers["valid"].get("noul", 0) >= 0.5
    overlapped = []
    for index, other in enumerate(filled):
        score = answers[f"overlap_{index}"].get("score", 0)
        if score >= 0.5:
            overlapped.append(other)
    if not valid:
        return {"ok": False, "reason": "Too vague", "overlapped": overlapped}
    if overlapped:
        return {
            "ok": False,
            "reason": "Overlaps with " + overlapped[0],
            "overlapped": overlapped,
        }
    return {"ok": True, "reason": "Looks valid", "overlapped": []}


def classify_with_jev(item, categories):
    """Ask Jev which category the item belongs to."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Add TYPESAFE_API_KEY to the .env file.")
    labels = add_other(categories)
    criteria = {
        label: "None of the categories" if label == "Other" else label
        for label in labels
    }
    body = {
        "model": "jev-latest",
        "state": item,
        "questions": {
            "category": {
                "type": "choice",
                "instructions": "Which category does this item belong to?",
                "criteria": criteria,
            }
        },
    }
    reply, milliseconds = post_json(
        "https://api.typesafe.ai/v1/systemone",
        key,
        body,
    )
    answer = reply["answers"]["category"]
    return {
        "category": read_label(answer.get("choice"), labels),
        "ms": milliseconds,
        "confidence": answer.get("confidence"),
    }


def classify_with_gpt(item, categories):
    """Ask GPT the same choice in one sentence."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Add OPENAI_API_KEY to the .env file.")
    labels = add_other(categories)
    names = ", ".join(labels)
    prompt = (
        f"Classify the item into one of the following categories:\n {names} \n\n"
        f"Item: {item} \n\n"
        "Reply with one category name only."
    )
    body = {
        "model": "gpt-5-nano",
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 200,
    }

    reply, milliseconds = post_json(
        "https://api.openai.com/v1/chat/completions",
        key,
        body,
    )    

    text = reply["choices"][0]["message"]["content"]

    return {
        "category": read_label(text, labels),
        "ms": milliseconds,
    }


def main():
    """Read the query and print the Jev result, the GPT result, or both."""
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--engine", choices=["jev", "gpt", "both"], required=True)
    parser.add_argument("--categories", nargs="+", required=True)
    args = parser.parse_args()
    if args.engine in ("jev", "both"):
        result = classify_with_jev(args.query, args.categories)
        print("jev")
        print("category:", result["category"])
        print("ms:", result["ms"])
        print("confidence:", result["confidence"])
    if args.engine == "both":
        print()
    if args.engine in ("gpt", "both"):
        result = classify_with_gpt(args.query, args.categories)
        print("gpt")
        print("category:", result["category"])
        print("ms:", result["ms"])


if __name__ == "__main__":
    main()
