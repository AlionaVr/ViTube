// Demo catalog: made-up channels and videos around the three open films in demo-data/.
// Every entry plays a real file and shows a real frame of it.
import type { Category } from '../videos/types'

// Mirrors demo-data/videos.json: file, duration, thumbnails_at.
const MEDIA = {
  bunny: {
    file: 'big-buck-bunny-trailer.mp4',
    duration: 33,
    frames: [5, 10, 15.25, 16.5, 20.5, 21.5, 25.25, 26.25],
  },
  sintel: { file: 'sintel-trailer.mp4', duration: 52.2, frames: [7, 13, 14.5, 23, 29, 34, 38] },
  flower: { file: 'flower.mp4', duration: 5.1, frames: [0.5, 2.5, 3.5, 4.75] },
} as const

export type MediaKey = keyof typeof MEDIA

const CREDITS: Record<MediaKey, string> = {
  bunny: 'Footage: Big Buck Bunny, © 2008 Blender Foundation, www.bigbuckbunny.org. CC BY 3.0.',
  sintel: 'Footage: Sintel, © 2010 Blender Foundation, durian.blender.org. CC BY 3.0.',
  flower: 'Footage: MDN Web Docs shared assets. Public domain (CC0).',
}

export function mediaUrl(media: MediaKey): string {
  return `/demo-data/videos/${MEDIA[media].file}`
}

export function thumbnailUrl(media: MediaKey, frame: number): string {
  const { file, frames } = MEDIA[media]
  return `/demo-data/thumbnails/${file.replace('.mp4', '')}-${frames[frame]}.jpg`
}

export function mediaDuration(media: MediaKey): number {
  return MEDIA[media].duration
}

export interface MockChannel {
  handle: string
  name: string
  subscribers: number
}

export const CHANNELS = {
  openmovies: { handle: 'openmovieclub', name: 'Open Movie Club', subscribers: 182_400 },
  frame: { handle: 'framebyframe', name: 'Frame by Frame', subscribers: 1_240_000 },
  render: { handle: 'renderfarmdiaries', name: 'Render Farm Diaries', subscribers: 48_300 },
  bloom: { handle: 'slowbloom', name: 'Slow Bloom', subscribers: 9_870 },
  dragon: { handle: 'dragonnotes', name: 'Dragon Notes', subscribers: 356_000 },
  kinoteka: { handle: 'kinoteka', name: 'Кинотека', subscribers: 412_000 },
  meadow: { handle: 'pixelmeadow', name: 'Pixel Meadow', subscribers: 77_400 },
  beats: { handle: 'storybeats', name: 'Story Beats', subscribers: 23_100 },
  multrazbor: { handle: 'multrazbor', name: 'Мультразбор', subscribers: 128_000 },
  score: { handle: 'soundofshorts', name: 'Sound of Shorts', subscribers: 5_420 },
  macro: { handle: 'macrogarden', name: 'Macro Garden', subscribers: 61_900 },
  indie: { handle: 'indieanimationweekly', name: 'Indie Animation Weekly', subscribers: 2_310_000 },
} satisfies Record<string, MockChannel>

export type ChannelKey = keyof typeof CHANNELS

/** Any signed-in viewer starts subscribed to these (one shared demo state). */
export const INITIAL_SUBSCRIPTIONS: ChannelKey[] = ['frame', 'dragon', 'bloom', 'multrazbor']

export const CATEGORIES: Category[] = [
  { id: 'animation', name: 'Animation' },
  { id: 'film', name: 'Film analysis' },
  { id: 'nature', name: 'Nature' },
  { id: 'tutorials', name: 'Tutorials' },
  { id: 'music', name: 'Music' },
  { id: 'trailers', name: 'Trailers' },
]

export interface MockVideo {
  title: string
  channel: ChannelKey
  media: MediaKey
  /** Index into the media's thumbnail frames. */
  frame: number
  category: string
  views: number
  /** Age in hours. */
  age: number
  description: string
  /** Part already watched by a signed-in viewer, 0..1. */
  watched?: number
}

const DAY = 24
const WEEK = 7 * DAY
const MONTH = 30 * DAY
const YEAR = 365 * DAY

// The order is the home feed's "recommended" order.
const ENTRIES: MockVideo[] = [
  {
    title: 'Big Buck Bunny – trailer',
    channel: 'openmovies',
    media: 'bunny',
    frame: 1,
    category: 'trailers',
    views: 2_384_112,
    age: 3 * YEAR,
    description: 'A giant rabbit takes revenge on three bullying rodents.',
  },
  {
    title: 'How Big Buck Bunny’s fur was rendered in 2008',
    channel: 'frame',
    media: 'bunny',
    frame: 3,
    category: 'animation',
    views: 412_908,
    age: 5 * DAY,
    description:
      'Millions of hairs, no GPU render farm, and a deadline. We look at the hair system, the shading tricks and what still holds up today.\n\n0:00 Intro\n0:12 The hair system\n0:24 Shading',
    watched: 0.4,
  },
  {
    title: 'Three rodents, one rabbit: comedic timing breakdown',
    channel: 'beats',
    media: 'bunny',
    frame: 2,
    category: 'film',
    views: 38_204,
    age: 2 * WEEK,
    description:
      'Why the jokes land: setup, pause, payoff. A beat-by-beat look at the bullies’ first scene.',
  },
  {
    title: 'Sintel – trailer',
    channel: 'openmovies',
    media: 'sintel',
    frame: 3,
    category: 'trailers',
    views: 1_920_441,
    age: 2 * YEAR,
    description: 'A lone girl searches for the baby dragon she once saved.',
  },
  {
    title: 'Sintel’s dragon: a design story',
    channel: 'dragon',
    media: 'sintel',
    frame: 5,
    category: 'film',
    views: 96_312,
    age: 9,
    description:
      'From the first sketches to the final rig. How the team kept a dragon readable at every size, from a baby in a cage to a giant in the sky.',
  },
  {
    title: 'Five seconds of spring: a portulaca opens',
    channel: 'bloom',
    media: 'flower',
    frame: 3,
    category: 'nature',
    views: 5_812,
    age: 18,
    description: 'Shot over forty minutes, played back in five. No music, just the flower.',
  },
  {
    title: 'Разбор: как устроена комедия в Big Buck Bunny',
    channel: 'multrazbor',
    media: 'bunny',
    frame: 5,
    category: 'film',
    views: 64_200,
    age: 4 * DAY,
    description:
      'Почему шутки работают без единого слова. Разбираем паузы, мимику и то, как камера помогает гэгу.',
  },
  {
    title: 'Snow, fire, desert: color scripts in Sintel',
    channel: 'dragon',
    media: 'sintel',
    frame: 0,
    category: 'film',
    views: 143_870,
    age: 3 * WEEK,
    description:
      'Each act of Sintel has its own palette. We line up the color script next to the final frames and see how mood follows color.',
    watched: 1,
  },
  {
    title: 'Lighting a meadow like Blender Studio',
    channel: 'meadow',
    media: 'bunny',
    frame: 0,
    category: 'tutorials',
    views: 21_440,
    age: 6 * DAY,
    description:
      'Sun, sky and a bit of fake bounce light. A step-by-step setup you can copy into your own scene.',
  },
  {
    title: 'Macro lens settings for flower timelapses',
    channel: 'macro',
    media: 'flower',
    frame: 1,
    category: 'tutorials',
    views: 133_012,
    age: 2 * MONTH,
    description:
      'Aperture, focus stacking and how to keep the frame steady for an hour. Settings for three budget lenses.',
  },
  {
    title: 'Синтел: почему этот короткий метр трогает до сих пор',
    channel: 'kinoteka',
    media: 'sintel',
    frame: 2,
    category: 'film',
    views: 287_455,
    age: 1 * MONTH,
    description:
      'Пятнадцать минут, один персонаж и финал, который помнят годами. Говорим о драматургии короткого метра.',
  },
  {
    title: 'Why squash and stretch still matters',
    channel: 'frame',
    media: 'bunny',
    frame: 7,
    category: 'animation',
    views: 881_230,
    age: 4 * MONTH,
    description:
      'The oldest principle of animation, explained with modern 3D. Side-by-side comparisons included.',
  },
  {
    title: 'The orchestral score of Sintel',
    channel: 'score',
    media: 'sintel',
    frame: 1,
    category: 'music',
    views: 3_204,
    age: 11 * DAY,
    description:
      'Themes, leitmotifs and the big swell in the final scene. A listening guide for non-musicians.',
  },
  {
    title: 'Character design of the three rodents',
    channel: 'indie',
    media: 'bunny',
    frame: 4,
    category: 'animation',
    views: 1_502_877,
    age: 8 * MONTH,
    description:
      'Shape language for villains who are also funny. We redraw each rodent from scratch.',
  },
  {
    title: 'Why red flowers open at noon',
    channel: 'bloom',
    media: 'flower',
    frame: 2,
    category: 'nature',
    views: 742,
    age: 3 * DAY,
    description: 'Light, warmth and pollinators. A short answer with a five-second demo.',
  },
  {
    title: 'Sword fight choreography for animators',
    channel: 'frame',
    media: 'sintel',
    frame: 4,
    category: 'tutorials',
    views: 255_610,
    age: 7 * WEEK,
    description:
      'Blocking a duel so it reads at full speed. Thumbnails, timing charts and the big mistakes to avoid.',
  },
  {
    title: 'Behind the render farm: ten frames a night',
    channel: 'render',
    media: 'sintel',
    frame: 3,
    category: 'animation',
    views: 17_930,
    age: 5 * MONTH,
    description:
      'What rendering an open movie looked like on 2010 hardware, and what changed since.',
  },
  {
    title: 'The butterfly scene, shot by shot',
    channel: 'beats',
    media: 'bunny',
    frame: 6,
    category: 'film',
    views: 9_442,
    age: 2 * DAY,
    description: 'Twelve shots, forty seconds. How the edit builds sympathy before the cruelty.',
  },
  {
    title: 'Цветение за 5 секунд — макросъёмка дома',
    channel: 'macro',
    media: 'flower',
    frame: 0,
    category: 'nature',
    views: 48_120,
    age: 3 * WEEK,
    description: 'Снимаем таймлапс цветка на подоконнике: свет, штатив, интервал и монтаж.',
  },
  {
    title: 'Rendering sand dunes that feel endless',
    channel: 'meadow',
    media: 'sintel',
    frame: 6,
    category: 'tutorials',
    views: 66_078,
    age: 9 * MONTH,
    description:
      'Displacement, atmosphere and scale cues. Build a desert that looks a hundred kilometers wide.',
  },
  {
    title: 'Open movies you can legally remix',
    channel: 'openmovies',
    media: 'bunny',
    frame: 1,
    category: 'trailers',
    views: 324_501,
    age: 1 * YEAR,
    description:
      'Big Buck Bunny, Sintel, Tears of Steel and more: where to get them and what the licenses allow.',
  },
  {
    title: 'Writing a sad ending in fifteen minutes of screen time',
    channel: 'beats',
    media: 'sintel',
    frame: 2,
    category: 'film',
    views: 12_870,
    age: 10 * DAY,
    description:
      'Short films have no time for a slow goodbye. Three techniques Sintel uses to earn its ending.',
  },
  {
    title: 'Score breakdown: playful woodwinds',
    channel: 'score',
    media: 'bunny',
    frame: 6,
    category: 'music',
    views: 1_108,
    age: 6 * WEEK,
    description: 'Bassoon jokes and clarinet chases. How the music tells you it is safe to laugh.',
  },
  {
    title: 'Полёт дракона: как анимировали крылья',
    channel: 'multrazbor',
    media: 'sintel',
    frame: 5,
    category: 'animation',
    views: 91_300,
    age: 2 * MONTH,
    description: 'Вес, инерция и перекрытие действий. Покадрово разбираем один взмах крыла.',
  },
  {
    title: 'Old mentor archetype in short films',
    channel: 'dragon',
    media: 'sintel',
    frame: 1,
    category: 'film',
    views: 41_015,
    age: 1 * YEAR,
    description: 'He has one scene and two lines. Why the mentor still matters to the story.',
  },
  {
    title: 'Flower opening',
    channel: 'openmovies',
    media: 'flower',
    frame: 3,
    category: 'nature',
    views: 15_204,
    age: 2 * YEAR,
    description: 'A red flower opens in five seconds.',
  },
  {
    title: 'Facial rigs that sell a reaction',
    channel: 'indie',
    media: 'bunny',
    frame: 5,
    category: 'tutorials',
    views: 204_330,
    age: 3 * MONTH,
    description:
      'Brows first, mouth last. Building a face rig around the expressions your story needs.',
    watched: 0.15,
  },
  {
    title: 'Shooting timelapse on a budget',
    channel: 'macro',
    media: 'flower',
    frame: 2,
    category: 'tutorials',
    views: 8_903,
    age: 5 * WEEK,
    description:
      'An old phone, a cheap intervalometer app and a lamp. Results you can post tomorrow.',
  },
  {
    title: 'Building the burrow tree in 30 minutes',
    channel: 'meadow',
    media: 'bunny',
    frame: 0,
    category: 'tutorials',
    views: 54_660,
    age: 7 * MONTH,
    description: 'Modeling, roots and moss with geometry nodes. Project file in the description.',
  },
  {
    title: 'A desert theme in three notes',
    channel: 'score',
    media: 'sintel',
    frame: 6,
    category: 'music',
    views: 2_017,
    age: 1 * MONTH,
    description: 'How a tiny motif can carry the loneliness of a whole act.',
  },
]

export const VIDEOS: MockVideo[] = ENTRIES.map((video) => ({
  ...video,
  description: `${video.description}\n\n${CREDITS[video.media]}`,
}))
