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
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DEFAULT_ORGANIZATION_ID = os.environ.get("DEFAULT_ORGANIZATION_ID", "")
USAGE_LOG = ROOT / "ai_usage_events.json"
CONVERSATION_LOG = ROOT / "whatsapp_conversations.json"
MEMORY_LOG = ROOT / "bot_memory.json"
TRAINING_LOG = ROOT / "bot_training.json"
PERSONALITY_LOG = ROOT / "bot_personality.json"
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
        if self.path == "/api/training/document":
            self._send_json(save_training_document(self._read_json()))
            return
        if self.path == "/api/training/document/delete":
            self._send_json(delete_training_document(self._read_json()))
            return
        if self.path == "/api/training/prompt":
            self._send_json(save_system_prompt(self._read_json()))
            return
        if self.path == "/api/training/prompt/delete":
            self._send_json(delete_system_prompt(self._read_json()))
            return
        if self.path == "/api/personality":
            self._send_json(save_personality(self._read_json()))
            return
        if self.path == "/api/memory":
            self._send_json(save_memory_entry(self._read_json()))
            return

        if self.path == "/api/whatsapp/inbound":
            try:
                payload = self._read_form()
                result = handle_whatsapp_inbound(payload)
            except Exception as exc:
                result = {
                    "reply": "Danke für deine Nachricht. Ich prüfe das gerade und melde mich gleich wieder.",
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
            result["warning"] = f"KI-Auswertung nicht verfügbar: {exc}"

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
        if self.path == "/api/bot-data":
            self._send_json({
                "conversations": load_conversations(),
                "memory": load_memory(),
                "training": load_training(),
                "personality": load_personality(),
            })
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
        raise MissingTwilioConfig("Twilio ist noch nicht vollständig konfiguriert.")
    if not to_number:
        raise ValueError("Empfänger-WhatsApp-Nummer fehlt.")
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
        return "Empfänger-Nummer ist ungültig. Nutze internationales Format, z. B. +491701234567."
    if "authenticate" in message.lower() or "account_sid" in message.lower():
        return "Twilio Login-Daten sind ungültig. Account SID und Auth Token prüfen."
    return "WhatsApp konnte nicht gesendet werden. Bitte Twilio-Konfiguration und Server-Logs prüfen."


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
    update_memory_from_intake(from_number, result)
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
    bot_context = build_bot_context(phone)
    body = {
        "model": MODEL,
        "instructions": build_inbound_instructions(bot_context),
        "input": json.dumps({"phone": phone, "conversation": messages, "context": bot_context}, ensure_ascii=False),
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
        "location": extract_match(inbound_text, r"(berlin|hamburg|muenchen|münchen|koeln|köln|st\.?\s*georgen|stuttgart|frankfurt)") or "",
        "experience": extract_match(inbound_text, r"(\d+\s*(jahr|jahre|jahren).{0,40})") or inbound_text[-180:],
        "availability": extract_match(inbound_text, r"(sofort|ab\s+\d{1,2}\.\d{1,2}\.\d{2,4}|verfügbar|kuendigung|kündigung)") or "",
        "salary": extract_match(inbound_text, r"(\d{2,3}[\.\s]?\d{3}|\d{3,5})\s*(eur|euro|brutto|netto)?") or "",
        "skills": extract_skills("", inbound_text),
        "documents": documents,
    }
    missing = []
    if not candidate["experience"]:
        missing.append("Berufserfahrung")
    if not candidate["availability"]:
        missing.append("Verfügbarkeit")
    if not candidate["salary"]:
        missing.append("Gehaltswunsch")
    missing.extend(DOCUMENT_LABELS[doc] for doc in REQUIRED_DOCUMENTS if doc not in documents)

    if "Berufserfahrung" in missing:
        reply = "Danke dir. Wie viele Jahre Erfahrung hast du genau und in welchen Aufgaben warst du tätig?"
    elif "Verfügbarkeit" in missing or "Gehaltswunsch" in missing:
        reply = "Super, danke. Ab wann bist du verfügbar und welche Gehaltsvorstellung hast du?"
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


def build_inbound_instructions(context):
    return (
        build_base_bot_instructions(context)
        + " Führe ein natürliches WhatsApp-Intake-Gespräch. Sammle nacheinander: Name, Zielrolle, Ort, "
        "Berufserfahrung, Skills, Verfügbarkeit, Gehaltswunsch, Lebenslauf, Zertifikate und Ausweis. "
        "Dokumente gelten nur dann als vorhanden, wenn sie als WhatsApp-Medien, Upload oder Datenbankeintrag vorliegen. "
        "Behaupte niemals, dass Dokumente vorhanden sind, wenn sie nicht im Kontext stehen. Stelle immer nur 1 bis 2 konkrete Rückfragen. "
        "Nutze Memory, Trainingswissen und aktive System-Prompts, um persönlicher und weniger generisch zu antworten. "
        "Wenn alle Kerndaten vorhanden sind, bestätige die Übergabe an den Recruiter. Antworte nur im JSON-Schema."
    )


def build_base_bot_instructions(context):
    personality = context.get("personality", {})
    prompts = context.get("activePrompts", [])
    memory = context.get("memory", {})
    training = context.get("trainingSnippets", [])
    return (
        "Du bist ein professioneller Recruiting-Mitarbeiter der Agentur, nicht ein generischer Chatbot. "
        "Du schreibst menschlich, empathisch, klar und individuell. Vermeide KI-Floskeln. "
        f"Kommunikationsstil: {personality.get('communicationStyle', 'professionell und freundlich')}. "
        f"Freundlichkeit: {personality.get('friendliness', 'hoch')}. "
        f"Professionalität: {personality.get('professionalism', 'hoch')}. "
        f"Humor: {personality.get('humor', 'dezent')}. "
        f"Verkaufsorientierung: {personality.get('salesOrientation', 'beratend')}. "
        f"Antwortlänge: {personality.get('answerLength', 'kurz bis mittel')}. "
        f"Sprache und Tonfall: {personality.get('tone', 'Deutsch, direkt und respektvoll')}. "
        f"Emoji-Nutzung: {personality.get('emojiUsage', 'sparsam')}. "
        f"Schwierige Situationen: {personality.get('difficultSituations', 'ruhig bleiben, klären, keine falschen Versprechen machen')}. "
        f"Kundenbezogene Memory: {json.dumps(memory, ensure_ascii=False)[:1600]}. "
        f"Aktive System-Prompts: {json.dumps(prompts, ensure_ascii=False)[:1600]}. "
        f"Trainingswissen: {json.dumps(training, ensure_ascii=False)[:2600]}. "
    )


def build_bot_context(customer_key):
    training = load_training()
    active_prompts = sorted(
        [prompt for prompt in training.get("prompts", []) if prompt.get("active", True)],
        key=lambda prompt: int(prompt.get("priority", 5)),
    )
    snippets = []
    for document in training.get("documents", []):
        if document.get("active", True):
            snippets.append({
                "title": document.get("title", "Dokument"),
                "type": document.get("type", "text"),
                "content": str(document.get("content", ""))[:1200],
            })
    return {
        "memory": load_memory().get(customer_key, {}),
        "activePrompts": active_prompts[:8],
        "trainingSnippets": snippets[:8],
        "personality": load_personality(),
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


def normalize_documents(documents):
    if not isinstance(documents, list):
        return []
    allowed = set(REQUIRED_DOCUMENTS)
    clean = []
    for document in documents:
        if document in allowed and document not in clean:
            clean.append(document)
    return clean


def apply_document_truth(payload, result):
    actual_documents = normalize_documents(payload.get("documents", []))
    missing = [doc for doc in REQUIRED_DOCUMENTS if doc not in actual_documents]
    result["documents"] = actual_documents
    result["missingDocuments"] = missing

    checklist = result.get("checklist", [])
    protected_labels = set(DOCUMENT_LABELS.values())
    checklist = [item for item in checklist if item.get("label") not in protected_labels]
    checklist.extend({"label": DOCUMENT_LABELS[doc], "done": doc in actual_documents} for doc in REQUIRED_DOCUMENTS)
    result["checklist"] = checklist

    if missing:
        missing_labels = ", ".join(DOCUMENT_LABELS[doc] for doc in missing)
        result["nextAction"] = f"Bot muss noch folgende Dokumente einholen: {missing_labels}."
    return result


def append_conversation_event(phone, event):
    conversations = load_conversations()
    key = phone or "unknown"
    conversations.setdefault(key, [])
    conversations[key].append(event)
    conversations[key] = conversations[key][-80:]
    CONVERSATION_LOG.write_text(json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8")
    sync_message_to_supabase(key, event)
    return conversations[key]


def load_conversations():
    if not CONVERSATION_LOG.exists():
        return {}
    try:
        return json.loads(CONVERSATION_LOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def update_memory_from_intake(customer_key, result):
    candidate = result.get("candidate", {})
    memory = load_memory()
    current = memory.get(customer_key, {
        "customerKey": customer_key,
        "knownFacts": [],
        "answeredQuestions": [],
        "preferences": [],
        "lastUpdated": "",
        "profile": {},
    })
    profile = current.get("profile", {})
    for key in ["name", "role", "location", "experience", "availability", "salary"]:
        value = candidate.get(key)
        if value:
            profile[key] = value
    if candidate.get("skills"):
        profile["skills"] = candidate.get("skills", [])
    if candidate.get("documents"):
        profile["documents"] = candidate.get("documents", [])
    for field in result.get("missingFields", []):
        if field not in current["answeredQuestions"]:
            continue
    summary = result.get("reply") or result.get("summary") or ""
    if summary:
        fact = summary[:260]
        if fact not in current["knownFacts"]:
            current["knownFacts"].append(fact)
    current["knownFacts"] = current["knownFacts"][-20:]
    current["profile"] = profile
    current["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    memory[customer_key] = current
    write_json(MEMORY_LOG, memory)
    sync_memory_to_supabase(customer_key, current, result)


def save_memory_entry(payload):
    customer_key = payload.get("customerKey") or payload.get("phone") or "manual"
    memory = load_memory()
    current = memory.get(customer_key, {
        "customerKey": customer_key,
        "knownFacts": [],
        "answeredQuestions": [],
        "preferences": [],
        "lastUpdated": "",
        "profile": {},
    })
    note = str(payload.get("note", "")).strip()
    if note and note not in current["knownFacts"]:
        current["knownFacts"].append(note)
    current["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    memory[customer_key] = current
    write_json(MEMORY_LOG, memory)
    sync_memory_to_supabase(customer_key, current, {"summary": note})
    return {"saved": True, "memory": current}


def save_training_document(payload):
    training = load_training()
    document_id = payload.get("id") or f"doc-{datetime.now(timezone.utc).timestamp()}"
    documents = [item for item in training.get("documents", []) if item.get("id") != document_id]
    documents.append({
        "id": document_id,
        "title": payload.get("title") or "Unbenanntes Dokument",
        "type": payload.get("type") or "text",
        "content": str(payload.get("content", ""))[:60000],
        "active": bool(payload.get("active", True)),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })
    training["documents"] = documents
    write_json(TRAINING_LOG, training)
    sync_training_document_to_supabase(documents[-1])
    return {"saved": True, "documentId": document_id, "training": training}


def delete_training_document(payload):
    training = load_training()
    document_id = payload.get("id")
    training["documents"] = [item for item in training.get("documents", []) if item.get("id") != document_id]
    write_json(TRAINING_LOG, training)
    delete_supabase_row("bot_training_documents", document_id)
    return {"deleted": True, "training": training}


def save_system_prompt(payload):
    training = load_training()
    prompt_id = payload.get("id") or f"prompt-{datetime.now(timezone.utc).timestamp()}"
    prompts = [item for item in training.get("prompts", []) if item.get("id") != prompt_id]
    prompts.append({
        "id": prompt_id,
        "title": payload.get("title") or "System-Prompt",
        "content": str(payload.get("content", ""))[:12000],
        "priority": int(payload.get("priority", 5) or 5),
        "active": bool(payload.get("active", True)),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })
    training["prompts"] = prompts
    write_json(TRAINING_LOG, training)
    sync_system_prompt_to_supabase(prompts[-1])
    return {"saved": True, "promptId": prompt_id, "training": training}


def delete_system_prompt(payload):
    training = load_training()
    prompt_id = payload.get("id")
    training["prompts"] = [item for item in training.get("prompts", []) if item.get("id") != prompt_id]
    write_json(TRAINING_LOG, training)
    delete_supabase_row("bot_system_prompts", prompt_id)
    return {"deleted": True, "training": training}


def save_personality(payload):
    personality = {
        "communicationStyle": payload.get("communicationStyle", "professionell und freundlich"),
        "friendliness": payload.get("friendliness", "hoch"),
        "politeness": payload.get("politeness", "hoch"),
        "humor": payload.get("humor", "dezent"),
        "professionalism": payload.get("professionalism", "hoch"),
        "salesOrientation": payload.get("salesOrientation", "beratend"),
        "answerLength": payload.get("answerLength", "kurz bis mittel"),
        "tone": payload.get("tone", "Deutsch, direkt und respektvoll"),
        "emojiUsage": payload.get("emojiUsage", "sparsam"),
        "difficultSituations": payload.get("difficultSituations", "ruhig bleiben, klären, keine falschen Versprechen machen"),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    write_json(PERSONALITY_LOG, personality)
    sync_personality_to_supabase(personality)
    return {"saved": True, "personality": personality}


def load_memory():
    return read_json(MEMORY_LOG, {})


def load_training():
    return read_json(TRAINING_LOG, {"documents": [], "prompts": []})


def load_personality():
    return read_json(PERSONALITY_LOG, {
        "communicationStyle": "professionell, menschlich und klar",
        "friendliness": "hoch",
        "politeness": "hoch",
        "humor": "dezent",
        "professionalism": "hoch",
        "salesOrientation": "beratend",
        "answerLength": "kurz bis mittel",
        "tone": "Deutsch, respektvoll, nahbar",
        "emojiUsage": "sparsam",
        "difficultSituations": "ruhig bleiben, empathisch reagieren, sauber an Recruiter eskalieren",
    })


def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def supabase_enabled():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and DEFAULT_ORGANIZATION_ID)


def supabase_headers(extra=None):
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def supabase_request(method, table, payload=None, query=""):
    if not supabase_enabled():
        return None
    url = f"{SUPABASE_URL}/rest/v1/{table}{query}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers=supabase_headers({"Prefer": "return=representation"}),
        method=method,
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


def supabase_select_one(table, query):
    result = supabase_request("GET", table, query=f"{query}&limit=1")
    if isinstance(result, list) and result:
        return result[0]
    return None


def sync_message_to_supabase(customer_key, event):
    if not supabase_enabled():
        return
    try:
        customer = get_or_create_supabase_customer(customer_key, event)
        conversation = get_or_create_supabase_conversation(customer)
        media = event.get("media", [])
        message = {
            "organization_id": DEFAULT_ORGANIZATION_ID,
            "conversation_id": conversation["id"],
            "customer_id": customer["id"],
            "direction": event.get("direction", "inbound"),
            "sender_type": "customer" if event.get("direction") == "inbound" else "bot",
            "body": event.get("body", ""),
            "media": media if isinstance(media, list) else [],
            "provider": "twilio",
            "metadata": {
                "from": event.get("from", ""),
                "to": event.get("to", ""),
                "candidate": event.get("candidate", {}),
                "missingFields": event.get("missingFields", []),
            },
        }
        supabase_request("POST", "bot_messages", [message])
        update_payload = {
            "last_message_at": event.get("createdAt") or datetime.now(timezone.utc).isoformat(),
            "summary": event.get("body", "")[:500],
        }
        supabase_request("PATCH", "bot_conversations", update_payload, query=f"?id=eq.{conversation['id']}")
    except Exception as exc:
        print(f"Supabase Message Sync fehlgeschlagen: {exc}")


def get_or_create_supabase_customer(customer_key, event):
    phone = customer_key or event.get("from", "")
    encoded_phone = urllib.parse.quote(phone, safe="")
    existing = supabase_select_one(
        "bot_customers",
        f"?organization_id=eq.{DEFAULT_ORGANIZATION_ID}&phone=eq.{encoded_phone}&select=id,organization_id,phone,display_name",
    )
    if existing:
        return existing
    payload = [{
        "organization_id": DEFAULT_ORGANIZATION_ID,
        "phone": phone,
        "display_name": phone.replace("whatsapp:", ""),
        "source": "whatsapp",
        "last_contact_at": event.get("createdAt") or datetime.now(timezone.utc).isoformat(),
        "profile": {},
    }]
    created = supabase_request("POST", "bot_customers", payload)
    return created[0]


def get_or_create_supabase_conversation(customer):
    existing = supabase_select_one(
        "bot_conversations",
        f"?organization_id=eq.{DEFAULT_ORGANIZATION_ID}&customer_id=eq.{customer['id']}&status=in.(open,waiting)&select=id,customer_id,organization_id,status",
    )
    if existing:
        return existing
    payload = [{
        "organization_id": DEFAULT_ORGANIZATION_ID,
        "customer_id": customer["id"],
        "channel": "whatsapp",
        "status": "open",
        "subject": "WhatsApp Intake",
        "last_message_at": datetime.now(timezone.utc).isoformat(),
    }]
    created = supabase_request("POST", "bot_conversations", payload)
    return created[0]


def sync_memory_to_supabase(customer_key, current, result):
    if not supabase_enabled():
        return
    try:
        customer = get_or_create_supabase_customer(customer_key, {
            "from": customer_key,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
        profile = current.get("profile", {})
        if profile:
            supabase_request("PATCH", "bot_customers", {"profile": profile}, query=f"?id=eq.{customer['id']}")
        summary = result.get("summary") or result.get("reply") or ""
        if summary:
            payload = [{
                "organization_id": DEFAULT_ORGANIZATION_ID,
                "customer_id": customer["id"],
                "memory_type": "note",
                "title": "Bot-Zusammenfassung",
                "content": summary[:2000],
                "importance": 5,
                "metadata": {"source": "bot"},
            }]
            supabase_request("POST", "bot_memory", payload)
    except Exception as exc:
        print(f"Supabase Memory Sync fehlgeschlagen: {exc}")


def sync_training_document_to_supabase(document):
    if not supabase_enabled():
        return
    try:
        payload = [{
            "organization_id": DEFAULT_ORGANIZATION_ID,
            "title": document.get("title", "Dokument"),
            "document_type": normalize_training_document_type(document.get("type", "text")),
            "content": document.get("content", ""),
            "active": bool(document.get("active", True)),
            "priority": int(document.get("priority", 5) or 5),
            "metadata": {"localId": document.get("id")},
        }]
        supabase_request("POST", "bot_training_documents", payload)
    except Exception as exc:
        print(f"Supabase Training Sync fehlgeschlagen: {exc}")


def sync_system_prompt_to_supabase(prompt):
    if not supabase_enabled():
        return
    try:
        payload = [{
            "organization_id": DEFAULT_ORGANIZATION_ID,
            "title": prompt.get("title", "System-Prompt"),
            "content": prompt.get("content", ""),
            "active": bool(prompt.get("active", True)),
            "priority": int(prompt.get("priority", 5) or 5),
        }]
        supabase_request("POST", "bot_system_prompts", payload)
    except Exception as exc:
        print(f"Supabase Prompt Sync fehlgeschlagen: {exc}")


def sync_personality_to_supabase(personality):
    if not supabase_enabled():
        return
    try:
        payload = [{
            "organization_id": DEFAULT_ORGANIZATION_ID,
            "name": "Standard",
            "active": True,
            "communication_style": personality.get("communicationStyle", "professionell und freundlich"),
            "friendliness": personality.get("friendliness", "hoch"),
            "politeness": personality.get("politeness", "hoch"),
            "humor": personality.get("humor", "dezent"),
            "professionalism": personality.get("professionalism", "hoch"),
            "sales_orientation": personality.get("salesOrientation", "beratend"),
            "answer_length": personality.get("answerLength", "kurz bis mittel"),
            "tone": personality.get("tone", "Deutsch, respektvoll, nahbar"),
            "emoji_usage": personality.get("emojiUsage", "sparsam"),
            "difficult_situations": personality.get("difficultSituations", ""),
        }]
        supabase_request("POST", "bot_personality_profiles", payload)
    except Exception as exc:
        print(f"Supabase Personality Sync fehlgeschlagen: {exc}")


def delete_supabase_row(table, local_id):
    if not supabase_enabled() or not local_id:
        return
    try:
        encoded = urllib.parse.quote(local_id, safe="")
        supabase_request("DELETE", table, query=f"?metadata->>localId=eq.{encoded}")
    except Exception as exc:
        print(f"Supabase Delete Sync fehlgeschlagen: {exc}")


def normalize_training_document_type(value):
    value = str(value or "text").lower()
    if value in {"text", "markdown", "pdf", "word", "website"}:
        return value
    return "other"


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

    bot_context = build_bot_context(normalize_twilio_whatsapp(payload.get("phone", "")) or payload.get("phone", "manual"))
    body = {
        "model": MODEL,
        "instructions": (
            build_base_bot_instructions(bot_context)
            + " WhatsApp ist der Hauptkanal. Wenn Telefonnummer oder WhatsApp-Opt-in fehlen, darfst du keine vollständige "
            "Qualifizierung annehmen, sondern musst als nächste Aktion Kontaktfreigabe oder Telefonnummer anfordern. "
            "Wenn noch keine Antworten vorliegen, erstelle eine individuelle WhatsApp-Erstnachricht. Analysiere den Erstkontakt, "
            "extrahiere strukturierte Bewerberdaten, prüfe Pflichtdokumente und gib eine knappe Recruiter-Empfehlung. "
            "Dokumente darfst du nur als vorhanden markieren, wenn sie ausdrücklich im Feld documents, als Upload oder in der Datenbank stehen. "
            "Wenn Erfahrung, Verfügbarkeit, Gehaltswunsch oder Dokumente fehlen, fordere sie aktiv an. "
            "Antworte nur im geforderten JSON-Schema."
        ),
        "input": json.dumps({"payload": payload, "context": bot_context}, ensure_ascii=False),
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
    result = apply_document_truth(payload, result)
    log_usage_event(payload, result, ai_enabled=True)
    update_memory_from_intake(normalize_twilio_whatsapp(payload.get("phone", "")) or payload.get("phone", "manual"), {
        "candidate": result,
        "summary": result.get("summary", ""),
        "missingFields": result.get("missingDocuments", []),
    })
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
        return "OpenAI API Fehler 401: API-Key ist ungültig, abgelaufen, widerrufen oder unvollständig kopiert."
    if exc.code == 429:
        return "OpenAI API Fehler 429: Limit erreicht oder Abrechnung/Quota prüfen."
    if exc.code == 400:
        return "OpenAI API Fehler 400: Anfrageformat oder Modellparameter prüfen."
    return f"OpenAI API Fehler {exc.code}: Bitte Server-Logs prüfen."


def rule_based_evaluation(payload, ai_enabled):
    answers = payload.get("answers", "")
    documents = normalize_documents(payload.get("documents", []))
    phone = payload.get("phone", "")
    whatsapp_opt_in = bool(payload.get("whatsappOptIn"))
    missing = [doc for doc in REQUIRED_DOCUMENTS if doc not in documents]
    has_availability = bool(re.search(r"verfügbar|sofort|kuendigung|kündigung|start", answers, re.I))
    has_experience = bool(re.search(r"jahr|erfahrung|ausbildung|zertifikat|abschluss|projekt", answers, re.I))
    has_salary = bool(re.search(r"gehalt|lohn|stunde|brutto|netto|euro|eur", answers, re.I))

    score = (30 if phone else 15) + min(len(documents) * 12, 36)
    score += 10 if has_availability else 0
    score += 12 if has_experience else 0
    score += 7 if has_salary else 0
    score += 5 if whatsapp_opt_in else 0
    score = min(score, 100)

    checklist = [
        {"label": "Telefonnummer für WhatsApp erfasst", "done": bool(phone)},
        {"label": "WhatsApp-Kontakt erlaubt", "done": whatsapp_opt_in},
        {"label": "Kontaktdaten und Zielrolle erfasst", "done": bool(payload.get("name") and payload.get("role"))},
        {"label": "Berufserfahrung erkennbar", "done": has_experience},
        {"label": "Verfügbarkeit geklärt", "done": has_availability},
        {"label": "Gehaltswunsch geklärt", "done": has_salary},
    ]
    checklist.extend({"label": DOCUMENT_LABELS[doc], "done": doc in documents} for doc in REQUIRED_DOCUMENTS)

    whatsapp_message = create_whatsapp_message(payload)
    if not phone:
        next_action = "Telefonnummer fehlt. Bot kann keinen WhatsApp-Erstkontakt starten."
    elif not whatsapp_opt_in:
        next_action = "WhatsApp-Opt-in fehlt. Bitte Einwilligung klären oder alternativen Kanal nutzen."
    elif not answers:
        next_action = "Bot sendet WhatsApp-Erstnachricht und wartet auf Antwort."
    elif missing:
        next_action = "Bot fordert noch " + ", ".join(DOCUMENT_LABELS[doc] for doc in missing) + " an."
    elif score >= 75:
        next_action = "Bewerber ist vollständig genug für Recruiter Review und Matching."
    else:
        next_action = "Bot stellt Rückfragen zu Erfahrung, Verfügbarkeit und Gehaltswunsch."

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
        "availability": extract_match(answers, r"(sofort|ab\s+\d{1,2}\.\d{1,2}\.\d{2,4}|verfügbar|verfügbar)"),
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
        "Kannst du mir kurz deine Erfahrung, Verfügbarkeit, Gehaltswunsch "
        "und vorhandene Dokumente nennen?"
    )


def main():
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), RecruitingHandler)
    print(f"RecruitOS läuft auf {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
