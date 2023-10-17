import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "singular",
    version = "0.0.1",
    author = "Joseph Zambrano",
    author_email = "j.zambrano@singularcapital.io",
    description = ("Singular library implemented in Python."),
    license = "LICENSE",
    package_dir={"singular": "singular"},
    packages=find_packages(include=["singular", "singular.*"])
    #long_description=read("../README.md"),
)

