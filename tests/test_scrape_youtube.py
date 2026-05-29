"""
Unit tests for scrape_youtube.py — pure logic layer only.
No API key or network connection required.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scrape_youtube import (
    anonymize_authors,
    conflict_intensity,
    is_manglish,
    normalize_manglish,
    parse_api_response,
    parse_thread,
    strip_urls_and_channels,
)

# ---------------------------------------------------------------------------
# Helpers to build fake API responses (mirror the real YouTube JSON shape)
# ---------------------------------------------------------------------------


def _make_comment(author: str, text: str, comment_id: str = "c1") -> dict:
    return {
        "id": comment_id,
        "snippet": {
            "authorDisplayName": author,
            "textDisplay": text,
        },
    }


def _make_thread(
    thread_id: str,
    top_author: str,
    top_text: str,
    replies: list[tuple[str, str]],
    video_id: str = "vid1",
) -> dict:
    """Build a fake commentThreads item matching the YouTube API shape."""
    reply_items = [
        {
            "snippet": {
                "authorDisplayName": a,
                "textDisplay": t,
            }
        }
        for a, t in replies
    ]
    return {
        "id": thread_id,
        "snippet": {
            "topLevelComment": {
                "snippet": {
                    "authorDisplayName": top_author,
                    "textDisplay": top_text,
                    "videoId": video_id,
                }
            }
        },
        "replies": {"comments": reply_items} if reply_items else {},
    }


def _make_response(items: list[dict]) -> dict:
    return {"items": items}


# ---------------------------------------------------------------------------
# Tests: strip_urls_and_channels
# ---------------------------------------------------------------------------


def test_strip_urls():
    assert "hello world" == strip_urls_and_channels(
        "hello https://example.com/foo world"
    )


def test_strip_channel_mentions():
    result = strip_urls_and_channels("reply to @SomeChannel ok")
    assert "@SomeChannel" not in result


# ---------------------------------------------------------------------------
# Tests: is_manglish
# ---------------------------------------------------------------------------


def test_malayalam_script_alone_not_manglish():
    # Pure Malayalam script with no romanized markers is Malayalam, not Manglish
    assert not is_manglish("ഇത് ശരിയല്ല അവൻ പറഞ്ഞു")


def test_malayalam_script_plus_romanized_is_manglish():
    # Mixed: script + romanized marker — qualifies as Manglish
    assert is_manglish("ഇത് correct aanu")


def test_romanized_marker_detected():
    assert is_manglish("athu alla correct")


def test_english_only_rejected():
    assert not is_manglish("This is a purely English sentence with no markers.")


# ---------------------------------------------------------------------------
# Tests: parse_thread (filtering rules)
# ---------------------------------------------------------------------------


def _top(text: str, author: str = "UserA", video_id: str = "vid1") -> dict:
    return {"id": "t1", "video_id": video_id, "author": author, "text": text}


def _reply(text: str, author: str = "UserB") -> dict:
    return {"author": author, "text": text}


def test_short_thread_dropped():
    # Only top + 1 reply = 2 total → must be dropped (need ≥ 3)
    top = _top("athu alla")
    replies = [_reply("yes aanu")]
    result = parse_thread(top, replies)
    assert result is None, "Thread with < 3 messages should be dropped"


def test_no_reply_dropped():
    # 3 messages but no replies (only top repeated — shouldn't happen but guard it)
    top = _top("athu alla")
    result = parse_thread(top, [])
    assert result is None, "Thread with 0 replies should be dropped"


def test_non_manglish_final_message_dropped():
    # Final message is pure English → should be dropped
    top = _top("athu alla anu")
    replies = [
        _reply("illa bro illa"),
        _reply("This is pure English, no Malayalam markers at all."),
    ]
    result = parse_thread(top, replies)
    assert result is None, "Thread whose final message is not Manglish should be dropped"


def test_valid_thread_passes():
    top = _top("athu alla enthu poda")
    replies = [
        _reply("aanu correct", author="UserB"),
        _reply("illa bro illa und", author="UserC"),
    ]
    result = parse_thread(top, replies)
    assert result is not None, "Valid Manglish+conflict thread should pass filtering"


def test_no_conflict_signal_kept_and_flagged():
    # Manglish but no conflict keyword → kept, likely_conflict=False, intensity=0
    top = _top("athu alla enthu")
    replies = [
        _reply("aanu correct", author="UserB"),
        _reply("illa bro und", author="UserC"),
    ]
    result = parse_thread(top, replies)
    assert result is not None, "Manglish thread with no conflict signal should still be kept"
    assert result["likely_conflict"] is False
    assert result["conflict_intensity"] == 0


# ---------------------------------------------------------------------------
# Tests: conflict_intensity scoring & spelling normalisation
# ---------------------------------------------------------------------------


def test_intensity_mild():
    assert conflict_intensity(["athu poda illa"]) == 1


def test_intensity_severe_slur():
    assert conflict_intensity(["avante myre okke"]) == 4


def test_intensity_threat():
    assert conflict_intensity(["veettil keri thallum"]) == 5


def test_intensity_zero_no_keywords():
    assert conflict_intensity(["njan paranju alla correct"]) == 0


def test_intensity_returns_max():
    # poda=1 and thayoli=5 in same thread → should return 5
    assert conflict_intensity(["poda nee", "thayoli aanu"]) == 5


def test_spelling_normalisation_maire_to_myre():
    # maire is a variant of myre (intensity 4) — should be caught after normalisation
    assert conflict_intensity(["avante maire okke"]) == 4


def test_spelling_normalisation_potthan_to_pottan():
    assert conflict_intensity(["potthan aanu avan"]) == 2


# ---------------------------------------------------------------------------
# Tests: anonymization
# ---------------------------------------------------------------------------


def test_authors_anonymized():
    top = _top("athu alla enthu poda", author="RealPerson")
    replies = [
        _reply("aanu correct", author="AnotherPerson"),
        _reply("illa bro und", author="ThirdPerson"),
    ]
    result = parse_thread(top, replies)
    assert result is not None
    for msg in result["messages"]:
        assert "RealPerson" not in msg
        assert "AnotherPerson" not in msg
        assert "ThirdPerson" not in msg


def test_same_author_gets_same_label():
    """If the same author appears in top and a reply, they get the same @userN."""
    raw = [
        {"author": "Alice", "text": "athu alla"},
        {"author": "Bob", "text": "aanu yes"},
        {"author": "Alice", "text": "illa und"},  # Alice again
    ]
    texts, size = anonymize_authors(raw)
    # Alice should be @user1 (first seen), Bob @user2; size must be 2
    assert size == 2


def test_url_stripped_in_output():
    top = _top("check https://youtube.com/watch?v=abc aanu this poda")
    replies = [
        _reply("alla bro", author="B"),
        _reply("illa und correct", author="C"),
    ]
    result = parse_thread(top, replies)
    assert result is not None
    for msg in result["messages"]:
        assert "youtube.com" not in msg
        assert "https://" not in msg


# ---------------------------------------------------------------------------
# Tests: output schema
# ---------------------------------------------------------------------------


def test_output_schema():
    top = _top("athu alla enthu poda", author="A")
    replies = [
        _reply("aanu right", author="B"),
        _reply("illa bro und", author="C"),
    ]
    result = parse_thread(top, replies)
    assert result is not None
    required_keys = {
        "thread_id", "video_id", "messages", "author_map_size",
        "target_index", "likely_conflict", "conflict_intensity", "topic",
    }
    assert required_keys == set(result.keys()), f"Missing keys: {required_keys - set(result.keys())}"
    assert isinstance(result["messages"], list)
    assert result["likely_conflict"] is True        # True because top text contains "poda"
    assert isinstance(result["conflict_intensity"], int)
    assert 1 <= result["conflict_intensity"] <= 5   # poda = intensity 1
    assert result["topic"] is None
    assert result["target_index"] == len(result["messages"]) - 1


# ---------------------------------------------------------------------------
# Tests: parse_api_response (full pipeline with fake API dict)
# ---------------------------------------------------------------------------


def test_parse_api_response_filters_short():
    items = [
        _make_thread(
            "t1", "A", "athu alla",
            replies=[("B", "aanu")],  # only 2 total → dropped
        )
    ]
    result = parse_api_response(_make_response(items), "vid1")
    assert result == [], "Short thread from API response should be filtered out"


def test_parse_api_response_filters_non_manglish():
    items = [
        _make_thread(
            "t2", "A", "athu alla",
            replies=[
                ("B", "correct yes"),
                ("C", "This is English only"),  # final message not Manglish
            ],
        )
    ]
    result = parse_api_response(_make_response(items), "vid1")
    assert result == [], "Non-Manglish final message should be filtered out"


def test_parse_api_response_valid_thread():
    items = [
        _make_thread(
            "t3", "Alice", "athu alla enthu poda",
            replies=[
                ("Bob", "aanu bro"),
                ("Carol", "illa und correct"),
            ],
        )
    ]
    result = parse_api_response(_make_response(items), "vid1")
    assert len(result) == 1
    t = result[0]
    assert t["thread_id"] == "t3"
    assert t["video_id"] == "vid1"
    assert len(t["messages"]) == 3
    assert t["target_index"] == 2
    assert isinstance(t["likely_conflict"], bool)
    # No real author names in output
    for msg in t["messages"]:
        assert "Alice" not in msg
        assert "Bob" not in msg
        assert "Carol" not in msg


def test_parse_api_response_multiple_threads():
    items = [
        _make_thread(
            "t4", "A", "athu alla poda",         # conflict keyword: poda
            replies=[("B", "aanu"), ("C", "illa und")],
        ),
        _make_thread(
            "t5", "X", "just english",
            replies=[("Y", "also english"), ("Z", "still english")],
        ),
    ]
    result = parse_api_response(_make_response(items), "vid1")
    # t4 passes (final message has Manglish markers), t5 dropped (all English)
    assert len(result) == 1
    assert result[0]["thread_id"] == "t4"


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_strip_urls,
        test_strip_channel_mentions,
        test_malayalam_script_alone_not_manglish,
        test_malayalam_script_plus_romanized_is_manglish,
        test_romanized_marker_detected,
        test_english_only_rejected,
        test_short_thread_dropped,
        test_no_reply_dropped,
        test_non_manglish_final_message_dropped,
        test_no_conflict_signal_kept_and_flagged,
        test_intensity_mild,
        test_intensity_severe_slur,
        test_intensity_threat,
        test_intensity_zero_no_keywords,
        test_intensity_returns_max,
        test_spelling_normalisation_maire_to_myre,
        test_spelling_normalisation_potthan_to_pottan,
        test_valid_thread_passes,
        test_authors_anonymized,
        test_same_author_gets_same_label,
        test_url_stripped_in_output,
        test_output_schema,
        test_parse_api_response_filters_short,
        test_parse_api_response_filters_non_manglish,
        test_parse_api_response_valid_thread,
        test_parse_api_response_multiple_threads,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed.")
    sys.exit(0 if failed == 0 else 1)
