from setuptools import find_packages, setup


setup(
    name="dailybrief",
    version="0.1.0",
    description="Daily Brief: local-first Python AI news and markets digest generator.",
    packages=find_packages(include=["dailybrief", "dailybrief.*"]),
    python_requires=">=3.9",
    install_requires=[
        "anthropic>=0.39.0",
        "beautifulsoup4>=4.12.0",
        "feedparser>=6.0.11",
        "httpx>=0.27.0",
        "json-repair>=0.30.0",
        "openai>=1.55.0",
        "python-dotenv>=1.0.1",
    ],
    extras_require={"test": ["pytest>=8.0.0"]},
    entry_points={"console_scripts": ["dailybrief=dailybrief.cli:main"]},
)
