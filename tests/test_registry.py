from dailybrief.sources.registry import load_all_sources


def test_sources_config_loads():
    sources = load_all_sources()
    assert len(sources) >= 20
    assert len({s.id for s in sources}) == len(sources)
    assert all(s.category in ("tech", "finance", "politics") for s in sources)
