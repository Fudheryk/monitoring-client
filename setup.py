from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent

README = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""

setup(
    name="monitoring-client",
    version="0.1.0",
    description="Lightweight metrics collector client for server monitoring",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Axiv IT Group",
    url="https://example.com/monitoring-client",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "psutil",
        "requests",
        "PyYAML",
        "jsonschema",
    ],
    entry_points={
        "console_scripts": [
            "monitoring-client=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Environment :: Console",
        "Operating System :: POSIX :: Linux",
        "Topic :: System :: Monitoring",
    ],
)
