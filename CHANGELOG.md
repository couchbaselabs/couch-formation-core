# Changelog

All notable changes to this project will be documented in this file.

## [4.0.0a370]

### Added

- Add self-signed CA to project credential package
- Added build target "cbscert" which uses project CA to create cluster and node certificates and enables cert auth
- Docker default build step to install host prep package
- Custom tag support for AWS via the ```--tags``` parameter

### Changed

- Docker provisioner now respects root flag so if this is set to true steps are run as the root user

### Fixed

- Fixed issue with AWS SSO auth when multiple accounts are configured
- Fixed issue with AWS SSO auth if multiple roles are available

### Removed

- Nothing was removed in this release
