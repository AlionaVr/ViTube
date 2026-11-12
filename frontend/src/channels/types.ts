// Types from the API (schema.d.ts).
import type { components } from '../api/schema'

/** What a card or a comment shows about a channel. */
export type ChannelSummary = components['schemas']['ChannelSummary']

/** The channel page header; the watch page reads the subscriber count from it. */
export type Channel = components['schemas']['ChannelOut']

export type Subscription = components['schemas']['SubscriptionOut']

/** A row of the viewer's subscriptions. */
export type SubscribedChannel = components['schemas']['SubscribedChannel']

/** A card on your own channel's Videos tab, which lists every visibility. */
export type MyChannelVideo = components['schemas']['MyChannelVideo']

/** The Videos tab's chips. */
export type VideoSort = components['schemas']['VideoSort']
