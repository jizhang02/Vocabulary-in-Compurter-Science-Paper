"""Offline spaCy suggestions. Nothing is written to the public database."""
import argparse
import json
from pathlib import Path


def suggest(nlp, text):
    doc = nlp(text)
    return {
        "text": text,
        "tokens": [{"text": t.text, "lemma": t.lemma_, "pos": t.pos_, "start": t.idx, "end": t.idx + len(t.text)}
                   for t in doc if not t.is_space and not t.is_punct],
        "candidate_phrases": list(dict.fromkeys(chunk.text for chunk in doc.noun_chunks)),
        "domain_tags": [],
        "review_required": True,
        "note": "候选短语不等于专业术语；词性依赖上下文，领域需人工确认。",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="English sentence or abstract (prefer context to isolated words)")
    parser.add_argument("--input", type=Path, help="UTF-8 plain text file")
    parser.add_argument("--output", type=Path, help="Write reviewable JSON suggestions")
    parser.add_argument("--model", default="en_core_web_sm")
    args = parser.parse_args()
    if bool(args.text) == bool(args.input):
        parser.error("Provide exactly one of --text or --input")
    try:
        import spacy
    except ImportError:
        parser.exit(1, "Install requirements-nlp.txt and run: python -m spacy download en_core_web_sm\n")
    try:
        nlp = spacy.load(args.model)
    except OSError:
        parser.exit(1, f"Model missing. Run: python -m spacy download {args.model}\n")
    if not nlp.has_pipe("parser") or not nlp.has_pipe("lemmatizer"):
        parser.error("Use a pipeline with a parser and lemmatizer")
    text = args.text if args.text else args.input.read_text(encoding="utf-8")
    result = suggest(nlp, text)
    result["model"] = args.model
    result["model_version"] = nlp.meta.get("version")
    result["spacy_version"] = spacy.__version__
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
