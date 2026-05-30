from connector import geo


def test_no_layer_context_uses_location_sensitive_demo_roster(monkeypatch) -> None:
    monkeypatch.setattr(geo, "_layers", False)

    assert geo.resolve_context("43.64413_-79.40280")["councillors"] == [
        "toronto0",
        "toronto1",
        "toronto2",
        "toronto3",
        "toronto4",
    ]
    assert geo.resolve_context("43.76480_-79.41430")["councillors"] == [
        "north0",
        "north1",
        "north2",
        "north3",
        "north4",
    ]
    assert geo.resolve_context("43.64520_-79.54280")["councillors"] == [
        "etobicoke0",
        "etobicoke1",
        "etobicoke2",
        "etobicoke3",
        "etobicoke4",
    ]
    assert geo.resolve_context("43.77640_-79.25710")["councillors"] == [
        "scarborough0",
        "scarborough1",
        "scarborough2",
        "scarborough3",
        "scarborough4",
    ]
