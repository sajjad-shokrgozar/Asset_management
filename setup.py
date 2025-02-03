from setuptools import setup, find_packages

setup(
    name="portfolio_management",
    version="0.1.0",
    author="sajjad_shokrgozar",
    author_email="shokrgozarsajjad@gmail.com",
    description="A Python package for asset management",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/sajjad-shokrgozar/asset_management",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "scipy",
        "requests",
        "matplotlib",
        "jdatetime"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    license="MIT",
    license_files=["LICENSE"],  # ✅ Correct field
)
