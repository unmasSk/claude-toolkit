# RESTRICTIONS — índice. Lo escribe el script. No editar. Si diverge, manda git.

[R-001][memory][install] everything the memory writes must travel in its own commit
[R-003][install][hooks] never delete the plugin cache during an active session
[R-004][release][architecture] every plugin change bumps version and syncs marketplace.json
[R-005][db][docs] reference-heavy skills must cite verified sources, never invented content
[R-006][memory][release] main branch protection depends on the repo_type marker
[R-007][hooks][skills] parallel agents never run global git stash/reset/checkout on a shared repo
[R-008][architecture][install] write access is only granted in claude-toolkit itself
[R-010][skills][architecture] agent frontmatter field memory: is real Claude Code API, never delete it
[R-011][skills][architecture] agent frontmatter field skills: preloads that skill into the subagent, verified
[R-012][memory][architecture] next_id must receive live index plus archived ids, or an id gets reused forever
