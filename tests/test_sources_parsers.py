import dailybrief.sources.github_trending as gh


def test_github_trending_parser_with_mock(monkeypatch):
    class Response:
        text = """
        <article class="Box-row">
          <h2><a href="/owner/repo">owner / repo</a></h2>
          <p>Useful repo.</p>
          <div class="f6"><span itemprop="programmingLanguage">Python</span>
            <a href="/owner/repo/stargazers">1,234</a>
            <a href="/owner/repo/forks">56</a>
            <span>7 stars today</span>
          </div>
        </article>
        """

    monkeypatch.setattr(gh.httpx, "get", lambda *args, **kwargs: Response())
    items = gh.fetch_github_trending("github-trending")
    assert items[0].title == "owner/repo"
    assert items[0].meta
