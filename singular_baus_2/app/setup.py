import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "euler",
    version = "0.0.1",
    author = "Joseph Zambrano",
    author_email = "j.zambrano@singularcapital.io",
    description = ("Euler interface implemented in Python."),
    license = "LICENSE",
    package_dir={"euler": "euler"},
    packages=find_packages(include=["euler", "euler.*"])
    #long_description=read("../README.md"),
)

