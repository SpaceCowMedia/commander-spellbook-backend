---
name: release-announcement
description: Write the Commander Spellbook Backend release announcement (changelog, release notes) for the changes since a given version. Use whenever a release announcement, changelog or release notes are asked for.
---

# Release announcement

The announcement is published verbatim, so the heading hierarchy and the two-space bullet indentation must match this skeleton exactly (`<>` wraps a replacement):

```markdown
# Commander Spellbook Backend <new version>
## API Changelog
### Breaking Changes
  * Removed ...
### Other Changes
  * Added ...
## Search Engine Changelog
## Editor Dashboard Changelog
  * Added ...
  * Changed ...
```

- Fill `<new version>` with the release version.
- Drop any heading with no entries under it.
- Keep bullets as `  * <verb> ...` (Added / Changed / Removed / Fixed).
- The `###` subheadings only separate breaking changes from the rest: when a section has no breaking changes, drop `### Other Changes` too and list its bullets straight under the `##` heading.

## Which section a change belongs to

- Variant generation changes (what ends up in generated variant texts, replacements, names) are **Editor Dashboard** changes, not API changes.
- The API Changelog is for the API contract itself: endpoints, fields, serializer shape. Auxiliary pages served next to it, such as the DRF browsable API login page, go under a separate `## Other` section.
- Leave out changes invisible to most people, such as data migrations that only normalize existing values.

## Gathering the changes

- Release tags carry a `v` prefix (`v7.0.0`); `v7`, `v7.1` and `latest` are floating tags. The new version is the latest tag on HEAD, if there is one.
- List the commits with `git log --no-merges v<old>..HEAD` and read each commit's body and diff, not just its subject.
- Leave out dependency bumps, CI changes and test-only commits unless they change behaviour someone would notice.
