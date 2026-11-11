import type { Category } from './types'

/** YouTube's names, in its order; the API sends ids only. */
export const CATEGORY_LABELS: Record<Category, string> = {
  film: 'Film & Animation',
  autos: 'Autos & Vehicles',
  music: 'Music',
  pets: 'Pets & Animals',
  sports: 'Sports',
  travel: 'Travel & Events',
  gaming: 'Gaming',
  people: 'People & Blogs',
  comedy: 'Comedy',
  entertainment: 'Entertainment',
  news: 'News & Politics',
  howto: 'Howto & Style',
  education: 'Education',
  science: 'Science & Technology',
  nonprofits: 'Nonprofits & Activism',
}

export const CATEGORIES = Object.keys(CATEGORY_LABELS) as Category[]
