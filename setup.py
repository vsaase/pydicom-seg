import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="pydicom-seg",
    version="0.3.0-dev",
    author="Sven Koitka",
    author_email="sven.koitka@uk-essen.de",
    description=(
        "Python package for DICOM-SEG medical segmentation file reading and writing"),
    license="MIT",
    keywords="dicom",
    url="https://github.com/razorx89/pydicom-seg",
    packages=['pydicom_seg'],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
    ],
)
