"""Marcador de CI del sistema de memoria v2 -- decision D-070
(`gitmem search --id D-070`, 2026-08-26).

SOLO DATOS. CERO FUNCIONES -- mismo principio que ``emojis.py`` y
``vocabulary.py``: si algun dia hace falta una funcion aqui, es senal de
que la logica se esta colando en la capa de datos.

``SKIP_CI_MARKER`` es la forma EXACTA que GitHub Actions reconoce de
forma nativa para no disparar un workflow (case-insensitive de por si en
GitHub, pero el texto literal que este proyecto escribe es siempre este,
sin variantes). Dos productores la usan, cada uno en su propio commit,
NUNCA dentro del ensamblado compartido de `notes_commit.write_work()`
(D-070: si aterrizara ahi, `bin/release.py` se la llevaria de regalo y
dejaria de disparar la CI que verifica cada publicacion):

- `bin/memory/work.py` -- la anade al mensaje de cada commit de trabajo.
- `bin/memory/wip.py` -- la anade al mensaje de cada checkpoint.

Se anade siempre en su PROPIA linea, separada por una linea en blanco
de cualquier otro campo (`Issue: #N`, etc.) -- `lib/memory/health_plans.py`
ancla su lectura del trailer `Issue:` por LINEA ENTERA
(`_ISSUE_TRAILER_RE`), asi que compartir linea con ese trailer lo
romperia en silencio.
"""

SKIP_CI_MARKER = "[skip ci]"
