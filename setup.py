from setuptools import setup, find_packages

setup(
    name="project-astra",
    version="2026.6.0",
    description="Sovereign AI Influencer Agent - Autonomous digital persona system",
    author="Sovereign Architect",
    python_requires=">=3.11",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "patchright>=1.58.0",
        "rebrowser-playwright>=1.40.0",
        "httpx[http2]>=0.27.0",
        "Pillow>=10.0.0",
        "imagehash>=4.3.0",
        "numpy>=1.26.0",
        "pydantic>=2.5.0",
        "loguru>=0.7.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-playwright>=0.4.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.7.0",
        ],
        "face": [
            "face-recognition>=1.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "astra=orchestrator:main",
        ]
    },
)
