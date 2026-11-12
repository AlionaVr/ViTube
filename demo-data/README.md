# Demo data

Three short open-licensed videos to upload in local development and, later, for the seed (upload → processing →
playback). The worker makes their thumbnails, as for any upload.
The files are not in git: `download.py` fetches them.

```bash
python3 demo-data/download.py
```

It skips files that are already there.

| File                         | Source                                                                         | License                                                         |
|------------------------------|--------------------------------------------------------------------------------|-----------------------------------------------------------------|
| `big-buck-bunny-trailer.mp4` | [Big Buck Bunny](https://peach.blender.org/), © 2008 Blender Foundation        | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)       |
| `sintel-trailer.mp4`         | [Sintel](https://durian.blender.org/), © 2010 Blender Foundation               | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)       |
| `flower.mp4`                 | [MDN shared assets](https://github.com/mdn/shared-assets/tree/main/videos)     | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)   |

CC BY needs attribution: keep the credit line from `description` when the seed uploads a video.

## videos.json

One entry per file: download `url`, `sha256`, size in `bytes`, `duration` (s), `title` and `description` for the seed,
`author`, `license`.

## Checks

Each file was checked by hand once before its `sha256` was pinned:

- `file --mime-type`: `video/mp4` (`video/x-m4v` for the Big Buck Bunny trailer, same container);
- the MP4 boxes cover the whole file (`ftyp` first, no trailing or foreign data);
- `ffprobe`: H.264 video + AAC audio, expected duration.

`download.py` accepts only bytes with the pinned hash. To add a video, repeat the checks, then add its entry.
