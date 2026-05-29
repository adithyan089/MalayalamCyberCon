"""
YouTube comment-thread scraper for the MalayalamCyberCon project.

Fetches top-level comments + reply threads from seed videos, filters for
Manglish content, flags likely conflict, anonymizes authors, and appends
results to data/raw_threads.jsonl.

Separates I/O (API calls, file writes) from pure logic so the logic layer
can be unit-tested without a network connection.
"""

import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# EDITABLE CONSTANTS — have a Malayalam speaker verify and expand both lists
# before relying on them for real filtering.
# ---------------------------------------------------------------------------

# Romanized-Malayalam function words / markers used to detect Manglish.
# TODO: have a native speaker verify and expand — this is a draft seed.
MANGLISH_MARKERS = [
    # Copula / existential
    "aanu", "anu", "aane", "aayirunnu", "aan", "ayirunnu",
    # Negation
    "alla", "alle", "allallo", "illa", "ille", "illallo", "aalla", "aalle",
    # Existential / availability
    "und", "undo", "undu", "undayirunnu", "undallo",
    # Common verbs (romanized)
    "cheyyu", "cheyyum", "cheythu", "cheyyunnu", "cheyyan",
    "paranju", "parayum", "parayunnu", "parayathe", "parayanda",
    "nokku", "kandu", "vaa", "vanne", "vannу",
    "pokum", "poyi", "povo", "pokunnu", "pokkunnu", "poyitt",
    "varum", "varunnu", "varuna", "vann",
    "kodukkum", "kittum", "kittilla", "kittunilla", "kittiyilla",
    "irikkum", "irikkunnu", "irunnу",
    "ayidum", "aayidum", "aakum",
    # Pronouns / demonstratives
    "njan", "njangal", "nee", "ningal", "avan", "aval", "avar",
    "athu", "ithu", "ethu", "ente", "ninte", "avante", "avalude",
    "enne", "ninne", "avane", "avale",
    # Question words
    "enthu", "enth", "enthaa", "enthina", "enthokke", "enthellam",
    "engane", "evide", "evidunnu", "aaranu", "evideyaanu", "evidaanu",
    # Common particles / discourse markers
    "athe", "ath", "ith", "ingane", "angane",
    "ennu", "ennal", "enkil", "eppol", "eppozhum", "ippol", "ippo", "ippozha",
    "pinne", "pinneyo", "appol", "appozha", "annu",
    "thanne", "aayitt", "koode", "koodi",
    # Conjunctions / connectors
    "kond", "kondu", "konde", "okke", "aanallo", "allallo",
    # Informal address / terms
    "machane", "mache", "mach", "da", "di", "eda", "edi",
    "chetta", "chette", "chettan", "mol", "mole", "mwone", "mone",
    "maash", "maashe",
    # Common affirmatives / confirmations
    "sheriyaanu", "sheriyanu", "sheri", "shari", "adipoli", "pwoli", "poli",
    "venam", "venda", "veruthe",
    # Exclamations
    "ayyo", "ayyappa", "enthokke",
]

# ---------------------------------------------------------------------------
# Intensity-weighted conflict keyword dictionary.
# Scale: 1 = mild dismissiveness → 5 = direct violent threat / worst slur.
# This structure lets you later build per-thread intensity scores and convert
# the flag into an ordinal feature for the model.
#
# To add a word: pick the right intensity tier and add it to the dict.
# Multi-word phrases must come before their component words in iteration order
# (Python dicts preserve insertion order from 3.7+), but the scorer checks
# all entries so order only matters if you deduplicate matches — it doesn't
# here.
# ---------------------------------------------------------------------------
CONFLICT_KEYWORDS: dict[str, int] = {
    # -----------------------------------------------------------------------
    # Intensity 1 — Mild dismissiveness & weak conflict signals
    # Note: some entries below are noisy (appear in neutral contexts too);
    # treat intensity-1 hits as soft signals, not hard evidence.
    # -----------------------------------------------------------------------
    "poda": 1,              # get lost
    "podi": 1,              # feminine form of poda
    "പോടാ": 1,              # FIXED: Moved from Intensity 4 to match 'poda'
    "പോടി": 1,
    "poyi": 1,              # go away
    "avale": 1,             # dehumanising dismissal of a woman
    "avanokke": 1,          # dismissive "him and all"
    "onnu podappa": 1,      # aggressive wave-off
    "fight": 1,
    "get a life": 1,
    "mind your own business": 1,
    "mind your business": 1,
    "shameless": 1,
    "pathetic": 1,
    "toxic": 1,             # noisy English term — weak signal only
    "kashtam": 1,           # "pathetic/sad" — noisy, appears in neutral contexts too
    "kashtam thanne": 1,
    "കഷ്ടം": 1,
    "കഷ്ടം തന്നെ": 1,

    # -----------------------------------------------------------------------
    # Intensity 2 — Insults, mockery & internet bullying labels
    # -----------------------------------------------------------------------
    "mandan": 2,            # idiot/fool
    "മണ്ടൻ": 2,
    "pottan": 2,
    "potthan": 2,
    "പൊട്ടൻ": 2,
    "maramandan": 2,        # absolute blockhead
    "മരമണ്ടൻ": 2,
    "thendi": 2,
    "kalla": 2,             # liar/thief
    "kashta jivi": 2,       # pathetic creature
    "kuda koodi": 2,        # aggressive "pack your bags"
    "marathaval": 2,
    "buddhi illathavan": 2, # brainless person
    "vivaram illatha": 2,   # lacks common sense
    "mandrake": 2,          # internet slang — brings bad luck/ruin
    "pucham": 2,            # scorn
    "dont normalize": 2,
    "stop normalizing": 2,
    "who are you to judge": 2,
    "nee ethada": 2,        # "who the hell are you?" (male address)
    "nee ethadi": 2,        # "who the hell are you?" (female address)
    "upadesham": 2,         # unsolicited moral lecturing
    "upadeshi": 2,
    "ഉപദേശം": 2,
    "ഉപദേശി": 2,
    "nyayeekaranam": 2,     # chronic defending of the indefensible
    "nyayeekari": 2,
    "ന്യായീകരണം": 2,
    "avante oru": 2,        # dismissive "look at this guy..."
    "avalude oru": 2,
    "enittu venam": 2,      # sarcastic "and then you expect..."
    "prahasanam": 2,        # sarcastic "what a complete farce"
    "പ്രഹസനം": 2,
    "vivadam": 2,           # drama monger / attention seeker
    "alavalaathi": 2,
    "buddhijeevi": 2,       # sarcastic "intellectual"
    "kulasthree": 2,        # sarcastic traditionalist-woman label
    "കുലസ്ത്രീ": 2,
    "kulapurushan": 2,
    "കുലപുരുഷൻ": 2,
    "ammavan": 2,           # ageist internet mockery (uncle/aunt)
    "അമ്മാവൻ": 2,
    "ammayi": 2,
    "അമ്മായി": 2,
    "sadacharam": 2,        # moral policing
    "സദാചാരം": 2,
    "simpathy": 2,          # accusing creator of milking sympathy for clout
    "sympathy star": 2,
    "സിംപതി": 2,
    "സിമ്പതി തരംഗം": 2,
    "shooran": 2,           # sarcastic "overly brave"
    "viriyaan": 2,
    "show off": 2,
    "ഓരോരുത്തർ ഇറങ്ങിക്കോളും": 2,  # dismissive classist insult
    "വിവരമില്ലാത്തവൻ": 2,
    "ബുദ്ധിശൂന്യൻ": 2,
    "നീ ഏതാടാ": 2,
    "നീ ഏതാടി": 2,

    # -----------------------------------------------------------------------
    # Intensity 3 — Political hatred & targeted degradation
    # -----------------------------------------------------------------------
    "chanakam": 3,
    "ചാണകം": 3,
    "antham": 3,
    "anthammi": 3,
    "അന്തംമ്മി": 3,
    "capsule": 3,           # mocking scripted political defence
    "ക്യാപ്സൂൾ": 3,
    "kaavi": 3,
    "commie": 3,
    "vazha": 3,             # useless/dead weight — NOTE: also the film "Vazha"; expect some FPs
    "വാഴ": 3,
    "konthiri": 3,
    "mungiyamavan": 3,
    "nanamkettavan": 3,
    "നാണംകെട്ടവർ": 3,
    "changathi kalla": 3,   # backstabber
    "koothara": 3,
    "കൂത്തറ": 3,
    "verupikkal": 3,
    "വെറുപ്പിക്കൽ": 3,
    "chenna nattam": 3,     # disgusting presence / rotten stench
    "sadachara police": 3,
    "സദാചാര പോലീസ്": 3,
    "ന്യായീകരണ തൊഴിലാളി": 3,  # defending the indefensible (capsule worker)
    "വെളുപ്പിക്കൽ": 3,          # whitewashing (Malayalam script)

    # -----------------------------------------------------------------------
    # Intensity 4 — Severe slurs & sexual harassment
    # -----------------------------------------------------------------------
    "vedi": 4,
    "വെടി": 4,
    "വേടി": 4,
    "myre": 4,
    "maire": 4,
    "mypre": 4,
    "മൈര്": 4,
    "kuna": 4,              # vulgar genital insult (high-frequency in heated threads)
    "kunna": 4,
    "charakku": 4,
    "ചരക്ക്": 4,
    "naaye": 4,
    "panni": 4,
    "ammanaaye": 4,
    "pennu keri meeyunnu": 4,
    "nokki koluthe": 4,

    # -----------------------------------------------------------------------
    # Intensity 5 — Direct violent threats & worst maternal/sexual slurs
    # -----------------------------------------------------------------------
    # Maternal / Severe Sexual Slurs (Newly Expanded)
    "thayoli": 5,
    "തയോളി": 5,
    "ninte ammayude poor": 5,
    "നിന്റെ അമ്മയുടെ പൂറ്": 5,
    "ammayude poor": 5,
    "അമ്മയുടെ പൂറ്": 5,
    # "poor": 5  — REMOVED: matches English "poor boy/quality" causing false positives
    "പൂറ്": 5,  # Malayalam script form only — unambiguous
    
    # Threats and Mutilation
    "vishwasaghaathan": 5,
    "veettil keri thallum": 5,
    "വീട്ടിൽ കേറി തല്ലും": 5,
    "veettil kayari thallum": 5,        # variant: kayari vs keri
    "വീട്ടിൽ കയറി തല്ലും": 5,
    "kaalu vettum": 5,
    "കാൽ വെട്ടും": 5,
    "kaiyum kaalu vettum": 5,
    "കൈയും കാലും വെട്ടും": 5,
    "കൈകാൽ വെട്ടും": 5,
    "thalli kollum": 5,
    "thallikollum": 5,
    "തല്ലി കൊല്ലും": 5,
    "തല്ലിക്കൊല്ലും": 5,
    "tholichu kalayum": 5,
    "തോലിച്ചു കളയും": 5,
    "tholi urikkum": 5,
    "തൊലി ഉരിക്കും": 5,
    "തൊലിഉരിക്കും": 5,
    "kannu kuthipottikkum": 5,
    "കണ്ണ് കുത്തിപൊട്ടിക്കും": 5,
    "kandam vazhi odikkum": 5,
    "കണ്ടം വഴി ഓടിക്കും": 5,
    "കണ്ടംവഴി ഓടിക്കും": 5,
    "jeevanode vechekkilla": 5,
    "ജീവനോടെ വെച്ചേക്കില്ല": 5,
    "ജീവനോടെ വെക്കില്ല": 5,
    "theerthu kalayum": 5,
    "തീർത്തു കളയും": 5,
    "തീർത്തുകളയും": 5,
    "avasanippikkum ninne": 5,
    "അവസാനിപ്പിക്കും നിന്നെ": 5,
    "അവസാനിപ്പിക്കും": 5,
    "pachakku kattikkum": 5,
    "പച്ചക്ക് കത്തിക്കും": 5,
    "kuthikollum": 5,
    "kuthi kollum": 5,
    "കുത്തിക്കൊല്ലും": 5,
    "കുത്തി കൊല്ലും": 5,
    "naakku pizhuthedukku": 5,
    "നാക്ക് പിഴുതെടുക്കും": 5,
    "mukham adichupottikkum": 5,
    "മുഖം അടിച്ചു പൊട്ടിക്കും": 5,
    "chavitti koottum": 5,
    "chavittikkoottum": 5,
    "ചവിട്ടി കൂട്ടും": 5,
    "ചവിട്ടിക്കൂട്ടും": 5,
    "naattil irakkilla": 5,
    "നാട്ടിൽ  ഇറക്കില്ല": 5,
    "നാട്ടിൽ ഇറക്കില്ല നിന്നെ": 5,
    "thuni urinjunadattum": 5,
    "തുണി ഉരിഞ്ഞു നടത്തും": 5,
    "kali tharatha": 5,
    "chooral edukkum": 5,
    "adippichu": 5,
    "thalluka": 5,
    "onnu nokkatte": 5,
}
# ---------------------------------------------------------------------------
# Spelling normalisation for Manglish variation.
# Applied before keyword matching so myre/maire/mairu all hit the same entry.
# Each tuple is (compiled_regex, replacement_canonical_form).
# ---------------------------------------------------------------------------
_SPELLING_NORMS: list[tuple[re.Pattern, str]] = [
    # myre variants → myre
    (re.compile(r"\bmairu\b|\bmypre\b|\bmaire\b", re.IGNORECASE), "myre"),
    # pottan variants → pottan
    (re.compile(r"\bpotthan\b", re.IGNORECASE), "pottan"),
    # thayoli variants → thayoli
    (re.compile(r"\btayoli\b|\bthayoly\b|\bthayolli\b", re.IGNORECASE), "thayoli"),
    # naaye variants → naaye
    (re.compile(r"\bnaye\b|\bnaayi\b|\bnaay\b", re.IGNORECASE), "naaye"),
    # poda variants
    (re.compile(r"\bpodaa\b", re.IGNORECASE), "poda"),
    # ammanaaye variants
    (re.compile(r"\bamma\s*naaye\b", re.IGNORECASE), "ammanaaye"),
    # thallikollum variants → thallikollum
    (re.compile(r"\bthalli\s*kollam\b|\bthalli\s*kollan\b", re.IGNORECASE), "thallikollum"),
    # veettil keri/kayari normalisation
    (re.compile(r"\bveettil\s*kayari\s*thallum\b", re.IGNORECASE), "veettil keri thallum"),
    # kuna/kunna variants
    (re.compile(r"\bkoonaa\b|\bkoona\b", re.IGNORECASE), "kuna"),
    # TODO: add more normalisation rules as your corpus reveals new variants
]


def normalize_manglish(text: str) -> str:
    """Collapse common spelling variants to their canonical forms before keyword matching."""
    for pattern, canonical in _SPELLING_NORMS:
        text = pattern.sub(canonical, text)
    return text

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"https?://\S+|www\.\S+|youtu\.be/\S+|youtube\.com/\S+",
    re.IGNORECASE,
)
_CHANNEL_RE = re.compile(r"@[\w.-]+")
_MALAYALAM_RE = re.compile(r"[ഀ-ൿ]")  # Unicode block for Malayalam script


# ---------------------------------------------------------------------------
# Pure logic layer (no I/O, fully unit-testable)
# ---------------------------------------------------------------------------


def strip_urls_and_channels(text: str) -> str:
    """Decode HTML entities, remove URLs and @channel mentions, collapse whitespace."""
    text = html.unescape(text)          # &#39; → '  ,  &amp; → &  etc.
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)  # <br> → space
    text = re.sub(r"<[^>]+>", "", text)  # strip any remaining HTML tags
    text = _URL_RE.sub(" ", text)
    text = _CHANNEL_RE.sub(" ", text)
    return " ".join(text.split())


def has_malayalam_script(text: str) -> bool:
    """Return True if text contains Malayalam Unicode characters."""
    return bool(_MALAYALAM_RE.search(text))


def has_manglish_markers(text: str) -> bool:
    """Return True if text contains any known romanized-Malayalam marker (word-boundary match)."""
    lower = text.lower()
    for marker in MANGLISH_MARKERS:
        if re.search(r"\b" + re.escape(marker) + r"\b", lower):
            return True
    return False


def is_manglish(text: str) -> bool:
    """
    Return True if text is likely Manglish.
    Requires romanized Malayalam markers — Malayalam script alone does not qualify,
    because pure Malayalam script is Malayalam, not Manglish.
    A text that mixes script + romanized markers still qualifies.
    """
    return has_manglish_markers(text)


def conflict_intensity(messages: list[str]) -> int:
    """
    Return the maximum conflict intensity (0–5) found across all messages.
    0 means no conflict signal detected.

    Applies spelling normalisation before matching so variant spellings
    (e.g. maire, mypre) map to their canonical keyword entry.
    """
    combined = normalize_manglish(" ".join(messages)).lower()
    max_intensity = 0
    for kw, intensity in CONFLICT_KEYWORDS.items():
        if re.search(r"(?<!\w)" + re.escape(kw.lower()) + r"(?!\w)", combined):
            if intensity > max_intensity:
                max_intensity = intensity
                if max_intensity == 5:
                    break  # can't go higher
    return max_intensity


def anonymize_authors(raw_messages: list[dict]) -> tuple[list[str], int]:
    """
    Replace real author names with @user1, @user2, … (consistent per thread).

    Args:
        raw_messages: ordered list of dicts, each with keys 'author' and 'text'.

    Returns:
        (anonymized_texts, author_map_size)
        anonymized_texts: list of cleaned text strings with no author identity.
        author_map_size: number of unique authors seen.
    """
    author_map: dict[str, str] = {}
    anonymized: list[str] = []

    for msg in raw_messages:
        author = msg.get("author", "")
        text = msg.get("text", "")

        if author not in author_map:
            author_map[author] = f"@user{len(author_map) + 1}"

        clean = strip_urls_and_channels(text)
        anonymized.append(clean)

    return anonymized, len(author_map)


def parse_thread(top_comment: dict, replies: list[dict]) -> Optional[dict]:
    """
    Parse one top-level comment + its replies into a thread dict, or return
    None if the thread should be filtered out.

    Filtering rules:
      1. Thread must have ≥ 3 total messages (top + replies).
      2. Thread must have ≥ 1 reply.
      3. At least 1 message must contain romanized-Malayalam markers (Manglish).
    Non-conflict threads are kept and flagged with likely_conflict=False so
    annotators can prioritise conflict threads without losing neutral context.

    Args:
        top_comment: dict with 'id', 'author', 'text' from the API snippet.
        replies: list of dicts with 'author', 'text' (ordered oldest-first).

    Returns:
        Thread dict ready to write, or None.
    """
    all_messages_raw = [top_comment] + replies
    total = len(all_messages_raw)
    reply_count = len(replies)

    # Filter 1: size
    if total < 3 or reply_count < 1:
        return None

    # Filter 2: at least 1 message in the thread must contain Manglish markers.
    # Checking any message (not just the final one) allows threads where the last
    # reply happens to be pure English or script Malayalam while the rest of the
    # thread is Manglish.
    if not any(is_manglish(m.get("text", "")) for m in all_messages_raw):
        return None

    # Score conflict on raw text before anonymization (keywords may match names/context)
    raw_texts = [m.get("text", "") for m in all_messages_raw]
    intensity = conflict_intensity(raw_texts)

    anonymized_texts, author_map_size = anonymize_authors(all_messages_raw)

    # target_index = the message most useful for the annotator to focus on.
    # Pick the message with the highest individual conflict score so annotators
    # see the most conflicting message highlighted, not always the last reply.
    # Falls back to last message when the thread has no conflict signal.
    per_msg_scores = [conflict_intensity([t]) for t in raw_texts]
    best_score = max(per_msg_scores)
    if best_score > 0:
        target_index = per_msg_scores.index(best_score)
    else:
        target_index = len(anonymized_texts) - 1

    thread_id = top_comment.get("id", "")
    video_id = top_comment.get("video_id", "")

    return {
        "thread_id": thread_id,
        "video_id": video_id,
        "messages": anonymized_texts,
        "author_map_size": author_map_size,
        "target_index": target_index,
        "likely_conflict": intensity > 0,
        "conflict_intensity": intensity,   # 0=none, 1=mild … 5=extreme threat
        "topic": None,
    }


def parse_api_response(response: dict, video_id: str) -> list[dict]:
    """
    Convert a raw YouTube commentThreads.list API response dict into a list
    of thread dicts (already filtered and anonymized).

    Args:
        response: the dict returned by the API (or a mock of the same shape).
        video_id: the YouTube video ID this response belongs to.

    Returns:
        List of valid thread dicts (may be empty).
    """
    threads = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        top_snippet = snippet.get("topLevelComment", {}).get("snippet", {})
        thread_id = item.get("id", "")

        top_comment = {
            "id": thread_id,
            "video_id": video_id,
            "author": top_snippet.get("authorDisplayName", ""),
            "text": top_snippet.get("textDisplay", ""),
        }

        raw_replies = item.get("replies", {}).get("comments", [])
        replies = [
            {
                "author": r.get("snippet", {}).get("authorDisplayName", ""),
                "text": r.get("snippet", {}).get("textDisplay", ""),
            }
            for r in raw_replies
        ]

        thread = parse_thread(top_comment, replies)
        if thread is not None:
            threads.append(thread)

    return threads


# ---------------------------------------------------------------------------
# I/O layer (network + file — not tested in unit tests)
# ---------------------------------------------------------------------------


def load_seed_video_ids(path: Path) -> list[str]:
    """Read video IDs from a JSONL file (one {"video_id": "..."} per line)."""
    ids = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                ids.append(json.loads(line)["video_id"])
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[WARN] Skipping malformed seed line {i}: {e}")
    return ids


def load_existing_thread_ids(output_path: Path) -> set[str]:
    """Return the set of thread_ids already written, for idempotency."""
    seen: set[str] = set()
    if not output_path.exists():
        return seen
    with output_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    seen.add(obj["thread_id"])
                except (json.JSONDecodeError, KeyError):
                    pass
    return seen


def fetch_threads_for_video(youtube, video_id: str) -> list[dict]:
    """
    Call the YouTube API to get comment threads for one video.
    Returns a list of parsed thread dicts.
    Handles quota exhaustion gracefully.
    """
    from googleapiclient.errors import HttpError  # type: ignore

    all_threads: list[dict] = []
    page_token = None

    while True:
        try:
            request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=100,
                order="relevance",
                pageToken=page_token,
            )
            response = request.execute()
        except HttpError as e:
            content = str(e.content)
            status = e.resp.status
            if status == 403 and "quotaExceeded" in content:
                print(
                    f"\n[QUOTA] YouTube API quota exceeded after collecting "
                    f"{len(all_threads)} threads. Re-run tomorrow to continue.",
                    file=sys.stderr,
                )
                return all_threads
            elif status == 403 and "commentsDisabled" in content:
                print(f"[SKIP] Comments disabled for video {video_id}")
                return all_threads
            elif status == 404:
                print(f"[SKIP] Video not found: {video_id}")
                return all_threads
            elif status == 403 and "forbidden" in content.lower():
                print(f"[SKIP] Access forbidden for video {video_id} (private/region-locked?)")
                return all_threads
            else:
                print(f"[ERROR] HTTP {status} for video {video_id}: {content[:200]}", file=sys.stderr)
                return all_threads

        all_threads.extend(parse_api_response(response, video_id))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_threads


def run_scraper(
    seed_path: Path,
    output_path: Path,
    api_key: str,
) -> None:
    """Main scraping loop: read seeds, fetch, filter, write."""
    from googleapiclient.discovery import build  # type: ignore

    video_ids = load_seed_video_ids(seed_path)
    if not video_ids:
        print("No video IDs found in seed file. Exiting.")
        return

    existing_ids = load_existing_thread_ids(output_path)
    print(f"[INFO] {len(existing_ids)} threads already in output (will skip duplicates).")

    # Build set of video_ids already scraped so we don't burn quota re-fetching them
    scraped_videos: set[str] = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        scraped_videos.add(json.loads(line)["video_id"])
                    except (json.JSONDecodeError, KeyError):
                        pass

    remaining = [v for v in video_ids if v not in scraped_videos]
    print(f"[INFO] {len(scraped_videos)} videos already scraped, {len(remaining)} remaining.")

    youtube = build("youtube", "v3", developerKey=api_key)
    total_new = 0

    with output_path.open("a", encoding="utf-8") as out_f:
        for video_id in remaining:
            print(f"[INFO] Fetching threads for video: {video_id}")
            threads = fetch_threads_for_video(youtube, video_id)
            for t in threads:
                if t["thread_id"] not in existing_ids:
                    out_f.write(json.dumps(t, ensure_ascii=False) + "\n")
                    existing_ids.add(t["thread_id"])
                    total_new += 1

    print(f"\n[DONE] Collected {total_new} new threads → {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    api_key = os.environ.get("YT_API_KEY")
    if not api_key:
        print(
            "ERROR: Set the YT_API_KEY environment variable before running.",
            file=sys.stderr,
        )
        sys.exit(1)

    repo_root = Path(__file__).parent.parent
    seed_path = repo_root / "data" / "seeds.jsonl"
    output_path = repo_root / "data" / "raw_threads.jsonl"

    if not seed_path.exists():
        print(f"ERROR: Seed file not found: {seed_path}", file=sys.stderr)
        sys.exit(1)

    run_scraper(seed_path, output_path, api_key)


if __name__ == "__main__":
    main()
