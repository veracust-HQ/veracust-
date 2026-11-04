from setuptools import setup, find_packages

setup(
    name="veracust",
    version="1.0.0",
    description="Audio synthetic-speech forensic triage engine",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.24", "scipy>=1.10", "PyYAML>=6.0",
        "torch>=2.1", "torchaudio>=2.1", "librosa>=0.10.1",
        "soundfile>=0.12", "transformers>=4.38", "parselmouth>=0.4.3"
    ],
)
