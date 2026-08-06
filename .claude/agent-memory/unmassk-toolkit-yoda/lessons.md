
## 2026-08-06 — HARD RULE violado por mi (git stash/git checkout -- en este repo), recuperado por suerte

Durante la verificacion de "N fallos preexistentes" via `git stash push -u --
<ficheros>` (patron que YO MISMO documente como valido en mis propias notas
del 2026-07-06 para OTRO repo), y despues un `git checkout --
unmassk-toolkit/hooks/customs.py` para deshacer una mutacion mia de prueba
(kill-test del reordenamiento determinista), destrui sin darme cuenta el
diff real de produccion de ese fichero (`git checkout --` restaura a HEAD,
no solo deshace mi mutacion -- se llevo por delante el trabajo real de
Ultron tambien). La memoria de Ultron en ESTE MISMO repo
(`.claude/agent-memory/unmassk-toolkit-ultron/MEMORY.md`, tope del fichero)
tiene una REGLA DURA explicita: NUNCA `git stash`/`git reset`/`git checkout
-- <path>`/`git restore` en este repo, ni siquiera acotado a un path,
porque el arbol de trabajo tiene sesiones concurrentes con cambios sin
commitear (ya paso dos veces antes de hoy, ambas por Ultron). Yo no lei esa
regla ANTES de tocar el arbol -- la lei DESPUES, al revisar la memoria de
Ultron para cruzar hallazgos. Recuperacion: `git stash pop` SI habia
funcionado limpio antes (confirmado por diff identico), pero el
`checkout --` posterior no tenia stash que revertir -- se recupero por
`git fsck --unreachable --no-reflog`, encontrando el SHA de commit del
stash ya dropeado (`0acfb3c9...`, todavia no recolectado por gc) y
`git show <sha>:<path> > <path>` para restaurar el blob exacto (verificado
byte a byte: mismo hash de blob `61c2f02` que el diff original). Sin ese
commit de stash todavia vivo en el object store, la perdida habria sido
irreversible desde mi lado.

**Regla que adopto de aqui en adelante, para CUALQUIER repo, no solo este:**
antes de cualquier prueba de mutacion/kill-test o cualquier comparacion
"antes/despues" sobre un fichero de produccion real (no una copia), busco
primero si existe una convencion de seguridad de git documentada en la
memoria de otros agentes del mismo repo (grep "HARD RULE"/"git stash"/"git
checkout" en `.claude/agent-memory/*/MEMORY.md` y `lessons.md`). El patron
correcto para una mutacion temporal sobre codigo real es: escribir la
version mutada con Python (`open(path).write(...)`) tras guardar el
contenido original en una variable en memoria (nunca en un fichero
temporal fuera del scratchpad que pueda perderse), y restaurar escribiendo
esa misma variable de vuelta -- nunca `git checkout --`/`git stash`, ni
siquiera "solo para revertir mi propio cambio", porque en un arbol de
trabajo compartido no hay forma de que ese comando distinga "mi cambio" de
"el cambio real que ya estaba ahi".
