from pathlib import Path

import setuptools

# read README file
from os import path
ROOT_DIR = Path(__file__).parent.resolve()

with open(ROOT_DIR / 'README.md', encoding='utf-8') as f:
    long_description = f.read()

setuptools.setup(
    name="versioned-pickle", # Replace with your own username
    # SCM stuff is added here as well, for compatibility with tools that don't yet use the info
    # from pyproject.toml (e.g. setup.py commands)
    use_scm_version={'local_scheme': 'dirty-tag'},
    setup_requires=['setuptools_scm'],
    packages=setuptools.find_packages(),
    author="Asaf Reich",
    author_email="asafspades@gmail.com",
    description="A small utility package for adding environment metadata to pickles and warning on mismatch when loaded",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires = ['importlib-metadata>=4.4;python_version<"3.10"'],
    include_package_data=True,
    url="https://github.com/a-reich/versioned_pickle",
    license='MIT License',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)