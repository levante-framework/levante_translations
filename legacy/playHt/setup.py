from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="Levante Audio Generation",
    version="0.1.0",
    author="David Cardinal",
    author_email="david81@stanford.edu",
    description="Create needed audio in supported languages",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/levante-framwork/audio-generation",
    packages=find_packages(include=['audio-generation', 'audio-generation.*']),
    install_requires=[
        certifi==2024.12.14
        charset-normalizer==3.4.1
        idna==3.10
        numpy==2.2.1
        pandas==2.2.3
        python-dateutil==2.9.0.post0
        pytz==2024.2
        requests==2.32.3
        six==1.17.0
        tzdata==2024.2
        urllib3==2.3.0
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
