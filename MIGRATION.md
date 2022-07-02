# Migration Guide

## <0.4.x to 0.5.0

### What changed?

- Group data structure changes: key name "track" changed to "toggles" and a "deleted" section is added

Run the migrate-to-0.5.0.py script in the scripts folder and include the name of your config file:\
`python scripts/migrate-to-0.5.0.py config.yaml`

If you don't pass the config file argument, the script will look for config.yaml or defaultconfig.yaml in the current folder and in the config folder.