from setuptools import setup
from setuptools import find_packages

version = '0.1.0'

install_requires = [
    'certbot>=1.1.0',
    'setuptools>=41.6.0',
    'requests',
]

setup(
    name='certbot-dns-cdmon',
    version=version,
    description="CDmon DNS Authenticator plugin for Certbot",
    url='https://github.com/yourusername/certbot-dns-cdmon',
    author="Your Name",
    author_email='your.email@example.com',
    license='Apache License 2.0',
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
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
    include_package_data=True,
    install_requires=install_requires,
    entry_points={
        'certbot.plugins': [
            'dns-cdmon = certbot_dns_cdmon.dns_cdmon:Authenticator',
        ],
    },
)