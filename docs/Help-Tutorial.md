# Add game Help demonstration

The first Library question on `/help` contains a silent 15-second MP4 tutorial.
It uses six captures of the real local interface with a fictional account and
Celeste on Nintendo Switch. The sequence covers search, result selection,
platform/status, optional rating/notes, saving, and the resulting library entry.
An animated pointer and click rings guide attention; this is an edited sequence
of real captures, not a continuous screen recording. No real account data or
provider credentials appear in the clip.

The local H.264 MP4 supports native pause, seek, fullscreen and captions, plus a
Replay button. It loads when the answer opens, pauses on closing, filtering out
the answer or hiding the tab, and does not autoplay with reduced motion enabled.
The ordinary text instructions remain usable without JavaScript or video.

Assets live in `app/static/videos/help-add-game.*`, with the WebP poster beside
them. The MP4 is approximately 620 KiB at 1280 × 800 and 24 fps, with fast-start
metadata. The dark demonstration remains the same in both site themes.

To refresh it after form changes, capture the same six stages in a disposable
local account through the browser and run `scripts/build_help_demo.py` with the
capture directory. This development-only script needs Pillow, imageio-ffmpeg
and the Windows Segoe UI font; none are runtime dependencies of the website.
Capture filenames and pointer targets are defined in the script. Review every
stage and its captions when recapturing; do not reuse personal profile captures.

Validation: six Python Help tests, three JavaScript behavior tests, and browser
checks for real MP4 decoding, deferred loading, pause/replay and mobile layout.
The implementation remains local until publication is authorized.
