import json
import os
import re
import base64
import html
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OPENAI_API_URL = "https://api.openai.com/v1/responses"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"
USAGE_LOG = ROOT / "ai_usage_events.json"
CONVERSATION_LOG = ROOT / "whatsapp_conversations.json"
DOCUMENT_LABELS = {
    "cv": "Lebenslauf",
    "certificate": "Zertifikate",
    "id": "Ausweis",
}
REQUIRED_DOCUMENTS = ["cv", "certificate", "id"]


class RecruitingHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path == "/api/whatsapp/inbound":
            try:
                payload = self._read_form()
                result = handle_whatsapp_inbound(payload)
            except Exception as exc:
                result = {
                    "reply": "Danke fuer deine Nachricht. Ich pruefe das gerade und melde mich gleich wieder.",
                    "warning": str(exc),
                }
            self._send_twiml(result.get("reply", "Danke, deine Nachricht wurde erfasst."))
            return

        if self.path == "/api/whatsapp/send":
            try:
                payload = self._read_json()
                result = send_whatsapp_with_twilio(payload)
            except Exception as exc:
                result = {"sent": False, "error": safe_twilio_error(exc)}
            self._send_json(result, status=200 if result.get("sent") else 400)
            return

        if self.path != "/api/bot-intake":
            self.send_error(404, "Not found")
            return

        try:
            payload = self._read_json()
            result = evaluate_with_openai(payload)
        except MissingApiKey:
            result = rule_based_evaluation(payload, ai_enabled=False)
        except Exception as exc:
            result = rule_based_evaluation(payload, ai_enabled=False)
            result["warning"] = f"KI-Auswertung nicht verfuegbar: {exc}"

        self._send_json(result)

    def do_GET(self):
        if self.path == "/api/ai-status":
            self._send_json({
                "configured": bool(os.environ.get("OPENAI_API_KEY")),
                "model": MODEL,
                "mode": "platform_managed",
            })
            return
        if self.path == "/api/twilio-status":
            self._send_json({
                "configured": twilio_configured(),
                "from": mask_phone(os.environ.get("TWILIO_WHATSAPP_FROM", "")),
                "mode": "whatsapp_business",
            })
            return
        if self.path == "/api/ai-usage":
            self._send_json(summarize_usage(load_usage_events()))
            return
        if self.path == "/api/whatsapp-conversations":
            self._send_json(load_conversations())
            return
        super().do_GET()

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed.items()}

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_twiml(self, message):
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{html.escape(message)}</Message></Response>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MissingApiKey(Exception):
    pass


class MissingTwilioConfig(Exception):
    pass


def twilio_configured():
    return all(os.environ.get(name) for name in [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
    ])


def send_whatsapp_with_twilio(payload):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = normalize_twilio_whatsapp(os.environ.get("TWILIO_WHATSAPP_FROM", ""))
    to_number = normalize_twilio_whatsapp(payload.get("to", ""))
    message = str(payload.get("message", "")).strip()

    if not all([account_sid, auth_token, from_number]):
        raise MissingTwilioConfig("Twilio ist noch nicht vollstaendig konfiguriert.")
    if not to_number:
        raise ValueError("Empfaenger-WhatsApp-Nummer fehlt.")
    if not message:
        raise ValueError("Nachrichtentext fehlt.")

    form_data = urllib.parse.urlencode({
        "From": from_number,
        "To": to_number,
        "Body": message,
    }).encode("utf-8")
    token = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"{TWILIO_API_BASE}/Accounts/{account_sid}/Messages.json",
        data=form_data,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(read_http_error(exc))

    return {
        "sent": True,
        "sid": data.get("sid"),
        "status": data.get("status"),
        "to": mask_phone(to_number),
        "from": mask_phone(from_number),
    }


def normalize_twilio_whatsapp(value):
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith("whatsapp:"):
        return cleaned
    number = re.sub(r"[^\d+]", "", cleaned)
    if not number.startswith("+"):
        number = f"+{number}"
    return f"whatsapp:{number}"


def mask_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) < 4:
        return ""
    return f"***{digits[-4:]}"


def read_http_error(exc):
    try:
        return exc.read().decode("utf-8")
    except Exception:
        return ""


def safe_twilio_error(exc):
    message = str(exc)
    if isinstance(exc, MissingTwilioConfig):
        return "Twilio ist noch nicht konfiguriert. Setze TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN und TWILIO_WHATSAPP_FROM im Server."
    if "not a valid whatsapp sender" in message.lower() or "from" in message.lower():
        return "Twilio WhatsApp-Absender ist nicht korrekt freigeschaltet oder falsch eingetragen."
    if "not a valid phone number" in message.lower() or "to" in message.lower():
        return "Empfaenger-Nummer ist ungueltig. Nutze internationales Format, z. B. +491701234567."
    if "authenticate" in message.lower() or "account_sid" in message.lower():
        return "Twilio Login-Daten sind ungueltig. Account SID und Auth Token pruefen."
    return "WhatsApp konnte nicht gesendet werden. Bitte Twilio-Konfiguration und Server-Logs pruefen."


def handle_whatsapp_inbound(form):
    from_number = normalize_twilio_whatsapp(form.get("From", ""))
    to_number = normalize_twilio_whatsapp(form.get("To", ""))
    body = str(form.get("Body", "")).strip()
    media = extract_twilio_media(form)
    conversation = append_conversation_event(from_number, {
        "direction": "inbound",
        "from": from_number,
        "to": to_number,
        "body": body,
        "media": media,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })

    try:
        result = continue_whatsapp_intake_with_openai(from_number, conversation)
    except MissingApiKey:
        result = continue_whatsapp_intake_rule_based(from_number, conversation)
    except Exception as exc:
        result = continue_whatsapp_intake_rule_based(from_number, conversation)
        result["warning"] = str(exc)

    append_conversation_event(from_number, {
        "direction": "outbound",
        "from": to_number,
        "to": from_number,
        "body": result["reply"],
        "candidate": result.get("candidate", {}),
        "missingFields": result.get("missingFields", []),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })
    return result


def continue_whatsapp_intake_with_openai(phone, conversation):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise MissingApiKey()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reply": {"type": "string"},
            "candidate": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "location": {"type": "string"},
                    "experience": {"type": "string"},
                    "availability": {"type": "string"},
                    "salary": {"type": "string"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                    "documents": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "role", "location", "experience", "availability", "salary", "skills", "documents"],
            },
            "missingFields": {"type": "array", "items": {"type": "string"}},
            "readyForRecruiter": {"type": "boolean"},
        },
        "required": ["reply", "candidate", "missingFields", "readyForRecruiter"],
    }
    messages = conversation[-12:]
    body = {
        "model": MODEL,
        "instructions": (
            "Du bist ein WhatsApp-Recruiting-Bot. Fuehre ein kurzes, freundliches Intake-Gespraech. "
            "Sammle nacheinander: Name, Zielrolle, Ort, Berufserfahrung, Skills, Verfuegbarkeit, Gehaltswunsch, "
            "Lebenslauf, Zertifikate und Ausweis. Wenn Medien gesendet wurden, werte sie als Dokumente und frage "
            "nur noch nach fehlenden Dokumenten. Stelle immer nur 1 bis 2 konkrete Rueckfragen pro Antwort. "
            "Wenn alle Kerndaten vorhanden sind, bestaetige die Uebergabe an den Recruiter. "
            "Antworte auf Deutsch und nur im JSON-Schema."
        ),
        "input": json.dumps({"phone": phone, "conversation": messages}, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "whatsapp_recruiting_intake",
                "schema": schema,
                "strict": True,
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(safe_openai_error(exc))

    text = data.get("output_text") or extract_output_text(data)
    result = json.loads(text)
    result["aiEnabled"] = True
    result["model"] = MODEL
    result["usage"] = normalize_openai_usage(data.get("usage", {}))
    result["score"] = 100 if result.get("readyForRecruiter") else max(20, 100 - (len(result.get("missingFields", [])) * 10))
    log_usage_event({"organizationId": "demo-org", "userId": phone}, result, ai_enabled=True)
    return result


def continue_whatsapp_intake_rule_based(phone, conversation):
    inbound_text = "\n".join(event.get("body", "") for event in conversation if event.get("direction") == "inbound")
    documents = infer_documents_from_conversation(conversation)
    candidate = {
        "name": "",
        "role": extract_match(inbound_text, r"(fahrer|pflege|sales|hr|lager|logistik|entwickler|manager)") or "",
        "location": extract_match(inbound_text, r"(berlin|hamburg|muenchen|koeln|st\.?\s*georgen|stuttgart|frankfurt)") or "",
        "experience": extract_match(inbound_text, r"(\d+\s*(jahr|jahre|jahren).{0,40})") or inbound_text[-180:],
        "availability": extract_match(inbound_text, r"(sofort|ab\s+\d{1,2}\.\d{1,2}\.\d{2,4}|verfuegbar|verfügbar|kuendigung|kündigung)") or "",
        "salary": extract_match(inbound_text, r"(\d{2,3}[\.\s]?\d{3}|\d{3,5})\s*(eur|euro|brutto|netto)?") or "",
        "skills": extract_skills("", inbound_text),
        "documents": documents,
    }
    missing = []
    if not candidate["experience"]:
        missing.append("Berufserfahrung")
    if not candidate["availability"]:
        missing.append("Verfuegbarkeit")
    if not candidate["salary"]:
        missing.append("Gehaltswunsch")
    missing.extend(DOCUMENT_LABELS[doc] for doc in REQUIRED_DOCUMENTS if doc not in documents)

    if "Berufserfahrung" in missing:
        reply = "Danke dir. Wie viele Jahre Erfahrung hast du genau und in welchen Aufgaben warst du taetig?"
    elif "Verfuegbarkeit" in missing or "Gehaltswunsch" in missing:
        reply = "Super, danke. Ab wann bist du verfuegbar und welche Gehaltsvorstellung hast du?"
    elif any(label in missing for label in DOCUMENT_LABELS.values()):
        reply = "Danke. Bitte sende mir jetzt noch deinen Lebenslauf, Zertifikate und einen Ausweis als Datei oder Foto hier in WhatsApp."
    else:
        reply = "Perfekt, ich habe die wichtigsten Daten und Dokumente erfasst. Ich gebe dein Profil jetzt an den Recruiter weiter."

    return {
        "reply": reply,
        "candidate": candidate,
        "missingFields": missing,
        "readyForRecruiter": not missing,
        "aiEnabled": False,
    }


def extract_twilio_media(form):
    media = []
    try:
        count = int(form.get("NumMedia", "0") or 0)
    except ValueError:
        count = 0
    for index in range(count):
        media.append({
            "url": form.get(f"MediaUrl{index}", ""),
            "contentType": form.get(f"MediaContentType{index}", ""),
        })
    return media


def infer_documents_from_conversation(conversation):
    documents = set()
    for event in conversation:
        text = event.get("body", "").lower()
        if "lebenslauf" in text or "cv" in text:
            documents.add("cv")
        if "zertifikat" in text or "schein" in text or "abschluss" in text:
            documents.add("certificate")
        if "ausweis" in text or "pass" in text or "id" in text:
            documents.add("id")
        for media in event.get("media", []):
            content_type = media.get("contentType", "")
            if "pdf" in content_type or "image" in content_type:
                if "cv" not in documents:
                    documents.add("cv")
                elif "certificate" not in documents:
                    documents.add("certificate")
                else:
                    documents.add("id")
    return [doc for doc in REQUIRED_DOCUMENTS if doc in documents]


def append_conversation_event(phone, event):
    conversations = load_conversations()
    key = phone or "unknown"
    conversations.setdefault(key, [])
    conversations[key].append(event)
    conversations[key] = conversations[key][-80:]
    CONVERSATION_LOG.write_text(json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8")
    return conversations[key]


def load_conversations():
    if not CONVERSATION_LOG.exists():
        return {}
    try:
        return json.loads(CONVERSATION_LOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def evaluate_with_openai(payload):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise MissingApiKey()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "role": {"type": "string"},
            "location": {"type": "string"},
            "channel": {"type": "string"},
            "phone": {"type": "string"},
            "contactStatus": {"type": "string"},
            "whatsappOptIn": {"type": "boolean"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "skills": {"type": "array", "items": {"type": "string"}},
            "experience": {"type": "string"},
            "availability": {"type": "string"},
            "salary": {"type": "string"},
            "documents": {"type": "array", "items": {"type": "string"}},
            "missingDocuments": {"type": "array", "items": {"type": "string"}},
            "checklist": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "done": {"type": "boolean"},
                    },
                    "required": ["label", "done"],
                },
            },
            "nextAction": {"type": "string"},
            "summary": {"type": "string"},
            "whatsappMessage": {"type": "string"},
        },
        "required": [
            "name",
            "role",
            "location",
            "channel",
            "phone",
            "contactStatus",
            "whatsappOptIn",
            "score",
            "skills",
            "experience",
            "availability",
            "salary",
            "documents",
            "missingDocuments",
            "checklist",
            "nextAction",
            "summary",
            "whatsappMessage",
        ],
    }

    body = {
        "model": MODEL,
        "instructions": (
            "Du bist ein KI-Recruiting-Bot fuer eine Recruiting-Agentur. "
            "WhatsApp ist der Hauptkanal. Wenn Telefonnummer oder WhatsApp-Opt-in fehlen, "
            "darfst du keine vollstaendige Qualifizierung annehmen, sondern musst als naechste Aktion "
            "Kontaktfreigabe oder Telefonnummer anfordern. Wenn noch keine Antworten vorliegen, "
            "erstelle eine kurze WhatsApp-Erstnachricht. Analysiere den Erstkontakt, extrahiere strukturierte Bewerberdaten, "
            "pruefe Pflichtdokumente und gib eine knappe Recruiter-Empfehlung. "
            "Antworte nur im geforderten JSON-Schema."
        ),
        "input": json.dumps(payload, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "candidate_intake",
                "schema": schema,
                "strict": True,
            }
        },
    }

    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(safe_openai_error(exc))

    text = data.get("output_text")
    if not text:
        text = extract_output_text(data)
    result = json.loads(text)
    result["aiEnabled"] = True
    result["model"] = MODEL
    result["usage"] = normalize_openai_usage(data.get("usage", {}))
    result["responseId"] = data.get("id")
    log_usage_event(payload, result, ai_enabled=True)
    return result


def extract_output_text(data):
    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in ("output_text", "text"):
                chunks.append(content.get("text", ""))
    return "".join(chunks)


def safe_openai_error(exc):
    if exc.code == 401:
        return "OpenAI API Fehler 401: API-Key ist ungueltig, abgelaufen, widerrufen oder unvollstaendig kopiert."
    if exc.code == 429:
        return "OpenAI API Fehler 429: Limit erreicht oder Abrechnung/Quota pruefen."
    if exc.code == 400:
        return "OpenAI API Fehler 400: Anfrageformat oder Modellparameter pruefen."
    return f"OpenAI API Fehler {exc.code}: Bitte Server-Logs pruefen."


def rule_based_evaluation(payload, ai_enabled):
    answers = payload.get("answers", "")
    documents = payload.get("documents", [])
    phone = payload.get("phone", "")
    whatsapp_opt_in = bool(payload.get("whatsappOptIn"))
    missing = [doc for doc in REQUIRED_DOCUMENTS if doc not in documents]
    has_availability = bool(re.search(r"verfuegbar|verfügbar|sofort|kuendigung|kündigung|start", answers, re.I))
    has_experience = bool(re.search(r"jahr|erfahrung|ausbildung|zertifikat|abschluss|projekt", answers, re.I))
    has_salary = bool(re.search(r"gehalt|lohn|stunde|brutto|netto|euro|eur", answers, re.I))

    score = (30 if phone else 15) + min(len(documents) * 12, 36)
    score += 10 if has_availability else 0
    score += 12 if has_experience else 0
    score += 7 if has_salary else 0
    score += 5 if whatsapp_opt_in else 0
    score = min(score, 100)

    checklist = [
        {"label": "Telefonnummer fuer WhatsApp erfasst", "done": bool(phone)},
        {"label": "WhatsApp-Kontakt erlaubt", "done": whatsapp_opt_in},
        {"label": "Kontaktdaten und Zielrolle erfasst", "done": bool(payload.get("name") and payload.get("role"))},
        {"label": "Berufserfahrung erkennbar", "done": has_experience},
        {"label": "Verfuegbarkeit geklaert", "done": has_availability},
        {"label": "Gehaltswunsch geklaert", "done": has_salary},
    ]
    checklist.extend({"label": DOCUMENT_LABELS[doc], "done": doc in documents} for doc in REQUIRED_DOCUMENTS)

    whatsapp_message = create_whatsapp_message(payload)
    if not phone:
        next_action = "Telefonnummer fehlt. Bot kann keinen WhatsApp-Erstkontakt starten."
    elif not whatsapp_opt_in:
        next_action = "WhatsApp-Opt-in fehlt. Bitte Einwilligung klaeren oder alternativen Kanal nutzen."
    elif not answers:
        next_action = "Bot sendet WhatsApp-Erstnachricht und wartet auf Antwort."
    elif missing:
        next_action = "Bot fordert noch " + ", ".join(DOCUMENT_LABELS[doc] for doc in missing) + " an."
    elif score >= 75:
        next_action = "Bewerber ist vollstaendig genug fuer Recruiter Review und Matching."
    else:
        next_action = "Bot stellt Rueckfragen zu Erfahrung, Verfuegbarkeit und Gehaltswunsch."

    skills = extract_skills(payload.get("role", ""), answers)
    result = {
        "aiEnabled": ai_enabled,
        "model": MODEL if ai_enabled else "demo-rule-engine",
        "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
        "name": payload.get("name", ""),
        "role": payload.get("role", ""),
        "location": payload.get("location", ""),
        "channel": payload.get("channel", ""),
        "phone": phone,
        "contactStatus": payload.get("contactStatus", "new"),
        "whatsappOptIn": whatsapp_opt_in,
        "score": score,
        "skills": skills,
        "experience": answers,
        "availability": extract_match(answers, r"(sofort|ab\s+\d{1,2}\.\d{1,2}\.\d{2,4}|verfuegbar|verfügbar)"),
        "salary": extract_match(answers, r"(\d{2,3}[\.\s]?\d{3}|\d{3,5})\s*(eur|euro|brutto|netto)?"),
        "documents": documents,
        "missingDocuments": missing,
        "checklist": checklist,
        "nextAction": next_action,
        "whatsappMessage": whatsapp_message,
        "summary": f"Bot Intake: {score}% qualifiziert. {next_action}",
    }
    log_usage_event(payload, result, ai_enabled=ai_enabled)
    return result


def normalize_openai_usage(usage):
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or input_tokens + output_tokens
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
    }


def log_usage_event(payload, result, ai_enabled):
    event = {
        "id": result.get("responseId") or f"local-{datetime.now(timezone.utc).timestamp()}",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "organizationId": payload.get("organizationId") or "demo-org",
        "userId": payload.get("userId") or "demo-user",
        "feature": "bot_intake",
        "aiEnabled": ai_enabled,
        "model": result.get("model", MODEL),
        "score": result.get("score", 0),
        "inputTokens": result.get("usage", {}).get("inputTokens", 0),
        "outputTokens": result.get("usage", {}).get("outputTokens", 0),
        "totalTokens": result.get("usage", {}).get("totalTokens", 0),
    }
    events = load_usage_events()
    events.append(event)
    USAGE_LOG.write_text(json.dumps(events[-1000:], ensure_ascii=False, indent=2), encoding="utf-8")


def load_usage_events():
    if not USAGE_LOG.exists():
        return []
    try:
        return json.loads(USAGE_LOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def summarize_usage(events):
    total_actions = len(events)
    ai_actions = sum(1 for event in events if event.get("aiEnabled"))
    total_tokens = sum(event.get("totalTokens", 0) for event in events)
    input_tokens = sum(event.get("inputTokens", 0) for event in events)
    output_tokens = sum(event.get("outputTokens", 0) for event in events)
    latest = events[-10:][::-1]
    return {
        "totalActions": total_actions,
        "aiActions": ai_actions,
        "demoActions": total_actions - ai_actions,
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "latest": latest,
    }


def extract_skills(role, answers):
    blocked = {"ich", "und", "oder", "mit", "der", "die", "das", "eine", "ein"}
    values = re.split(r"[,\s]+", f"{role} {answers}")
    skills = []
    for value in values:
        cleaned = value.strip(" .;:").capitalize()
        if len(cleaned) > 2 and cleaned.lower() not in blocked and cleaned not in skills:
            skills.append(cleaned)
    return skills[:8]


def extract_match(text, pattern):
    match = re.search(pattern, text, re.I)
    return match.group(0) if match else ""


def create_whatsapp_message(payload):
    name = payload.get("name", "Hallo")
    role = payload.get("role", "die Stelle")
    location = payload.get("location", "deiner Region")
    return (
        f"Hallo {name}, hier ist RecruitOS im Auftrag deiner Recruiting-Agentur. "
        f"Du hast Interesse an der Rolle {role} in {location} angegeben. "
        "Kannst du mir kurz deine Erfahrung, Verfuegbarkeit, Gehaltswunsch "
        "und vorhandene Dokumente nennen?"
    )


def main():
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), RecruitingHandler)
    print(f"RecruitOS laeuft auf {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
