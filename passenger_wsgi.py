import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote

from server import (
    MODEL,
    MissingApiKey,
    evaluate_with_openai,
    load_usage_events,
    rule_based_evaluation,
    summarize_usage,
)


ROOT = Path(__file__).resolve().parent


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method == "GET" and path == "/api/ai-status":
      return json_response(start_response, {
          "configured": bool(__import__("os").environ.get("OPENAI_API_KEY")),
          "model": MODEL,
          "mode": "platform_managed",
      })

    if method == "GET" and path == "/api/ai-usage":
      return json_response(start_response, summarize_usage(load_usage_events()))

    if method == "POST" and path == "/api/bot-intake":
      try:
          payload = read_json(environ)
          result = evaluate_with_openai(payload)
      except MissingApiKey:
          result = rule_based_evaluation(payload, ai_enabled=False)
      except Exception as exc:
          result = rule_based_evaluation(payload, ai_enabled=False)
          result["warning"] = f"KI-Auswertung nicht verfuegbar: {exc}"
      return json_response(start_response, result)

    if method == "GET":
      return static_response(start_response, path)

    return text_response(start_response, "Method not allowed", status="405 Method Not Allowed")


def read_json(environ):
    length = int(environ.get("CONTENT_LENGTH") or "0")
    body = environ["wsgi.input"].read(length).decode("utf-8")
    return json.loads(body or "{}")


def json_response(start_response, payload, status="200 OK"):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def text_response(start_response, text, status="200 OK"):
    body = text.encode("utf-8")
    start_response(status, [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def static_response(start_response, path):
    clean_path = unquote(path.lstrip("/")) or "index.html"
    target = (ROOT / clean_path).resolve()
    if ROOT not in target.parents and target != ROOT:
        return text_response(start_response, "Forbidden", status="403 Forbidden")
    if target.is_dir():
        target = target / "index.html"
    if not target.exists():
        target = ROOT / "index.html"

    content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    body = target.read_bytes()
    start_response("200 OK", [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
    ])
    return [body]
