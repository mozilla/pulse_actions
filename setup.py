from setuptools import setup, find_packages

deps = [
    'ijson==2.2',
    'mozci==0.16.0',
    'MozillaPulse==1.2.2',
    'requests==2.7.0',
    'taskcluster==0.0.29',
    'treeherder-client==1.7.0',
]

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
      install_requires=deps,
      url='https://github.com/adusca/pulse_actions',
      entry_points={
          'console_scripts': [
              'run-pulse-actions = pulse_actions.worker:main'
              ],
          })
