#!/usr/bin/env python3
from setuptools import setup, find_packages
from os import path, environ

BASE_PATH = path.abspath(path.dirname(__file__))


def required(requirements_file):
    """
    Load a requirements file relative to the project base and return a cleaned list of package requirement strings.
    
    If the environment variable `MYCROFT_LOOSE_REQUIREMENTS` is set, convert strict version specifiers (`==`, `~=`) to `>=` before filtering. Blank lines and comment lines beginning with `#` are removed.
    
    Parameters:
        requirements_file (str): Path to the requirements file relative to the project's base path.
    
    Returns:
        list[str]: A list of requirement lines suitable for use in package installation.
    """
    with open(path.join(BASE_PATH, requirements_file), 'r') as f:
        requirements = f.read().splitlines()
        if 'MYCROFT_LOOSE_REQUIREMENTS' in environ:
            print('USING LOOSE REQUIREMENTS!')
            requirements = [r.replace('==', '>=').replace('~=', '>=') for r in requirements]
        return [pkg for pkg in requirements
                if pkg.strip() and not pkg.startswith("#")]


with open(path.join(BASE_PATH, "README.md"), "r") as f:
    long_description = f.read()

def get_version():
    """
    Determine the package version from ovos_tts_server/version.py.
    
    Reads version components and returns a version string in the form "major.minor.build".
    If the alpha component is greater than zero, appends an "a" suffix followed by the alpha number.
    
    Returns:
        str: The computed version string, e.g. "1.2.3" or "1.2.3a1".
    """
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
        'License :: OSI Approved :: Apache Software License',
    ],
    keywords='plugin TTS OVOS OpenVoiceOS',
    entry_points={
        'console_scripts': [
            'ovos-tts-server=ovos_tts_server.__main__:main'
        ]
    }
)