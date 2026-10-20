import type { Register } from 'claude-code'

// The plan stays in view (D-149, D-153): opened without focus, closeOnEscape or holdToasts.
const PANE = 'plan'

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.ui.open({ id: PANE, title: 'Plan' })

    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)

    return (
      <Box flexDirection="column">
        <Text dimColor>No plan yet.</Text>
      </Box>
    )
  })
}
