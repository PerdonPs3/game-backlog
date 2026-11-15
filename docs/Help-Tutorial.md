# Add game Help demonstration

The first Library question on `/help` contains a silent 30-second MP4 tutorial.
It uses captures of the real local interface with a fictional account and
Celeste on Linux. The sequence shows each typed character, result selection,
platform and status menus, a half-star rating, scrolling, saving, and the
resulting library entry. Pointer movement, click rings, short crossfades and
interpolated page scrolling keep the sequence continuous. Native select menus
are recreated from the actual option labels because browser captures omit OS
popup surfaces. This is an edited guided sequence, not a continuous recording.
No real account data or provider credentials appear in the clip.

The local H.264 MP4 supports native pause, seek, fullscreen and captions, plus a
Replay button. The answer expands over 380 ms and playback starts after a
two-second reading pause. Closing, filtering or hiding the tab cancels a pending
start; manual playback and Replay start immediately. It loads when the answer opens, pauses on closing, filtering out
the answer or hiding the tab, and does not autoplay with reduced motion enabled.
The ordinary text instructions remain usable without JavaScript or video.

Assets live in `app/static/videos/help-add-game.*`, with the WebP poster beside
them. The MP4 is approximately 2.6 MiB at 1280 × 800 and 30 fps, with fast-start
metadata. The dark demonstration remains the same in both site themes.

To refresh it after form changes, capture the same stages in a disposable
local account through the browser and run `scripts/build_help_demo.py` with the
capture directory. This development-only script needs Pillow, imageio-ffmpeg
and the Windows Segoe UI font; none are runtime dependencies of the website.
Capture filenames and pointer targets are defined in the script. Review every
stage and its captions when recapturing; do not reuse personal profile captures.

Validation: six Python Help tests, five JavaScript behavior tests, and browser
checks for real MP4 decoding, deferred loading, delayed playback, pause/replay
and mobile layout. Timer regressions cover quick reopening, manual playback,
reduced motion, filtering and hidden tabs.
The implementation remains local until publication is authorized.
