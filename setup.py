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
        "pandas>=1.3.0",
        "scapy>=2.4.5",
        "requests>=2.26.0",
        "beautifulsoup4>=4.10.0",
        "colorama>=0.4.4",
        "python-whois>=0.8.0",
        "tldextract>=3.2.0",
        "python-nmap>=0.7.1",
        "joblib>=1.1.0",
    ],
    entry_points={
        "console_scripts": [
            "cyber-ai=main:main",
        ],
    },
    python_requires=">=3.8",
)
