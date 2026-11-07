// Demo comments, generated per video from a seed.
import type { ChannelSummary } from '../channels/types'
import type { Comment } from '../comments/types'
import type { MediaKey } from './catalog'
import { pick, seededRandom } from './random'

/** Stored comment: the viewer's own rating is added on read. */
export type MockComment = Omit<Comment, 'my_rating'>

const AUTHORS: ChannelSummary[] = [
  ['marta.draws', 'Marta'],
  ['kevin_renders', 'Kevin'],
  ['lena-k', 'Lena K'],
  ['oldfilmnerd', 'Old Film Nerd'],
  ['pixelpusher42', 'Pixel Pusher'],
  ['tanya.v', 'Tanya V'],
  ['anim8or', 'Anim8or'],
  ['user-q8w2n5tz', 'user-q8w2n5tz'],
  ['dmitry.blender', 'Dmitry'],
  ['sofia.frames', 'Sofia'],
  ['nightowl_edits', 'Night Owl'],
  ['greenthumb', 'Green Thumb'],
  ['jules.sound', 'Jules'],
  ['paper.boats', 'Paper Boats'],
  ['user-7fq2p0zd', 'user-7fq2p0zd'],
  ['studio.sparrow', 'Studio Sparrow'],
  ['coffee.and.keys', 'Coffee and Keys'],
  ['ana.lumen', 'Ana'],
].map(([handle, name]) => ({ handle, name, avatar_url: null }))

const GENERAL_TEXTS = [
  'Очень круто разобрано, спасибо! Ждём продолжение.',
  'Наконец-то нормальный разбор без воды.',
  'Underrated channel. Subscribed.',
  'Rewatched three times just for the lighting.',
  'This deserves way more views.',
  'Where can I download the source files?',
  'Great video, but the audio is a bit quiet in the second half.',
  'First time seeing this and I’m hooked.',
]

// Comments that fit what the video shows.
const TEXTS_BY_MEDIA: Record<MediaKey, string[]> = {
  bunny: [
    'The timing on the apple gag still gets me every single time.',
    'That fur shading holds up better than some recent features.',
    'The way the squirrel freezes before the fall — perfect anticipation.',
    'I teach intro to animation and show this to every new group. Never fails.',
    'My kids made me watch this 14 times today. Send help.',
    'I’ve been animating for about six years and this finally made squash and stretch click for me. The part about holding the extreme pose for two extra frames before the release is something nobody explained in any of the courses I paid for.\n\nAlso, the side-by-side with the final render is brilliant. Please do more of these!',
    'Who else is here after the latest Blender release? 🙋',
  ],
  sintel: [
    'The ending wrecked me the first time. Still does.',
    'Pausing on that frame — it could be a painting.',
    'The music at the end gives me chills.',
    'The color script part was so useful. Bookmarked.',
    'Can’t believe this was made with free software.',
    'That dragon’s wing timing is unreal.',
  ],
  flower: [
    'Five seconds of pure calm. Thank you.',
    'Anyone know which lens settings were used for this shot?',
    'What a color! Is it a portulaca?',
    'I could watch this on loop all day.',
  ],
}

const REPLIES = [
  'Same here!',
  'Totally agree.',
  'Haha, true',
  'Came here to say exactly this.',
  'It’s in the description 🙂',
  'Согласен!',
  'This 👆',
  'Couldn’t have said it better.',
]

const OWNER_TEXTS = [
  'Thanks for watching! The next part is coming next week.',
  'Glad it helped 🙂',
  'Good catch — fixed in the description.',
  'Project files are linked in the description.',
]

const HOUR_MS = 3600 * 1000

export interface GeneratedComments {
  top: MockComment[]
  replies: Map<string, MockComment[]>
}

export function generateComments(
  videoId: string,
  media: MediaKey,
  owner: ChannelSummary,
  views: number,
  publishedAt: number,
  now: number,
): GeneratedComments {
  const random = seededRandom(videoId)
  const between = (from: number) => new Date(from + random() * (now - from)).toISOString()
  const likes = () => Math.floor(random() ** 3 * Math.max(views, 50) * 0.002)
  const texts = [...TEXTS_BY_MEDIA[media], ...GENERAL_TEXTS]
  const replies = new Map<string, MockComment[]>()

  const count = 4 + Math.floor(random() * 6) + Math.floor(Math.log10(Math.max(views, 10)) * 2.5)
  const top: MockComment[] = Array.from({ length: count }, (_, i) => {
    const byOwner = i === 0 && random() < 0.5
    const id = `${videoId}-c${i}`
    const publishedAtIso = between(publishedAt + HOUR_MS)
    const replyCount = random() < 0.3 ? 1 + Math.floor(random() * 4) : 0
    if (replyCount > 0) {
      const start = Date.parse(publishedAtIso)
      replies.set(
        id,
        Array.from({ length: replyCount }, (_, j) => {
          const replyByOwner = random() < 0.25
          return {
            id: `${id}-r${j}`,
            author: replyByOwner ? owner : pick(random, AUTHORS),
            by_owner: replyByOwner,
            text: pick(random, replyByOwner ? OWNER_TEXTS : REPLIES),
            published_at: between(start),
            like_count: Math.floor(random() * 40),
            reply_count: 0,
          }
        }).sort((a, b) => a.published_at.localeCompare(b.published_at)),
      )
    }
    return {
      id,
      author: byOwner ? owner : pick(random, AUTHORS),
      by_owner: byOwner,
      text: pick(random, byOwner ? OWNER_TEXTS : texts),
      published_at: publishedAtIso,
      like_count: likes(),
      reply_count: replyCount,
    }
  })
  return { top, replies }
}
