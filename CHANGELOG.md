# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - Unreleased

### Changed

- Update dependencies
  - ImageHash to 4.3.0
  - python-telegram-bot to 13.14
  - python-dotenv to 0.21.0

## [0.5.0] - 2022-07-04

### Added

- Auto-delete reposts, toggleable with `/toggle autodelete`
- Auto call out reposts, toggleable with `/toggle autocallout`
- Remove more strings from code and put into config file
- Made script to migrate group data files from <=0.4.0 to 0.5.0 format

### Changed

- Use ujson library to try and help with performance
- Revert interaction of URL and picture tracking settings and repost processing
  - When toggled off, messages containing those entities will not be acknowledged at all

### Fixed

- Fix picture download timer not measuring time correctly.
- Fix error when getting sender ID.
- Update dependencies.

### Security

- Update Pillow to 9.2.0

## [0.4.0] - 2021-11-20

### Added

- Added CLI flag to load Telegram token and bot admin ID from environment variables.

### Fixed

- README formatting consistency.

## [0.3.3] - 2021-10-25

### Changed

- Use group's title rather than "Anonymous Admin".

### Fixed

- Fix bot not being able to run solely from defaultconfig.yaml if all required variables are provided in it.
- Revise README to be more descriptive.
- Fix RepostBot still not being able to reply in channels.

## [0.3.2] - 2021-09-22

### Fixed

- Channel repost detection and callouts implemented.
- Admins posting anonymously will be referred to as "Anonymous Admin".
  - Anonymous admins also have ability to reset RepostBot data.
- Update dependencies.
- Update README commands and installation instructions

## [0.3.1] - 2021-06-22

### Fixed

- Fix `/whitelist` command failing when called.

## [0.3.0] - 2021-06-21

### Added

- Add `/stats` command to display number of unique images and URLs and how many total reposts in those separate categories.

### Fixed

- Fix `/toggle` and `/settings` commands falling under same flood protection key, preventing one from being called shortly after the other.

## [0.2.2] - 2021-06-16

### Fixed

- Revise requirements.txt to have only what's needed for the bot.

### Security

- Bumped Pillow version.

## [0.2.1] - 2021-04-24

### Fixed

- Fix user-defined repost strategies not being obtained correctly.
- Fix bug with verbose callout strategy.

## [0.2.0] - 2021-04-05

### Added

- Per-user flood protection on commands and per-group flood protection on repost callouts.
- Allow configuration of repost callout styles.