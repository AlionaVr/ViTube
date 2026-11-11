import type { RouteObject } from 'react-router'

import AuthPage from '../pages/auth/AuthPage'
import ChannelPage from '../pages/channel/ChannelPage'
import ChannelVideos from '../pages/channel/ChannelVideos'
import ChannelsPage from '../pages/feed/ChannelsPage'
import SubscriptionsPage from '../pages/feed/SubscriptionsPage'
import HomePage from '../pages/HomePage'
import NotFoundPage from '../pages/NotFoundPage'
import PlaylistPage from '../pages/playlist/PlaylistPage'
import ResultsPage from '../pages/results/ResultsPage'
import StudioVideosPage from '../pages/studio/StudioVideosPage'
import WatchPage from '../pages/watch/WatchPage'
import Layout from './Layout'

export const routes: RouteObject[] = [
  // Outside Layout: full-page forms with no header or sidebar, like Google's sign-in.
  { path: '/login', element: <AuthPage mode="signin" /> },
  { path: '/signup', element: <AuthPage mode="signup" /> },
  {
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'results', element: <ResultsPage /> },
      { path: 'watch', element: <WatchPage /> },
      { path: 'studio/videos', element: <StudioVideosPage /> },
      { path: 'playlist', element: <PlaylistPage /> },
      { path: 'feed/subscriptions', element: <SubscriptionsPage /> },
      { path: 'feed/channels', element: <ChannelsPage /> },
      // /@handle. Static paths rank higher, so this only gets the rest.
      {
        path: ':channel',
        element: <ChannelPage />,
        children: [
          { index: true, element: <ChannelVideos /> },
          { path: 'videos', element: <ChannelVideos /> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
