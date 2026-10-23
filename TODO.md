# To-do

## macmini: turn off the features that keep waking background daemons

`launchctl disable` doesn't stick for Apple services on macOS 15 with SIP on: launchd clears it
when a new GUI session starts (seen 2026-10-23, after a Chrome Remote Desktop login). Turn off
the features that call these daemons instead, in System Settings on the macmini:

- [ ] Find My Mac: Apple Account → iCloud → Find My Mac (stops `searchpartyuseragent`, which
      kept waking `contactsd`).
- [ ] iMessage: Messages → Settings → iMessage → Sign Out (stops `imagent` and
      `IMDPersistenceAgent`, which also wake `contactsd`).
- [ ] Spotlight: turn off Siri suggestions and the result categories you don't need
      (less work for `spotlightknowledged`).
