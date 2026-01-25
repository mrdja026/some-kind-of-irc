# Change: Update media image variants

## Why
Large image uploads should preserve an original copy while serving a downscaled display version to reduce bandwidth and improve UI performance.

## What Changes
- Store an original image variant capped at 3840x2160.
- Store a display image variant capped at 1920x1080.
- Preserve aspect ratio and avoid upscaling.
- Return only the display variant key and URL in the upload response.

## Impact
- Affected specs: media-storage
- Affected code: media-storage/app.py, media-storage/requirements.txt

## Known Issues
- **HIGH**: WebSocket realtime and typing indicators can fail after login until a page reload.
