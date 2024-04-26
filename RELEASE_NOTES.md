# Frequenz Reporting API Client Release Notes

## Summary

## Upgrading

* The `ReportingClient` is renamed to `ReportingApiClient`.

* The client method `iterate_single_component` is renamed to `list_single_component_data`.

## New Features

* The client method `list_microgrid_components_data` is added to
expose the functionality of supporting arbitrary lists of microgrid-component IDs
and metric IDs. It is intended to be as close as possible on the gRPC function call.

## Bug Fixes

