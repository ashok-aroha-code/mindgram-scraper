import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from scraper_pipeline.models import finalize_record
from scraper_pipeline.utils.dates import normalize_date

def test_date_normalization():
    print("Testing date normalization...")
    dates = [
        ("2026-05-29", "2026-05-29"),
        ("Friday, October 23, 2026", "2026-10-23"),
        ("12 May 2024", "2024-05-12"),
        ("May 12, 2024", "2024-05-12"),
    ]
    for input_date, expected in dates:
        result = normalize_date(input_date)
        print(f"  '{input_date}' -> '{result}' (expected '{expected}')")
        assert result == expected

def test_structure_finalization():
    print("\nTesting record finalization...")
    raw = {
        "link": "http://example.com/art1",
        "title": "A Great Paper",
        "author_info": "John Doe",
        "abstract": "This is the text abstract.",
        "abstract_html": "<div><p>This is <b>bold</b> and <i>italic</i>.</p></div>",
        "abstract_markdown": "This is **bold** and *italic*.",
        "date": "2026-04-14",
        "some_extra_info": "Extra Value"
    }
    
    final = finalize_record(raw)
    
    print("Final record structure:")
    import json
    print(json.dumps(final, indent=4))
    
    # Check mandatory fields
    assert "link" in final
    assert "abstract_metadata" in final
    assert final["abstract_metadata"]["date"] == "2026-04-14"
    assert final["abstract_metadata"]["some_extra_info"] == "Extra Value"
    assert "doi" in final
    assert final["doi"] == "" # Default

if __name__ == "__main__":
    try:
        test_date_normalization()
        test_structure_finalization()
        print("\nAll unit tests passed!")
    except Exception as e:
        print(f"\nTests failed: {e}")
        import traceback
        traceback.print_exc()
