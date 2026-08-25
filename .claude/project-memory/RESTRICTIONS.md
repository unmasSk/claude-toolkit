# RESTRICTIONS — índice. Lo escribe el script. No editar. Si diverge, manda git.

[R-003][install][hooks] never delete the plugin cache during an active session
[R-004][release][architecture] every plugin change bumps version and syncs marketplace.json
[R-005][db][docs] reference-heavy skills must cite verified sources, never invented content
[R-008][architecture][install] write access is only granted in claude-toolkit itself
[R-010][skills][architecture] agent frontmatter field memory: is real Claude Code API, never delete it
[R-011][skills][architecture] agent frontmatter field skills: preloads that skill into the subagent, verified
[R-012][memory][architecture] next_id must receive live index plus archived ids, or an id gets reused forever
[R-014][memory][install] wip verify hashes via --path only, --no-filters is forbidden (autocrlf)
[R-015][memory][release] main branch protection reads repo_type from .claude/project-memory/config.json
[R-016][memory][install] a memory note travels in its own commit; a zone add writes zones.json only
[R-017][hooks][skills] agents never run git stash/reset/checkout/restore, no pathspec exception
