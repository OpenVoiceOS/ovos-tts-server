#!/usr/bin/env python3
from setuptools import setup, find_packages
from os import path, environ

BASE_PATH = path.abspath(path.dirname(__file__))


def required(requirements_file):
    """ Read requirements file and remove comments and empty lines. """
    with open(path.join(BASE_PATH, requirements_file), 'r') as f:
        requirements = f.read().splitlines()
        if 'MYCROFT_LOOSE_REQUIREMENTS' in environ:
            print('USING LOOSE REQUIREMENTS!')
            requirements = [r.replace('==', '>=').replace('~=', '>=') for r in requirements]
        return [pkg for pkg in requirements
                if pkg.strip() and not pkg.startswith("#")]


with open(path.join(BASE_PATH, "readme.md"), "r") as f:
    long_description = f.read()

def get_version():
    """ Find the version of ovos-core"""
    version = None
    version_file = path.join(BASE_PATH, 'ovos_tts_server', 'version.py')
    major, minor, build, alpha = (None, None, None, None)
    with open(version_file) as f:
        for line in f:
            if 'VERSION_MAJOR' in line:
                major = line.split('=')[1].strip()
            elif 'VERSION_MINOR' in line:
                minor = line.split('=')[1].strip()
            elif 'VERSION_BUILD' in line:
                build = line.split('=')[1].strip()
            elif 'VERSION_ALPHA' in line:
                alpha = line.split('=')[1].strip()

            if ((major and minor and build and alpha) or
                    '# END_VERSION_BLOCK' in line):
                break
    version = f"{major}.{minor}.{build}"
    if int(alpha):
        version += f"a{alpha}"
    return version

setup(
    name='ovos-tts-server',
    version=get_version(),
    description='simple FastAPI server to host TTS plugins as a service',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/OpenVoiceOS/ovos-tts-server',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    license='Apache-2.0',
    packages=find_packages(),
    install_requires=required("requirements/requirements.txt"),
    package_data={"ovos_tts_server": ["examples/*"]},
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
