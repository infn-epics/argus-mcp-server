# ADR 0002: ChannelFinder as the Device metadata source of truth

## Status

Accepted.

## Context

ARGUS is device-centric: a `Device` (e.g. quadrupole QF12) has PVs, an IOC,
a Kubernetes pod/namespace, a git repo, documentation, rack, and owner.
Something has to map a device name to all of that. The options considered:

1. A new static registry (e.g. `config/devices.yaml`) owned by ARGUS.
2. ChannelFinder, the existing EPICS-ecosystem PV/device metadata registry
   (already in the provider list), using its `properties`/`tags` on channels.

## Decision

Use ChannelFinder as the single source of truth. A `device` property groups
channels under one device name; well-known optional properties
(`deviceClass`, `iocName`, `rack`, `owner`, `k8sNamespace`, `k8sPod`,
`argocdApp`, `gitRepo`, `docRef`) populate the rest of the `Device` model.
`DeviceService.resolve_device()` is the only place this mapping happens.

If ChannelFinder is unconfigured or a name isn't found there, `resolve_device`
falls back to a minimal `Device(name=X, pv_names=[X])` built from the bare
name — `get_pv`/`diagnose_device` still work against an ungrouped PV, just
without cross-system enrichment.

## Consequences

- No second metadata store to keep in sync with what control-room engineers
  already curate in ChannelFinder.
- Device richness is bounded by what's actually tagged in ChannelFinder —
  sites with sparse tagging get sparse `Device` objects, not errors.
- If a future site doesn't run ChannelFinder at all, per-PV operations still
  work; only the device-centric tools (`get_device`, `diagnose_device`,
  `beamline_status`) lose their cross-system enrichment gracefully.
