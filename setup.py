from setuptools import setup, find_packages

deps = [
    'mozillapulse',
    'mozci>=0.7.0',
    'requests',
]

setup(name='pulse-actions',
      version='0.1.3',
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
