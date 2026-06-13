from setuptools import setup, find_packages

setup(
    name="cyber_ai",
    version="1.0.0",
    description="AI-puissance : Framework IA de Cybersécurité tout-en-un",
    author="CyberAI Team",
    packages=find_packages(),
    install_requires=[
        "scikit-learn>=1.0.0",
        "numpy>=1.21.0",
        "requests>=2.26.0",
        "beautifulsoup4>=4.10.0",
        "colorama>=0.4.4",
        "joblib>=1.1.0",
    ],
    entry_points={
        "console_scripts": [
            "cyber-ai=main:main",
        ],
        "gui_scripts": [
            "cyber-ai-gui=gui:main",
        ],
    },
    python_requires=">=3.8",
)
