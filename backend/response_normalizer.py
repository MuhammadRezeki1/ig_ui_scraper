"""
response_normalizer.py
======================
Utility untuk normalize response dari tiktok_scraper_v52 sebelum
dikirim ke frontend.

MASALAH ASAL:
  - Backend: _summarize() mengembalikan top_liked_comments (List[Dict])
  - Instagram backend: _summarize() mengembalikan top_liked (List[Dict])
  - Frontend TypeScript: SentimentSummary tidak punya kedua field itu
    → field di-strip TypeScript, top 5 komentar tidak pernah render

FIX:
  - Pastikan response selalu punya `top_liked_comments`
  - Pastikan `comments_count` selalu ada di root response
  - Inject ke route FastAPI sebelum return ke frontend

Cara pakai di main.py FastAPI:
    from response_normalizer import normalize_video_result

    result = scrape_video(url, max_comments)
    result = normalize_video_result(result)   # <── tambah ini
    return success(result, f"Scraped {result.get('comments_count',0)} comments")
"""

from typing import Dict, Any, List


def normalize_sentiment_summary(s: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pastikan field top_liked_comments selalu ada di sentiment_summary.

    Backend tiktok_scraper_v52.py → _summarize() sudah mengisi
    top_liked_comments dengan benar. Fungsi ini hanya safety-net
    kalau scraper versi lama tidak mengirim field tersebut.
    """
    if not isinstance(s, dict):
        return s

    # Jika top_liked_comments tidak ada atau bukan list, isi array kosong
    if not isinstance(s.get("top_liked_comments"), list):
        s["top_liked_comments"] = []

    # Pastikan setiap item punya field yang diharapkan frontend
    normalized = []
    for i, c in enumerate(s["top_liked_comments"]):
        if not isinstance(c, dict):
            continue
        normalized.append({
            "rank":       c.get("rank", i + 1),
            "username":   c.get("username", ""),
            "text":       c.get("text", "")[:200],
            "like_count": int(c.get("like_count", 0) or 0),
            "category":   c.get("category", "NEUTRAL"),
            "sentiment":  c.get("sentiment", ""),
            "number":     c.get("number", 0),
        })
    s["top_liked_comments"] = normalized

    # Pastikan field numerik lainnya tidak None
    numeric_fields = [
        "total_comments",
        "positive_count", "positive_percentage",
        "negative_count", "negative_percentage",
        "neutral_count",  "neutral_percentage",
        "humor_count",    "humor_percentage",
        "toxic_count",    "toxic_percentage",
        "hate_speech_count", "hate_percentage",
        "sarcasm_count",  "sarcasm_percentage",
        "wellwish_count", "wellwish_percentage",
        "avg_ml_confidence",
    ]
    for field in numeric_fields:
        if s.get(field) is None:
            s[field] = 0

    return s


def normalize_video_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize full video result sebelum dikirim ke frontend.

    Panggil ini di FastAPI bridge (main.py) sebelum return response.
    """
    if not isinstance(result, dict):
        return result

    # FIX: pastikan comments_count selalu ada
    # Backend mengisi ini, tapi kalau ada edge case (error parsing), field mungkin hilang
    if "comments_count" not in result or result.get("comments_count") is None:
        comments = result.get("comments", [])
        result["comments_count"] = len(comments) if isinstance(comments, list) else 0

    # FIX: normalize sentiment_summary
    ss = result.get("sentiment_summary")
    if isinstance(ss, dict):
        result["sentiment_summary"] = normalize_sentiment_summary(ss)

    return result


def normalize_batch_result(batch_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize batch scrape result.

    batch_data = {total, success, failed, results: [{url, success, data?, error?}]}
    """
    if not isinstance(batch_data, dict):
        return batch_data

    results = batch_data.get("results", [])
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and item.get("success") and isinstance(item.get("data"), dict):
                item["data"] = normalize_video_result(item["data"])

    batch_data["results"] = results
    return batch_data