# Demo data

Three short open-licensed videos for local development and, later, the seed (upload → processing → playback).
The files are not in git: `download.py` fetches them and renders thumbnails.

```bash
python3 demo-data/download.py   # needs Docker for the thumbnails
```

It skips files that are already there. A thumbnail is rendered again only if its video is newer.

| File                         | Source                                                                         | License                                                         |
|------------------------------|--------------------------------------------------------------------------------|-----------------------------------------------------------------|
| `big-buck-bunny-trailer.mp4` | [Big Buck Bunny](https://peach.blender.org/), © 2008 Blender Foundation        | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)       |
| `sintel-trailer.mp4`         | [Sintel](https://durian.blender.org/), © 2010 Blender Foundation               | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)       |
| `flower.mp4`                 | [MDN shared assets](https://github.com/mdn/shared-assets/tree/main/videos)     | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)   |

CC BY needs attribution: keep the credit line from `description` when the seed uploads a video.

## videos.json

One entry per file: download `url`, `sha256`, size in `bytes`, `duration` (s), `title` and `description` for the seed,
`author`, `license`, `thumbnails_at` (seconds) and an optional `crop` that drops letterbox bars. The times were
picked by eye: no black frames, title cards or transitions.

## Checks

Each file was checked by hand once before its `sha256` was pinned:

- `file --mime-type`: `video/mp4` (`video/x-m4v` for the Big Buck Bunny trailer, same container);
- the MP4 boxes cover the whole file (`ftyp` first, no trailing or foreign data);
- `ffprobe`: H.264 video + AAC audio, expected duration.

`download.py` accepts only bytes with the pinned hash. To add a video, repeat the checks, then add its entry.

Thumbnails come from ffmpeg in a container with no network, a read-only root and read-only videos; it can write only
to `thumbnails/`.
