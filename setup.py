import os
from setuptools import setup, find_packages

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(name='pulse-actions',
      version='0.2.2',
      description='A pulse listener that acts upon messages with mozci.',
      classifiers=['Intended Audience :: Developers',
                   'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
                   'Natural Language :: English',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Software Development :: Libraries :: Python Modules',
                   ],
      author='Alice Scarpa',
      author_email='alicescarpa@gmail.com',
      license='MPL 2.0',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=required,
      url='https://github.com/mozilla/pulse_actions',
      entry_points={
          'console_scripts': [
              'run-pulse-actions = pulse_actions.worker:main'
              ],
          })
