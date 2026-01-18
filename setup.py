from setuptools import setup, find_packages

setup (
       name='pdb_browser',
       version='0.1',
       packages=find_packages(),

       # Declare your packages' dependencies here, for eg:
       install_requires=['Flask>=2.0', 'Flask-SQLAlchemy>=3.0', 'pymysql>=1.0'],

       # Fill in these to make your Egg ready for upload to
       # PyPI
       author='gelpi',
       author_email='',

       #summary = 'Just another Python package for the cheese shop',
       url='',
       license='',
       long_description='Long description of the package',

       # could also include long_description, download_url, classifiers, etc.

  
       )