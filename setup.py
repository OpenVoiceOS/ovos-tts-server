#!/usr/bin/env python3
from setuptools import setup

setup(
    name='ovos-tts-server',
    version='0.0.2',
    description='simple flask server to host OpenVoiceOS tts plugins as a service',
    url='https://github.com/OpenVoiceOS/ovos-tts-server',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    license='Apache-2.0',
    packages=['ovos_tts_server'],
    install_requires=["ovos-plugin-manager>=0.0.18a1",
                      "flask"],
    zip_safe=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Text Processing :: Linguistic',
        'License :: OSI Approved :: Apache Software License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='plugin TTS OVOS OpenVoiceOS',
    entry_points={
        'console_scripts': [
            'ovos-tts-server=ovos_tts_server.__main__:main'
        ]
    }
)
