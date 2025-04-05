from setuptools import setup, find_packages
from pathlib import Path

# Read the README.md content
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='certbot-dns-cdmon',
    version='0.4.0',
    description="CDmon DNS Authenticator plugin for Certbot",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/rascazzione/certbot-dns-cdmon',
    author="rascazzione",
    author_email='rascazzione@gmail.com',
    license='MIT',
    include_package_data=True,
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Intended Audience :: System Administrators',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Security',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Networking',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
    packages=find_packages(),
    install_requires=[
        'certbot>=1.1.0',
        'requests',
    ],
    entry_points={
        'certbot.plugins': [
            'dns-cdmon = certbot_dns_cdmon.dns_cdmon:Authenticator',
        ],
    },
)
