# Frequenz Reporting API Client Release Notes

## Summary

<!-- Here goes a general summary of what this release is about -->

## Upgrading

* Update and fix readme to make use of newest release version 0.8.0

## New Features

* States can now be requested via the client and are provided through the flat iterator.
  They can be identified via their category `state`, `warning` and `error`, respectively.
  Each individual state is provided as its own sample.

* Support for states is also added to the CLI tool via the `--states` flag.

## Bug Fixes

<!-- Here goes notable bug fixes that are worth a special mention or explanation -->
