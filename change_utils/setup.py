from setuptools import setup, find_packages

setup(
    name="change_check",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "crowdin-api-client>=1.24.1",
        "pyairtable>=3.3.0",
        "python-dotenv>=1.1.0",
        "argparse>=1.4.0",
        "flatten-json>=0.1.14",
        "requests>=2.32.5"
    ],
    entry_points={
        "console_scripts": [
            # Transition tools
            #"get-split-stringids=change_check.transition_tools.get_split_stringIds:main",
            #"attach-screenshots=change_check.transition_tools.attach_screenshots:main",
            #"crowdin-airtable-sync=change_check.transition_tools.crowdin_airtable_sync:main"
            "crowdin-backup=change_check.transition_tools.crowdin_backup:main",
            # Source string update
            "check-newsource=change_check.source_update.check_source_strings:main",
            "test-ci-edit=change_check.source_update.test_edit_string:main",
            "update-source-strings=change_check.source_update.update_source_strings:main",
            # Platform update
            "build-survey=change_check.platform_update.update_survey:main",
            "build-corpus=change_check.platform_update.build_corpus:main",
            "split-corpus=change_check.platform_update.split_corpus:main"
            #"review-translations=app.platform_update.fetch_translations:main",
            #"update-translations=app.platform_update.fetch_translations:main"
        ]
    }
)