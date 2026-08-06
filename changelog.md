# Changelog

## [Unreleased]

* Replace three dots with Ellipsis in menus

## [v0.7.5 (Kampgarten)] - 2026-07-24

* Added: platform-specific program icons
* Added: TTS message for theme selection
* Changed: On/off state of the mute and loop checkboxes is now announced when they are triggered via keyboard shortcuts.
* Changed: F6 now cycles between mode selection, deck list and active deck controls.
* Changed: Swap menu and playback buttons in active deck controls.
* Changed: Various logging improvements.
* Fixed: Added missing translations for some UI controls, e.g. Help / About window title.
* Windows installer: Remove old runtime files before updating.

## [v0.7.4 (Forelle)] - 2026-07-05
Here's whats new, brought to you by a trout in a washing machine: 

* Added: a basic sleep timer is now available in the Tools menu (Ctrl+Shift+I).
* Changed: The project manager can now save and load local files with relative paths. This makes it possible to share project folders across devices.
* Changed: The effect configuration is no longer saved for empty decks, which reduces project file size.
* Fixed: Old hardcoded deck count removed from project manager.
* Fixed: A default OK button action in Program Options has been added so that pressing Enter will now close the dialog.

## [v0.7.3 (Rohrbruch)] - 2026-05-19
I’ve decided to give every future release a quirky and totally random codename. After all, what wouldn't you do for a bit of attention? 'Rohrbruch' is the german word for burst pipe. It came about during a Codex conversation when the assistant told me that he had fixed a leak in my code, and used the rather ununsual german word 'Leckage' for this. So let the water flow!
 
### What's new

* Add a 'Play' checkbox to the decklist. You can now conveniently activate every deck by pressing the space bar.
* Added an output device submenu to the deck main menu.
* Various logging improvements.
* Improved error handling for non-existent files in projects.
* Correctly restore previous settings after closing the options dialogue via Cancel or Escape. 
* Improved TTS support on Linux.
* Bump InnoSetup to v7.0 and make Windows installer fully 64-bit compatible.

## [v0.7.2] - 2026-05-08
This release continues the series of improvements to features that have already been implemented. Here's what's changed: 

* Improvements to VST3 support
    * The ability to load VST3 bundles has been added. These are usually saved as a folder with the extension '*.vst3'.
    * Fixed accidental loading of VST instruments; these will now be correctly removed from effect chains after an attempt to load them.
* New TTS module
    * Switch TTS backend from Pyttsx3 to Prism.
    * Depending on platform support, you can now select whether TTS messages should be spoken through your preferred screen reader or the system voice (OneCore, SAPI, etc.). 

## [v0.7.1] - 2026-05-05

### What's new?

* The internationalisation module has been improved.
    * The available languages are no longer hard-coded and will be loaded if an appropriate language folder containing a .mo file is present in the locales directory. 
    * A system language selection has been added to automatically detect the interface language.
* Some hidden UI options have been added to config.ini.
    * `deck_list_focus`: Controls whether MultiDeck should set the keyboard focus on the deck list when it starts, othervise the focus hits the mode selection (Default: True). 
    * `force_dataview`: to ensure the best accessibility on all operating systems, MultiDeck uses a platform-specific control to display the deck list. This option forces the use of a DataView control to display the deck list if the operating system cannot be detected or if this is explicitly requested (default: False).

## [v0.7.0] - 2026-04-24

### What's new

* Added live streaming support
    * Configure the credentials of an Icecast2-compatible server on the Streaming tab in Program Options.
    * Start/stop the live stream by pressing F8 or using the corresponding option in the global playback controls or the Tools menu. 
* Added a dummy sound output device for silent output in pure streaming setups.
* Added the ability to set an intro audio file for each deck, e.g. for station announcements in automatic mode. 

### Changed:

* Made the multi-column list view fully accessible on Linux and probably Mac OS. 
* The old compact list view has been removed; multi-column is now the default. 
* Various other GUI improvements.

## [v0.6.0] - 2026-04-20

This should have been a release focused purely on code quality, but it also ended up including some new features. 

### What's new

* Added multiroom mode
    * This is a special variant of mixer mode that allows each deck to have its own sound device.
    * Select the desired output device from the deck's context menu. Changes take effect immediately.
    * The remaining modes work as usual. 
* A multi-column deck list view has been added. 
    * Select your preferred list view in the General tab of the Program Options.
    * Linux and MacOS use a DataView list control because the native list control is not accessible on these systems.
* A deck menu and playback menu have been added for users who prefer menu bar navigation. 
* Play/pause and stop shortcuts have been added for all decks and for individual decks. 
* The options dialogue shortcut has been changed to Ctrl+Shift+O.
* The allowed deck count has been increased to 128. The default count remains at 10 decks. 
* The command line interface has been added to the compiled packages. 

## [v0.5.0] - 2026-04-09

### Whats new

* Text-to-speech event announcements can be activated in preferences. 
* Replaced the shortcuts file with a more comprehensive user documentation, press F1 to access. 
* Added Windows installer. 

### Fixed

* Crossfade duration setting in automation preferences no longer uses tenths, and is now fully accessible.
* A problem in level-based switching has been fixed where the setting was still enabled when it shouldn't have been. 

## [v0.4.0] - 2026-03-04

### New features

* Support for VST3 effects has been added, but it is still very experimental. 
* Added streaming of sound card inputs, accessible via the deck's context menu or by pressing Ctrl+D. 

### Changed:

* Replaced tabs with ListView in options and effects dialogues, allowing first-letter navigation.
* Split effect chains into built-in effects and VST plugins.
* Remove the menu ellipsis from translations to avoid duplicate strings.

### Binaries

* `multideck_win64.zip`: Windows 64 bit
* `multideck_linux_x64.tar.gz`: Linux 64 bit, built on Debian 13. 

## [v0.3.1] - 2026-02-16

### Whats new

* Added level-based switching to automation mode
  * New configuration options in automation tab for threshold, hysteresis and hold time.
* Added a level meter with visual and dB indicator to main window.

### Fixed

* Linux: Fixed GTK-related accessibility issues and warnings.

## [v0.3.0] - 2026-02-05
What's new: 

* Enhance cross-platform compatibility
* Added a key down event handler to the deck listbox to allow opening the context menu with Enter, Return, or the Application/Menu key. This improves accessibility, particularly for VoiceOver users on macOS who cannot trigger the context menu via the standard event.
* Introduces a new CLI (src/cli.py) for running MultiDeck in headless mode, suitable for server or script integration. Only supports loading .mdap project files at the moment.
* Options: Add per-tab Apply behavior and change detection to the Options dialog, allowing users to apply a single section without closing the dialog. 
* Make all dialog buttons translatable throughout the app.
* Added optional recording of individual decks.
* Added some basic audio effects (Ctrl+Shift+E), powered by Spotify Pedalboard library. Effect configuration is saved in project files and will be restored upon opening a project.

## [v0.2.3] - 2026-01-27

* Project management: Track mixer and deck modifications and prompt users to save changes when opening, closing or creating new projects.
* Add an unsaved indicator to the window title.
* Add M3U import and export.
* Remove the redundant deck menu leftovers from the old GUI.
* Fix some menu shortcuts for the German locale.

## [v0.2.2] - 2026-01-25
This release is primarily focused on accessibility.

* More keyboard shortcuts have been added to perform various actions. 
* Improved readability in dark mode. 
* Added time seeking to the player controls. 

## [v0.2.1] - 2026-01-23
* Fix player controls and deck selection not being updated in automatic mode
* Fix mode selection in project files.

## [v0.2.0] - 2026-01-22
completely redesigned the deck panel. The individual decks have been replaced by a selection list accessible via F6 where you can select the deck using the cursor keys or first letter navigation. In solo and automatic mode, the sound immediately switches to the selected deck upon selection.

## [v0.1.0] - 2026-01-20
First release.
