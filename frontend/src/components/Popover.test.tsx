import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import Popover from './Popover'

const CARD = { width: 200, height: 120 }

/** jsdom lays nothing out: the button's box and the card's size come from here. */
function layout(button: { top: number; left: number }, windowHeight = 800) {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(
    DOMRect.fromRect({ x: button.left, y: button.top, width: 40, height: 40 }),
  )
  vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(CARD.width)
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(CARD.height)
  vi.spyOn(document.documentElement, 'clientWidth', 'get').mockReturnValue(1000)
  vi.stubGlobal('innerHeight', windowHeight)
}

async function open(align: 'start' | 'end' = 'start') {
  render(
    <Popover
      label="Options"
      role="menu"
      align={align}
      trigger={(props) => (
        <button type="button" {...props}>
          ⋮
        </button>
      )}
    >
      {() => <button type="button">Edit details</button>}
    </Popover>,
  )
  await userEvent.click(screen.getByRole('button', { name: '⋮' }))
  return screen.getByRole('menu', { name: 'Options' })
}

describe('Popover', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('opens in the top layer, under its button', async () => {
    const show = vi.spyOn(HTMLElement.prototype, 'showPopover')
    layout({ top: 100, left: 300 })

    const card = await open()

    expect(card).toHaveAttribute('popover', 'manual')
    expect(show).toHaveBeenCalled()
    expect(card.style.top).toBe('148px') // the button's bottom (140) + 8
    expect(card.style.left).toBe('300px')
  })

  it('lines up with the button’s right edge when aligned to the end', async () => {
    layout({ top: 100, left: 300 })

    const card = await open('end')

    expect(card.style.left).toBe('140px') // 340 - 200
  })

  it('opens over the button when the window has no room below', async () => {
    layout({ top: 700, left: 300 })

    const card = await open()

    expect(card.style.top).toBe('572px') // 700 - 8 - 120
  })

  it('stays inside the window', async () => {
    layout({ top: 100, left: 900 })

    const card = await open()

    expect(card.style.left).toBe('792px') // 1000 - 200 - 8
  })
})
