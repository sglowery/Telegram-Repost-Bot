# Migration Guide

You must go through all the migrations, e.g. if your version was 0.3.0, you must migrate to 0.5.0, init the database, then migrate to 0.6.0

## \>=0.5.0 to 0.6.0

### What changed?

- Storing repost, whitelist and deleted message data in a database and only group settings in JSON.

Open a terminal at the project root. Use your venv's python.exe:

`venv/scripts/python.exe scripts/init_db.py`

This will create the database. Then, migrate your group data to the database and the new JSON format:

(This step is destructive! Your data will be deleted from the JSON files. Back it up if you are worried about losing it.)

`venv/scripts/python.exe scripts/migrate-to-db.py`

This will try to find your group data, add it to the database, and then cull the unneeded data from the JSON files.

You should be able to run RepostBot normally at this point

## <=0.4.x to 0.5.0

### What changed?

- Group data structure changes: key name "track" changed to "toggles" and a "deleted" section is added

Run the migrate-to-0.5.0.py script in the scripts folder and include the name of your config file:\
`python scripts/migrate-to-0.5.0.py config.yaml`

If you don't pass the config file argument, the script will look for config.yaml or defaultconfig.yaml in the current folder and in the config folder.