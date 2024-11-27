# Changelog

All notable changes to this project will be documented in this file.

## [4.0.1]

### Added
- New AWS, GCP, and Azure parameter `--machine_name` to specify a cloud dependent machine name
- Retry on transient resource capacity errors with some Azure machine sizes 
- Added the `aws.tags` configuration setting to provide a default set of tags for AWS deployments
- Added the `ssh.key` configuration setting to provide a default SSH key
- Added the ability to create a SSH key to use with Couch Formation via `cloudmgr ssh create`

### Changed
- New project and service names must conform to RFC1035
- Project clean now removes the project root directory as well as files
- Refactored the Docker driver to no longer depend on a locally installed `host-prep-lib`

### Fixed
- Fixed the Docker driver state check to properly identify orphaned resources

## [4.0.0]

### Notes
- Couchformation 4.0 GA

### Added
- Automatic peering for Capella with AWS and GCP
- Support for Python 3.13
- Deployment stage has been added to project state
- Global configuration parameter subsystem with initial support for storing Capella settings
- Ability to use a Capella project as opposed to always using the CF project as the Capella project

### Changed
- The `show` subcommand should be used to display project IP addresses, hostnames, and credentials
- The `list` subcommand now shows which projects are in a deployed state
- The `list` subcommand output has been enhanced
- Versions going forward will be GA versions

### Fixed
- Fixed numerous bugs and refactored code to better handle exceptions
- Code cleanup

### Removed
- Prerelease code designation

## [4.0.0a390]

### Added

- Added Columnar support to the Capella driver
- Migrated Capella driver to use [`libcapella`](https://pypi.org/project/libcapella/)
- The AWS driver now supports deprecated images allowing the deployment of older OS revisions (hostprep does not support these so they need to be deployed with the `--raw` option)
- Added an `options` parameter that can be used to pass arguments to scripts that are run by a provisioner
- Added support for creating Couchbase Server clusters with memory optimized indexes via `--options memopt` optional parameter

### Changed

- Refactored regression tests

### Fixed

- Fixed several issues with Capella deployments

### Removed

- Nothing was removed in this release

## [4.0.0a380]

### Added

- Nothing new was added

### Changed

- Nothing was changed

### Fixed

- Fixed issue with AWS SSO auth if a ```sso-session``` is not configured

### Removed

- Nothing was removed in this release

## [4.0.0a370]

### Added

- Add self-signed CA to project credential package
- Added build target "cbscert" which uses project CA to create cluster and node certificates and enables cert auth
- Docker default build step to install host prep package
- Custom tag support for AWS via the ```--tags``` parameter
- Extended flag (```-E```) for list operation to show additional information such as the CA certificate in PEM format

### Changed

- Docker provisioner now respects root flag so if this is set to true steps are run as the root user

### Fixed

- Fixed issue with AWS SSO auth when multiple accounts are configured
- Fixed issue with AWS SSO auth if multiple roles are available

### Removed

- Nothing was removed in this release
