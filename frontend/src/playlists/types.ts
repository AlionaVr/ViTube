// Types from the API (schema.d.ts).
import type { components } from '../api/schema'

export type Playlist = components['schemas']['PlaylistOut']

/** One of the viewer's playlists; `contains_video` is set when asked about a video. */
export type MyPlaylist = components['schemas']['MyPlaylist']

export type PlaylistItem = components['schemas']['PlaylistItemOut']

export type Visibility = components['schemas']['Visibility']

export type PlaylistCreate = components['schemas']['PlaylistCreate']
