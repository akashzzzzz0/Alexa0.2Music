"""Alexa Own AI: low-memory multilingual conversational HTTP service.

The service combines deterministic local intents, contextual dialogue rules,
SQLite conversation history, and optional hosted/self-hosted LLM inference.
"""

import ast
import datetime as dt
import hmac
import json
import math
import os
import re
import sqlite3
import sys
import threading
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Resolve the service directory explicitly so the dialogue module is found even
# when the platform launches this file with a different working directory.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

try:
    from .conversation_brain import respond as conversation_respond
except ImportError:  # support direct execution: python app.py
    from conversation_brain import respond as conversation_respond

try:
    from .model_runtime import generate as local_model_generate, status as model_runtime_status
except ImportError:
    from model_runtime import generate as local_model_generate, status as model_runtime_status

try:
    from .context_envelope import normalize_context
    from .document_retrieval import retrieve_document_context
except ImportError:
    from context_envelope import normalize_context
    from document_retrieval import retrieve_document_context

try:
    from .feedback_learning import record_feedback, feedback_guidance
    from .response_decision import decide as decide_response
except ImportError:
    from feedback_learning import record_feedback, feedback_guidance
    from response_decision import decide as decide_response

PORT = int(os.getenv("PORT", "3000"))
API_TOKEN = os.getenv("ALEXA_AI_TOKEN", "")
DB_PATH = os.getenv("ALEXA_AI_DB_PATH", "alexa_memory.sqlite3")
MAX_BODY = 32_000
MAX_HISTORY = 20
MAX_MEMORY_ITEMS = 40
MAX_MEMORY_KEY_CHARS = 80
MAX_MEMORY_VALUE_CHARS = 800
INDIA_TZ = ZoneInfo("Asia/Kolkata")
DB_LOCK = threading.RLock()

# Approximate transliteration for common Urdu and Hindi chat vocabulary.
URDU = {
"ا":"a","آ":"aa","ب":"b","پ":"p","ت":"t","ٹ":"t","ث":"s","ج":"j","چ":"ch","ح":"h","خ":"kh","د":"d","ڈ":"d","ذ":"z","ر":"r","ڑ":"r","ز":"z","ژ":"zh","س":"s","ش":"sh","ص":"s","ض":"z","ط":"t","ظ":"z","ع":"","غ":"gh","ف":"f","ق":"q","ک":"k","گ":"g","ل":"l","م":"m","ن":"n","ں":"n","و":"o","ؤ":"o","ہ":"h","ھ":"h","ۃ":"h","ء":"","ئ":"i","ی":"i","ي":"i","ك":"k","ى":"a","ے":"e","َ":"a","ِ":"i","ُ":"u","ّ":"","ً":"an","ٍ":"in","ٌ":"un","ٓ":""
}
DEV = {
"अ":"a","आ":"aa","इ":"i","ई":"ee","उ":"u","ऊ":"oo","ऋ":"ri","ए":"e","ऐ":"ai","ओ":"o","औ":"au",
"क":"k","ख":"kh","ग":"g","घ":"gh","ङ":"n","च":"ch","छ":"chh","ज":"j","झ":"jh","ञ":"n",
"ट":"t","ठ":"th","ड":"d","ढ":"dh","ण":"n","त":"t","थ":"th","द":"d","ध":"dh","न":"n",
"प":"p","फ":"ph","ब":"b","भ":"bh","म":"m","य":"y","र":"r","ल":"l","व":"v","श":"sh","ष":"sh","स":"s","ह":"h",
"क्ष":"ksh","त्र":"tr","ज्ञ":"gy","ड़":"r","ढ़":"rh","ँ":"n","ं":"n","ः":"h","़":"",
"ा":"a","ि":"i","ी":"ee","ु":"u","ू":"oo","ृ":"ri","े":"e","ै":"ai","ो":"o","ौ":"au","्":"","़":""
}
DEV_CONS = set("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहड़ढ़")

def transliterate(text):
    out = []
    i = 0
    while i < len(text):
        pair = text[i:i+2]
        if pair in DEV:
            out.append(DEV[pair]); i += 2; continue
        ch = text[i]
        if ch in DEV:
            # Inherent 'a' after a consonant unless a vowel sign or virama follows.
            val = DEV[ch]
            if ch in DEV_CONS:
                nxt = text[i+1:i+2]
                if nxt not in ("्","ा","ि","ी","ु","ू","ृ","े","ै","ो","ौ"):
                    val += "a"
            out.append(val)
        elif ch in URDU:
            out.append(URDU[ch])
        else:
            out.append(ch)
        i += 1
    return "".join(out)

def normalize(value):
    value = transliterate(str(value or "").strip().lower())
    value = value.replace("’", "'").replace("‘", "'").replace("،", " ")
    value = re.sub(r"[^\w\s+*/().%\-]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()

def script_of(value):
    s = str(value or "")
    if any("\u0900" <= c <= "\u097f" for c in s):
        return "hi"
    if any("\u0600" <= c <= "\u06ff" for c in s):
        return "ur"
    return "roman"

def detect_language(raw):
    script = script_of(raw)
    if script == "hi":
        return "hi"
    if script == "ur":
        return "ur"
    t = normalize(raw)
    # Choose the dominant language in mixed Latin-script messages instead of
    # letting one English keyword override an otherwise Roman Urdu sentence.
    tokens = set(re.findall(r"[a-z']+", t))
    english_markers = {
        "the", "is", "you", "your", "what", "why", "how", "hello", "hey",
        "please", "thanks", "thank", "can", "will", "would", "should",
        "this", "that", "i", "we", "they", "where", "when", "who", "doing",
        "good", "morning", "evening", "today", "tomorrow", "because", "about",
        "with", "from", "for", "my", "did", "have", "has", "had", "am", "was",
        "were", "it", "to", "of", "on", "in", "at", "and", "or", "but", "not",
        "just", "tell", "say", "something", "there", "here", "yes", "yeah",
        "yep", "yup", "no", "nope", "ok", "okay",
    }
    roman_urdu_markers = {
        "main", "mai", "mujhe", "mera", "meri", "mere", "tum", "tumhe",
        "tumhein", "aap", "apko", "apka", "kya", "kyun", "kyu", "kaise",
        "kaisa", "kaisi", "kab", "kahan", "kidhar", "kon", "kaun", "hai",
        "hain", "ho", "haan", "han", "nahi", "nahin", "nhi", "acha",
        "achha", "theek", "thik", "aur", "lekin", "magar", "batao", "btao",
        "samjhao", "samjha", "kar", "karo", "kro", "chahiye", "chaiye",
        "dila", "doon", "karo", "raha", "rahi", "rahe", "tha", "thi",
        "wala", "wali", "wale", "ka", "ki", "ke", "ko", "se", "mein",
        "me", "par", "abhi", "aaj", "kal", "kyunke", "kyunki",
    }
    english_score = len(tokens & english_markers)
    roman_urdu_score = len(tokens & roman_urdu_markers)
    if roman_urdu_score and roman_urdu_score >= english_score:
        return "ur"
    if english_score:
        return "en"
    return "ur"

REPLIES = {
"en": {
"hello":"Hey! How's it going? What's up?",
"how":"I'm doing well! How are you?",
"thanks":"You're welcome! Happy to help.",
"identity":"I'm Alexa, your friendly assistant. What can I help you with?",
"bored":"Let's make this interesting. Want a joke, a fun fact, or just a chat?",
"sad":"Sorry things feel rough. Want to tell me what's going on?",
"happy":"That's great news! What happened?",
"joke":"Why did the computer go to the doctor? It caught a virus. 😄",
"bye":"See you later! Take care.",
"yes":"Alright! Tell me a little more.",
"no":"No worries. What would you rather talk about?",
"doing":"Just here chatting with you. What are you up to?",
"where":"I am right here in this chat. What is up?",
"whatsup":"Not much, just chatting with you. How about you?",
"unknown":"I'm listening. Could you rephrase that or add a little context so I can understand exactly?"
},
"ur": {
"hello":"Assalam o alaikum! Kya haal hain? Aaj kya scene hai?",
"how":"Main theek hoon! Aap sunao, sab kaisa chal raha hai?",
"thanks":"Koi baat nahi! Khushi hui help karke.",
"identity":"Main Alexa hoon, aapki friendly assistant. Batao, kis cheez mein help chahiye?",
"bored":"Chalo kuch interesting baat karte hain! Joke sunna hai ya koi mazedar fact?",
"sad":"Oh, sun kar afsos hua. Agar batana chaho to kya hua? Main sun rahi hoon.",
"happy":"Wah, yeh to achi baat hai! Kya khushkhabri hai?",
"joke":"Teacher: Homework kahan hai? Student: Sir, cloud mein save kiya tha, badal aa gaye! 😄",
"bye":"Allah hafiz! Phir baat hoti hai. Apna khayal rakhna!",
"yes":"Achha ji! Thora aur batao, phir main behtar samajh sakungi.",
"no":"Theek hai, koi masla nahi. Phir kis bare mein baat karein?",
"doing":"Bas yahin tumse baat kar rahi hoon. Tum sunao?",
"where":"Yahin chat mein hoon. Batao, kya scene hai?",
"whatsup":"Bas tumse baat ho rahi hai. Tum sunao, kya haal hai?",
"unknown":"Haan, main sun rahi hoon. Thora aur context de do taake main sahi jawab de sakun."
},
"hi": {
"hello":"Arey hello! Kaise ho? Aaj kya chal raha hai?",
"how":"Main badhiya hoon! Tum batao, sab kaisa chal raha hai?",
"thanks":"Koi baat nahi! Help karke achha laga.",
"identity":"Main Alexa hoon, tumhari friendly assistant. Batao, kya help chahiye?",
"bored":"Chalo kuch mazedaar karte hain! Joke sunoge ya koi interesting fact?",
"sad":"Ye sunkar bura laga. Agar batana chaho to kya hua? Main sun rahi hoon.",
"happy":"Arey wah, ye to bahut achhi baat hai! Kya good news hai?",
"joke":"Teacher: Homework kahan hai? Student: Sir, Google Drive mein tha, internet chala gaya! 😄",
"bye":"Phir milte hain! Apna khayal rakhna.",
"yes":"Achha! Thoda aur batao, main samajhne ki koshish karti hoon.",
"no":"Koi baat nahi. Phir kis baare mein baat karein?",
"doing":"Bas tumse baat kar rahi hoon. Tum kya kar rahe ho?",
"where":"Yahin chat mein hoon. Tum kahan ho?",
"whatsup":"Bas yahin hoon! Tum batao, kya chal raha hai?",
"unknown":"Haan, main sun rahi hoon. Thoda aur context do taake main sahi jawab de sakun."
},
"pa": {
"hello":"Oye hoye! Ki haal aa? Sab changa?",
"how":"Main vadiya haan ji! Tussi sunao, ki haal chaal ne?",
"thanks":"Koi gall nahi veere! Help karke changa laggeya.",
"identity":"Main Alexa haan ji! Dassyo, tuhadi ki help karaan?",
"bored":"Oye bore kyun ho rahe o? Koi joke sunna ya gallan maariye?",
"sad":"Aah, eh sun ke changa nahi laggeya. Je dil kare taan dasso ki hoya, main sun rahi haan.",
"happy":"O balle balle! Eh taan vadiya khabar aa. Ki hoya ji?",
"joke":"Master ji: Homework kithe aa? Student: Sir, cloud te si, ajj badal chhaye hoye ne! 😄",
"bye":"Changa fer! Apna khayal rakhyo, fer gall karde aan.",
"yes":"Haanji, dasso fer! Hor thoda samjhao.",
"no":"Chalo koi gall nahi ji. Hor ki gall kariye?",
"doing":"Bas tuhade naal gallan kar rahi haan ji. Tussi dasso?",
"where":"Ethe chat vich hi haan ji. Tussi kithe o?",
"whatsup":"Bas gallan-baatan chal rahi aan. Tussi sunao, ki haal aa?",
"unknown":"Haanji, main sun rahi aan. Gall thodi hor samjha deo taake main sahi jawab de sakaan."
}
}

def india_now():
    """Return the current aware datetime in India Standard Time."""
    return dt.datetime.now(INDIA_TZ)


def safe_math(expression):
    expression = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
    if not re.fullmatch(r"[0-9\s.+\-*/()%]*", expression):
        return None
    try:
        node = ast.parse(expression, mode="eval")
        def calc(n):
            if isinstance(n, ast.Expression): return calc(n.body)
            if isinstance(n, ast.Constant) and type(n.value) in (int, float): return n.value
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
                v = calc(n.operand); return v if isinstance(n.op, ast.UAdd) else -v
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
                a, b = calc(n.left), calc(n.right)
                if isinstance(n.op, ast.Add): v = a+b
                elif isinstance(n.op, ast.Sub): v = a-b
                elif isinstance(n.op, ast.Mult): v = a*b
                elif isinstance(n.op, ast.Div): v = a/b
                elif isinstance(n.op, ast.FloorDiv): v = a//b
                elif isinstance(n.op, ast.Mod): v = a%b
                else:
                    if abs(b) > 8: raise ValueError()
                    v = a**b
                if abs(v) > 10**15: raise ValueError()
                return v
            raise ValueError()
        result = calc(node)
        if not math.isfinite(float(result)): return None
        return int(result) if int(result) == result else round(result, 6)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None

def memory_connection():
    conn = sqlite3.connect(DB_PATH, timeout=8)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("CREATE TABLE IF NOT EXISTS turns (conversation TEXT NOT NULL, seq INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_turns_conversation_seq ON turns(conversation, seq)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS memory_items ("
        "scope TEXT NOT NULL, memory_key TEXT NOT NULL, memory_value TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, PRIMARY KEY(scope, memory_key))"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_scope_updated ON memory_items(scope, updated_at)")
    return conn


def _memory_scope(value):
    return str(value or "").strip()[:256]


def save_memory_items(scope, updates=None, forget_keys=None, forget_all=False):
    """Persist only explicit, caller-approved scalar memory updates."""
    scope = _memory_scope(scope)
    if not scope:
        return {"saved": 0, "deleted": 0}
    updates = updates if isinstance(updates, dict) else {}
    forget_keys = forget_keys if isinstance(forget_keys, list) else []
    saved = deleted = 0
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    blocked = {"password", "token", "secret", "api_key", "apikey", "authorization"}
    with DB_LOCK:
        with memory_connection() as conn:
            if forget_all:
                cur = conn.execute("DELETE FROM memory_items WHERE scope=?", (scope,))
                deleted += cur.rowcount
            else:
                for raw_key in forget_keys[:MAX_MEMORY_ITEMS]:
                    key = str(raw_key or "").strip()[:MAX_MEMORY_KEY_CHARS]
                    if key:
                        cur = conn.execute("DELETE FROM memory_items WHERE scope=? AND memory_key=?", (scope, key))
                        deleted += max(cur.rowcount, 0)
            for raw_key, raw_value in list(updates.items())[:MAX_MEMORY_ITEMS]:
                key = str(raw_key or "").strip()[:MAX_MEMORY_KEY_CHARS]
                if not key or key.casefold() in blocked:
                    continue
                if not isinstance(raw_value, (str, int, float, bool)):
                    continue
                value = str(raw_value).strip()[:MAX_MEMORY_VALUE_CHARS]
                if not value:
                    continue
                conn.execute(
                    "INSERT INTO memory_items(scope, memory_key, memory_value, updated_at) "
                    "VALUES(?,?,?,?) ON CONFLICT(scope, memory_key) DO UPDATE SET "
                    "memory_value=excluded.memory_value, updated_at=excluded.updated_at",
                    (scope, key, value, now),
                )
                saved += 1
            conn.execute(
                "DELETE FROM memory_items WHERE scope=? AND memory_key NOT IN "
                "(SELECT memory_key FROM memory_items WHERE scope=? ORDER BY updated_at DESC LIMIT ?)",
                (scope, scope, MAX_MEMORY_ITEMS),
            )
    return {"saved": saved, "deleted": deleted}


def get_memory_items(scope):
    scope = _memory_scope(scope)
    if not scope:
        return {}
    with DB_LOCK:
        with memory_connection() as conn:
            rows = conn.execute(
                "SELECT memory_key, memory_value FROM memory_items WHERE scope=? "
                "ORDER BY updated_at DESC LIMIT ?",
                (scope, MAX_MEMORY_ITEMS),
            ).fetchall()
    return {key: value for key, value in rows}


def _extract_explicit_user_name(message):
    """Extract a plainly stated first name; never infer a name from other text."""
    match = re.search(
        r"\b(?:mera|meri|my)\s+(?:naam|name)\s+"
        r"([a-z][a-z0-9_-]{1,30})"
        r"(?:\s+(?:hai|ha|is))?(?:\s+(?:yaad|remember)\b.*)?[.! ]*$",
        str(message or "").strip(),
        re.IGNORECASE,
    )
    if not match:
        return None
    name = match.group(1).strip()
    if name.casefold() in {"kya", "what", "hai", "ha", "is", "nahi", "nahin", "name", "naam"}:
        return None
    return name[:60]


def _is_alexa_identity_question(text):
    """Recognize direct questions about Alexa's name or purpose in Roman Urdu/English."""
    value = normalize(text)
    asks_name = bool(re.search(
        r"\b(?:tumhara|tumhari|aapka|apka|your|what is your)\s+(?:naam|name)\b|"
        r"\b(?:tumhara|tumhari|aapka|apka)\s+name\s+kya\b",
        value,
    ))
    asks_role = bool(re.search(
        r"\b(?:tumhara|tumhari|aapka|apka|your)\s+(?:kaam|work|job|purpose)\b|"
        r"\b(?:tumhara|aapka)\s+kaam\s+kya\b",
        value,
    ))
    return asks_name or asks_role


def request_context(body, default_scope, message=""):
    """Combine approved memory, explicit feedback, request facts, and retrieved document excerpts."""
    # Personal long-term memory must not default to a shared group/chat ID.
    # Prefer an explicit scope; otherwise isolate by the sending user when known.
    explicit_scope = body.get("memory_scope")
    user_identity = body.get("user_id") or body.get("from_user_id")
    if explicit_scope:
        scope = _memory_scope(explicit_scope)
    elif user_identity is not None and str(user_identity).strip():
        scope = _memory_scope("user:" + str(user_identity).strip())
    else:
        scope = _memory_scope(default_scope)
    memory_updates = body.get("memory_updates")
    memory_updates = dict(memory_updates) if isinstance(memory_updates, dict) else {}
    stated_name = _extract_explicit_user_name(message)
    if stated_name:
        memory_updates["name"] = stated_name
    memory_result = save_memory_items(
        scope,
        updates=memory_updates,
        forget_keys=body.get("forget_memory_keys"),
        forget_all=body.get("forget_all_memory") is True,
    )
    memory_result["feedback_recorded"] = record_feedback(
        DB_PATH, scope, body.get("feedback")
    )
    saved = get_memory_items(scope)
    request_memory = body.get("memory_context")
    memory_payload = {}
    if saved:
        memory_payload["saved_memory"] = saved
    if isinstance(request_memory, (dict, list, tuple)) and request_memory:
        memory_payload["request_memory"] = request_memory
    elif isinstance(request_memory, str) and request_memory.strip():
        memory_payload["request_memory"] = request_memory.strip()[:MAX_MEMORY_VALUE_CHARS]
    document_context = retrieve_document_context(message, body.get("documents"))
    if document_context:
        memory_payload["attached_document_excerpts"] = document_context
    guidance = feedback_guidance(DB_PATH, scope)
    if guidance:
        memory_payload["explicit_feedback_guidance"] = guidance
    if not memory_payload:
        memory_payload = request_memory
    context = normalize_context(
        body.get("context"), memory_payload, body.get("media_context")
    )
    return context, memory_result, len(saved)


def response_decision(message, body):
    """Return a conservative action recommendation for the calling chat app."""
    decision_context = body.get("decision_context")
    return decide_response(message, decision_context)


def get_history(conversation, supplied, current_message=""):
    supplied_messages = [x for x in supplied if isinstance(x, dict)]
    if supplied_messages and supplied_messages[-1].get("role") == "user" and str(supplied_messages[-1].get("content", "")) == str(current_message):
        supplied_messages = supplied_messages[:-1]
    if conversation:
        with DB_LOCK:
            with memory_connection() as conn:
                rows = conn.execute("SELECT role, content FROM turns WHERE conversation=? ORDER BY seq DESC LIMIT ?", (conversation, MAX_HISTORY)).fetchall()
        if rows:
            return [{"role": role, "content": content} for role, content in reversed(rows)]
    # The bot caller also has its own persistent five-message history. Use it
    # when the microservice database is new or was reset during a redeploy.
    return supplied_messages[-MAX_HISTORY:]

def save_turns(conversation, user_text, reply):
    if not conversation:
        return
    with DB_LOCK:
        with memory_connection() as conn:
            conn.execute("INSERT INTO turns(conversation, role, content, created_at) VALUES(?,?,?,?)", (conversation, "user", user_text[:4000], dt.datetime.now(dt.timezone.utc).isoformat()))
            conn.execute("INSERT INTO turns(conversation, role, content, created_at) VALUES(?,?,?,?)", (conversation, "assistant", reply[:4000], dt.datetime.now(dt.timezone.utc).isoformat()))
            conn.execute("DELETE FROM turns WHERE conversation=? AND seq NOT IN (SELECT seq FROM turns WHERE conversation=? ORDER BY seq DESC LIMIT ?)", (conversation, conversation, MAX_HISTORY))

def _is_compound_message(text):
    """Detect multi-clause chat that must not be swallowed by a single-intent fallback."""
    parts = re.split(r"\b(?:aur|and|but|lekin|magar|also)\b", str(text or ""), flags=re.IGNORECASE)
    meaningful_parts = [part for part in parts if len(part.split()) >= 3]
    if len(meaningful_parts) < 2:
        return False
    # Keep expressions for the exact local calculator on their existing path.
    return not re.search(r"\d\s*[+*/%\-]\s*\d", str(text or ""))


def _is_name_question(text):
    return bool(re.fullmatch(
        r"\s*(?:(?:mera|meri|my)\s+(?:naam|name)\s+(?:kya|what)(?:\s+(?:hai|ha|is))?|"
        r"(?:what is|whats)\s+my\s+(?:name|naam))\s*[?.!]*",
        str(text or "").casefold(),
    ))

def _known_user_name(history, context=None):
    """Return a name only when it was explicitly supplied in recent turns or memory."""
    if isinstance(context, dict):
        memory = context.get("relevant_memory", {})
        if isinstance(memory, dict):
            for section in (memory.get("saved_memory"), memory.get("request_memory")):
                if isinstance(section, dict):
                    for key in ("name", "user_name", "preferred_name"):
                        value = section.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()[:60]
    declaration = re.compile(
        r"\b(?:mera|meri|my)\s+(?:naam|name)\s+(?:hai|is|:)?\s*"
        r"([a-z][a-z0-9_-]{1,30})\b",
        re.IGNORECASE,
    )
    excluded = {"kya", "what", "hai", "is", "nahi", "nahin", "kya", "name", "naam"}
    for item in reversed(history or []):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        match = declaration.search(str(item.get("content", "")))
        if match and match.group(1).casefold() not in excluded:
            return match.group(1)
    return None


def _is_substantive_question(text):
    """Route real questions and multi-question turns to inference before canned intents."""
    value = str(text or "").strip()
    if not value:
        return False
    # Preserve deterministic handling for the most common tiny social exchanges.
    if re.fullmatch(
        r"(?:hi+|hello|hey+|salam|assalam(?: o alaikum)?|good morning|good afternoon|good evening|"
        r"how are you|how r u|kaise ho|kaisay ho|kese ho|kya haal hai|time kya hai|aaj date kya hai)[!. ]*",
        value,
        re.IGNORECASE,
    ):
        return False
    question_cues = re.compile(
        r"\b(what|why|when|where|who|which|how|can|could|would|is|are|do|does|did|"
        r"kya|kyun|kyu|kaise|kaisa|kaisi|kab|kahan|kidhar|kon|kaun|kitna|kitni|"
        r"batao|btao|samjhao|mtlb|matlab)\b",
        re.IGNORECASE,
    )
    if "?" in value or "؟" in value:
        return True
    # Longer natural-language turns usually carry context, emotion, or multiple clauses.
    if len(re.findall(r"\w+", value)) >= 6:
        return True
    if len(re.findall(r"\b(?:1[.)]|2[.)]|3[.)]|4[.)]|5[.)])\s+", value)) >= 2:
        return True
    return bool(question_cues.search(value))


def response_for(message, history, context=None):
    raw = str(message or "").strip()
    lang = detect_language(raw)
    t = normalize(raw)
    r = REPLIES[lang]
    model_attempted = False

    # The local conversation brain handles clear dialogue intents first.
    # Open-ended messages continue through deterministic app intents and then
    # exactly one model-runtime call below, with the supplied context.
    if not raw:
        return r["hello"]

    # Confirm a plainly stated name after request_context has persisted it.
    stated_name = _extract_explicit_user_name(raw)
    if stated_name:
        return ("Got it, I'll remember your name is " + stated_name + "."
                if lang == "en" else "Theek hai, " + stated_name + " naam yaad rakhungi.")

    # Answer direct questions about Alexa herself without depending on an LLM.
    if _is_name_question(t):
        known_name = _known_user_name(history, context=context)
        if known_name:
            return ("Your name is " if lang == "en" else "Tumhara naam ") + known_name + "."
        return "Tumne abhi tak apna naam nahi bataya. Bata do, phir main sahi naam yaad rakh sakungi."

    if (_is_alexa_identity_question(t)
            and not _is_compound_message(t)
            and len(re.findall(r"\\b\\d+[.)]\\s+", t)) < 2
            and t.count("?") <= 1):
        if lang == "en":
            return "My name is Alexa. I'm your assistant, and my job is to understand your messages and help with questions, conversation, and tasks."
        return "Mera naam Alexa hai. Main tumhari assistant hoon. Mera kaam tumhari baat samajhna, sawalon ke jawab dena aur zaroori kaamon mein madad karna hai."

    # Keep emoji-only input intact for contextual dialogue matching; normalize()
    # intentionally strips symbols for word-based intent rules.
    if context is None:
        brain_reply = conversation_respond(raw, t or raw, lang, history)
    else:
        brain_reply = conversation_respond(raw, t or raw, lang, history, context=context)
    if brain_reply:
        return brain_reply

    # Give substantive questions first chance at contextual model inference.
    # This prevents keyword-based canned replies (e.g. 'happy', 'leaderboard')
    # from swallowing the actual question before the model can read its context.
    if _is_substantive_question(t):
        model_attempted = True
        question_reply = local_model_generate(raw, history, context=context)
        if question_reply:
            return question_reply

    # Compound messages must reach the model intact before a one-intent
    # keyword fallback can answer only one clause and silently drop the rest.
    if _is_compound_message(t):
        model_attempted = True
        compound_reply = local_model_generate(raw, history, context=context)
        if compound_reply:
            return compound_reply

    # Deterministic intent and short-follow-up rules run before paid/remote inference.

    # Natural Roman Hindi/Urdu small talk and conversational repair.
    if re.search(r"\b(sab theek|sab thik|sab thek)\b", t) and re.search(r"\b(kahan thi|kha th+i+|kaha thi|kidhar thi|tum thi|tum ho)\b", t):
        return "Haan, sab theek chal raha hai. Main yahin thi, tum sunao? Kya chal raha hai?"
    if re.search(r"\b(kis|kaun se|kon se)\b", t) and re.search(r"\b(alfaz|lafz|ilfaz|words|tarah)\b", t) and re.search(r"\b(samj|samajh|samjhe|samjha)\w*\b", t):
        prior = " ".join(normalize(x.get("content", "")) for x in history[-MAX_HISTORY:] if isinstance(x, dict))
        if any(word in prior for word in ("rephrase", "doosre alfaaz", "apne words", "context", "samajh")):
            return "Arey, meri galti! Tumne bilkul theek kaha tha. Tumhari pehli baat samajh aa gayi thi—mujhe dobara poochna nahi chahiye tha."
        return "Mera matlab hai, jis tarah tum normally baat karte ho usi tarah batao. Main samajhne ki koshish karungi."
    if re.fullmatch(r"(are+ yaar|aray yaar|oye yaar|uff yaar|yaar)[!. ]*", t):
        return "Arey kya hua? Meri baat se confusion hua kya? Batao, main dhyan se samajhti hoon."
    # Common speech-to-text and casual Roman Urdu spellings for "speak / go ahead".
    if re.fullmatch(r"(?:bool|bol|bo+l+)\s*(?:ly+|le|na|do)?", t) or t in {"bolo", "bolo na", "bol na", "bolly", "bollyy", "suno", "sun na", "sunn"}:
        if lang == "en":
            return "I'm listening. Go ahead—what did you want to say?"
        if lang == "pa":
            return "Haanji, dasso! Main sun rahi aan."
        return "Haan ji, bolo! Main sun rahi hoon."
    # A greeting plus Alexa's name or a casual call should be treated as a direct greeting.
    if re.search(r"\balexa\b", t) and re.search(r"\b(oye|oy+|hello|hi|hey|baby)\b", t):
        if lang == "en":
            return "Hey! I'm here. What's up?"
        return "Oyyyy! Haan bolo, sun rahi hoon."
    if re.search(r"\b(suno|sun na|listen|listen up)\b", t):
        if lang == "en":
            return "I'm listening. What's up?"
        return "Haan ji, sun rahi hoon. Bolo?"
    if any(mark in raw for mark in ("السلام علیکم", "السلام عليكم", "السلامعلیکم", "سلام", "नमस्ते", "नमस्कार", "हैलो")):
        return r["hello"]
    if any(mark in raw for mark in ("آپ کیسے ہیں", "آپ کیسے ہو", "آپ کا حال")):
        return r["how"]
    math_text = re.sub(r"^(what is|calculate|solve|kitna hota hai|batao|btao|iska jawab)\s+", "", t)
    if re.search(r"\d\s*[+*/%\-]\s*\d", math_text) or re.search(r"\d\s*[×÷^]\s*\d", raw):
        value = safe_math(math_text if math_text != t else raw)
        if value is not None:
            if lang == "en": return "The answer is " + str(value) + "."
            if lang == "hi": return "Iska jawab " + str(value) + " hai."
            if lang == "pa": return "Isda jawab " + str(value) + " aa."
            return "Iska jawab " + str(value) + " hai."
    if re.search(r"\b(good morning|subah|subha|morning)\b", t):
        return "Good morning! Aaj ka din kaisa ja raha hai?" if lang != "en" else "Good morning! How's your day going?"
    if re.search(r"\b(hello|hi|hii+|hey|heyy+|salam|salaam|assalam|aslam|namaste|namaskar|hailo|aoa|sat sri akal|satsriakal|ki haal)\b", t):
        return r["hello"]
    if re.search(r"\b(how are you|how r u|kaise ho|kaise hain|kaisay ho|kese ho|kese hain|kya haal|ki haal|kida|kidda|ap kise hin|aap kaise hain)\b", t):
        return r["how"]
    if re.search(r"\b(what are you doing|what r u doing|kya kar rahe|kya kar rahi|ki kar rahe|ki kar rahi|ki karna|ki kardi|ki karde|tussi ki karde|tussi ki kar rahe)\b", t):
        return r["doing"]
    if re.search(r"\b(where are you|where r u|kahan ho|kidhar ho|tussi kithe|kithe o)\b", t):
        return r["where"]
    if re.search(r"\b(what is up|whats up|what's up|kya chal raha|ki haal chaal|ki haal aa)\b", t):
        return r["whatsup"]
    if re.search(r"\b(thank you|thanks|shukriya|bohat shukriya|meharbani|dhanvaad|dhanyavaad)\b", t):
        return r["thanks"]
    if re.search(r"\b(who are you|tum kon ho|tum kaun ho|aap kon|your name|naam kya|tu kaun)\b", t):
        return r["identity"]
    if re.search(r"\b(bored|boring|bore ho|pak gaya|pak gayi|vehla|vela)\b", t):
        return r["bored"]
    if re.search(r"\b(sad|udaas|pareshan|tension|mood off|dukhi|dil udaas)\b", t):
        return r["sad"]
    if re.search(r"\b(happy|khush|khushi|great news|vadiya khabar|changa hoya)\b", t):
        return r["happy"]
    if re.search(r"\b(joke|jokes|mazaak|mazak|chutkula|latifa|hasao|laugh)\b", t):
        return r["joke"]
    if re.search(r"\b(bye|goodbye|allah hafiz|khuda hafiz|see you|fer milange|chal bye)\b", t):
        return r["bye"]
    if re.fullmatch(r"(yes|yeah|yup|haan|han|ji|achha|acha|theek|ok|okay|bilkul|haaji)[!. ]*", t):
        prior = " ".join(normalize(x.get("content", "")) for x in history[-MAX_HISTORY:] if isinstance(x, dict))
        if "joke" in prior or "mazak" in prior:
            return r["joke"]
        if not history:
            return r["yes"]
        # An affirmative with conversation history answers the previous turn.
        # Let the model resolve what was agreed to instead of returning a
        # context-free "tell me more" line.
    if re.fullmatch(r"(no|nahi|nahin|na|nope)[!. ]*", t) and not history:
        return r["no"]
    if re.search(r"\b(time kya|abhi time|abhi kitne? baje|kitna time|what time|current time|time now|waqt kya|abhi waqt|samay kya|kinna time)\b", t):
        now = india_now().strftime("%I:%M %p IST")
        return ("It is " if lang == "en" else "Hun time " if lang == "pa" else "Abhi time ") + now + "."
    if re.search(r"\b(today date|date today|aaj date|aaj ki date|date kya|what date|what is the date|today.s date|aaj ki tareekh|ajj di tareekh|tareekh kya|aaj ka din|which day is it|what day is it)\b", t):
        today = india_now().strftime("%A, %d %B %Y")
        return ("Today's date is " if lang == "en" else "Ajj di tareekh " if lang == "pa" else "Aaj ki tareekh ") + today + "."
    # Short conversational turns need context-sensitive replies, not the same
    # generic clarification on every message.
    words = set(t.split())
    if t in {"baby", "babu", "babyy", "oye baby", "oy baby", "hmm", "hmmm"}:
        if lang == "en":
            return "Hey, I'm here. What did you want to tell me?"
        if lang == "pa":
            return "Oye, dasso ji! Ki gall karni aa?"
        return "Haan bolo, kya baat hai?"
    if re.search(r"\b(axha|acha|achha|accha)\b", t) and re.search(r"\b(kya du|kia du|kya doon|kia doon|kya btaun|kya bataun|kya bolun)\b", t):
        if lang == "en":
            return "Just tell me what's on your mind. I'm listening."
        if lang == "pa":
            return "Jo dil vich aa, dass deo ji. Main sun rahi aan."
        return "Jo dil mein hai woh bata do, main sun rahi hoon."
    if t in {"hain", "hein", "han", "huh", "what", "kya", "kyaa", "acha", "achha", "axha"} or t.endswith("?") and len(t.split()) <= 2:
        previous_assistant = next((normalize(x.get("content", "")) for x in reversed(history) if isinstance(x, dict) and x.get("role") == "assistant"), "")
        if any(token in previous_assistant for token in ("context", "samajh", "listening", "batao", "tell me")):
            if lang == "en":
                return "I mean, you can talk to me normally. What's going on?"
            if lang == "pa":
                return "Mera matlab, tussi aam gall karo ji. Ki hoya?"
            return "Mera matlab, tum mujhse normal baat kar sakte ho. Kya chal raha hai?"
        if lang == "en":
            return "What happened? Tell me a little more."
        if lang == "pa":
            return "Ki hoya ji? Thoda hor dasso."
        return "Kya hua? Thoda aur batao na."
    # Contextual follow-up: resolve short replies against the previous turn.
    if history:
        last_user = next((normalize(x.get("content", "")) for x in reversed(history) if isinstance(x, dict) and x.get("role") == "user"), "")
        previous_assistant = next((normalize(x.get("content", "")) for x in reversed(history) if isinstance(x, dict) and x.get("role") == "assistant"), "")
    # All deterministic local intents have now been checked. Open-ended chat
    # gets exactly one bounded model attempt with the caller's context attached.
    model_reply = None if model_attempted else local_model_generate(raw, history, context=context)
    if model_reply:
        return model_reply

    # If inference is unavailable, use a concise language-matched fallback.
    if lang == "en":
        return "I'm listening. Tell me a little more about what you mean."
    if lang == "pa":
        return "Haanji, thoda hor dasso. Main samajh rahi aan."
    return "Haan, main sun rahi hoon. Aage batao?"

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return not API_TOKEN or hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + API_TOKEN)

    def do_GET(self):
        if self.path.split("?", 1)[0].rstrip("*") == "/health":
            model_status = model_runtime_status()
            return self.send_json(200, {"ok": True, "service": "alexa-own-ai-micro", "engine": "multilingual-context+llm" if model_status["is_llm"] else "multilingual-local-context", "is_llm": model_status["is_llm"], "model_provider": model_status["provider"], "model": model_status["model"], "languages": ["English", "Roman Urdu", "Roman Hindi", "Roman Punjabi", "Urdu script input", "Devanagari input"], "memory_mode": "sqlite_recent_20+scoped_long_term"})
        return self.send_json(200, {"service": "alexa-own-ai-micro", "endpoints": ["/health", "/chat", "/v1/chat/completions"]})

    def do_POST(self):
        if not self.authorized():
            return self.send_json(401, {"error": "unauthorized"})
        if self.path not in ("/chat", "/v1/chat/completions"):
            return self.send_json(404, {"error": "not_found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY:
                return self.send_json(413 if size > MAX_BODY else 400, {"error": "request_too_large" if size > MAX_BODY else "empty_body"})
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "invalid_json"})

        if self.path == "/chat":
            message = str(body.get("message", ""))
            supplied = body.get("history", [])
            if not isinstance(supplied, list): supplied = []
            conversation = str(body.get("conversation_id") or body.get("chat_id") or body.get("user_id") or body.get("session_id") or "").strip()
            context, memory_change, memory_items = request_context(body, conversation, message)
            history = get_history(conversation, supplied, message)
            decision = response_decision(message, body)
            # A group message that was not explicitly addressed must not
            # trigger inference or become a hidden assistant turn in history.
            reply = response_for(message, history, context=context) if decision["action"] == "reply" else ""
            if reply:
                save_turns(conversation, message, reply)
            model_status = model_runtime_status()
            return self.send_json(200, {"reply": reply, "fallback": False, "provider": model_status["provider"] or "alexa-own-ai-micro", "is_llm": model_status["is_llm"], "model": model_status["model"], "language": detect_language(message), "memory_messages": min(MAX_HISTORY, len(history)+2), "memory_items": memory_items, "memory_saved": memory_change["saved"], "memory_deleted": memory_change["deleted"], "feedback_recorded": memory_change["feedback_recorded"], "decision": decision})

        messages = body.get("messages", [])
        if not isinstance(messages, list): messages = []
        message = ""
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "user":
                content = item.get("content", "")
                message = content if isinstance(content, str) else ""
                break
        conversation = str(body.get("conversation_id") or body.get("chat_id") or body.get("user_id") or body.get("session_id") or "").strip()
        context, memory_change, memory_items = request_context(body, conversation, message)
        history = get_history(conversation, messages, message)
        decision = response_decision(message, body)
        # Silence and reaction decisions must not create assistant turns or
        # pollute the next conversation context.
        reply = (
            response_for(message, history, context=context) or REPLIES[detect_language(message)]["unknown"]
            if decision["action"] == "reply" else ""
        )
        if reply:
            save_turns(conversation, message, reply)
        return self.send_json(200, {
            "id": "alexa-own-ai-micro-v2", "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "x_alexa_memory": {"items": memory_items, "saved": memory_change["saved"], "deleted": memory_change["deleted"]},
            "x_alexa_feedback_recorded": memory_change["feedback_recorded"],
            "x_alexa_decision": decision
        })

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

if __name__ == "__main__":
    print("Alexa Own AI microservice listening on port", PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
