from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="institutional-microstructure",
    version="0.1.0",
    author="Netrade1",
    description="A toolkit for institutional trading and market microstructure analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Netrade1/Institutional-Microstructure-",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "requests>=2.31.0",
        "websocket-client>=1.6.0",
        "python-dateutil>=2.8.2",
        "pytz>=2023.3",
    ],
)
