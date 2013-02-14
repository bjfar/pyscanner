from distutils.core import setup

setup(
    name='PyScanner',
    version='0.1.0',
    author='Benjamin Farmer',
    author_email='ben.farmer@gmail.com',
    packages=['pyscanner', 'pyscanner.test','pyscanner.common'],
    scripts=['bin/example.py'],
    url='http://pypi.python.org/pypi/PyScanner/', #not really, just an example
    license='LICENSE.txt',
    description='A collection of tools for performing Bayesian model comparison and parameter estimation, using the MultiNest 2.12 engine',
    long_description=open('README.txt').read(),
    install_requires=[
        "MultiNest == 2.12",
    ],
)
