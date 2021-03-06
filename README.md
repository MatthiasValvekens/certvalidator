# certvalidator
Forked from [wbond/certvalidator](https://github.com/wbond/certvalidator), with patches for [pyHanko](https://github.com/MatthiasValvekens/pyHanko).

A Python library for validating X.509 certificates or paths. Supports various
options, including: validation at a specific moment in time, whitelisting and
revocation checks.

 - [Features](#features)
 - [Related Crypto Libraries](#related-crypto-libraries)
 - [Current Release](#current-release)
 - [Dependencies](#dependencies)
 - [Installation](#installation)
 - [License](#license)
 - [Documentation](#documentation)
 - [Continuous Integration](#continuous-integration)
 - [Testing](#testing)
 - [Development](#development)
 - [CI Tasks](#ci-tasks)


## Features

 - X.509 path building
 - X.509 basic path validation
   - Signatures
     - RSA (including PSS padding), DSA and EC algorithms
   - Name chaining
   - Validity dates
   - Basic constraints extension
     - CA flag
     - Path length constraint
   - Key usage extension
   - Extended key usage extension
   - Certificate policies
     - Policy constraints
     - Policy mapping
     - Inhibit anyPolicy
   - Failure on unknown/unsupported critical extensions
 - TLS/SSL server validation
 - Whitelisting certificates
 - Blacklisting hash algorithms
 - Revocation checks
   - CRLs
     - Indirect CRLs
     - Delta CRLs
   - OCSP checks
     - Delegated OCSP responders
   - Disable, require or allow soft failures
   - Caching of CRLs/OCSP responses
 - CRL and OCSP HTTP clients
 - Point-in-time validation
 - Name constraints

## Current Release

![pypi](https://img.shields.io/pypi/v/pyhanko-certvalidator.svg) - [changelog](changelog.md)

## Dependencies

 - *asn1crypto*
 - *cryptography*
 - *uritools*
 - *oscrypto*
 - *requests*
 - Python 3.7, 3.8 or 3.9

## Installation

```bash
pip install pyhanko-certvalidator
```

## License

*certvalidator* is licensed under the terms of the MIT license. See the
[LICENSE](LICENSE) file for the exact license text.

## Documentation

[*certvalidator* documentation](docs/readme.md)

## Continuous Integration

Various combinations of platforms and versions of Python are tested via:

 - [GitHub Actions](https://github.com/MatthiasValvekens/certvalidator/actions)

## Testing

Tests are written using `unittest` and require no third-party packages.

Depending on what type of source is available for the package, the following
commands can be used to run the test suite.

### Git Repository

When working within a Git working copy, or an archive of the Git repository,
the full test suite is run via:

```bash
python run.py tests
```

To run only some tests, pass a regular expression as a parameter to `tests`.

```bash
python run.py tests path
```

### PyPi Source Distribution

When working within an extracted source distribution (aka `.tar.gz`) from
PyPi, the full test suite is run via:

```bash
python setup.py test
```

### Test Cases

The test cases for the library are comprised of:

 - [Public Key Interoperability Test Suite from NIST](http://csrc.nist.gov/groups/ST/crypto_apps_infra/pki/pkitesting.html)
 - [OCSP tests from OpenSSL](https://github.com/openssl/openssl/blob/master/test/recipes/80-test_ocsp.t)
 - Various certificates generated for TLS certificate validation

## Development

To install the package used for linting, execute:

```bash
pip install --user -r requires/lint
```

The following command will run the linter:

```bash
python run.py lint
```

To install the packages requires to generate the API documentation, run:

```bash
pip install --user -r requires/api_docs
```

The documentation can then be generated by running:

```bash
python run.py api_docs
```

The following will run a test that connects to all (non-adult) sites in the
Alexa top 1000 that respond on port 443:

```bash
python run.py stress_test
```

Once the script is complete, results that differ between the OS validation and
the *certvalidator* validation will be listed for further debugging.

To change the version number of the package, run:

```bash
python run.py version {pep440_version}
```

To install the necessary packages for releasing a new version on PyPI, run:

```bash
pip install --user -r requires/release
```

Releases are created by:

 - Making a git tag in [PEP 440](https://www.python.org/dev/peps/pep-0440/#examples-of-compliant-version-schemes) format
 - Running the command:

   ```bash
   python run.py release
   ```

Existing releases can be found at https://pypi.org/project/pyhanko-certvalidator.
