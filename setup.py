from setuptools import setup, find_packages

DESCRIPTION = 'A simple search engine for non-relational databases. Supports stemming and search-as-you-type.'

LONG_DESCRIPTION = None
try:
    LONG_DESCRIPTION = open('README.rst').read()
except:
    pass

setup(name='nonrel-search',
      version='0.1',
      packages=find_packages(exclude=('tests', 'tests.*',
                                      'base_project', 'base_project.*')),
      author='Thomas Wanschik',
      author_email='twanschik@googlemail.com',
      url='http://www.allbuttonspressed.com/projects/nonrel-search',
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      platforms=['any'],
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Web Environment',
          'Framework :: Django',
          'Intended Audience :: Developers',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Software Development :: Libraries :: Application Frameworks',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'License :: OSI Approved :: BSD License',
      ],
)
