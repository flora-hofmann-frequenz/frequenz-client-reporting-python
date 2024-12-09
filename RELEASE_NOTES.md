# Frequenz Reporting API Client Release Notes

## Summary

<!-- Here goes a general summary of what this release is about -->

## Upgrading

* Update repo-config and setuptools versions
* Timestamps in the response are now timezone aware.

## New Features

* Support for streaming: By omitting the end date in the request,
  the client will return any historical data from timestamp until now and
  keep streaming new data as it arrives.
* Also the start date can be omitted which let's the data start at the
  earliest time stamp that is available.

## Bug Fixes

<!-- Here goes notable bug fixes that are worth a special mention or explanation -->
