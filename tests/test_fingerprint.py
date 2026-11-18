from pgrv.fingerprint import diff


def test_identical_maps_have_no_diff():
    fp = {"public.a": {"rows": 3, "md5": "abc"}}
    assert diff(fp, dict(fp)) == []


def test_reports_missing_extra_and_changed_tables():
    expected = {"public.a": {"rows": 3, "md5": "aaaaaaaa1"}, "public.b": {"rows": 1, "md5": "b"}}
    actual = {"public.a": {"rows": 2, "md5": "bbbbbbbb2"}, "public.c": {"rows": 0, "md5": ""}}
    problems = diff(expected, actual)
    assert "public.a: rows 3 -> 2, md5 aaaaaaaa -> bbbbbbbb" in problems
    assert "public.b: missing after restore" in problems
    assert "public.c: unexpected table after restore" in problems
