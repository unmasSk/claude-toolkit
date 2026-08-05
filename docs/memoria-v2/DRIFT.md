# Barrido del repo: qué habla del sistema viejo

Ocho exploraciones en paralelo sobre todo el repo (chatroom excluido a propósito). Es la entrada de trabajo de la **fase 7** del plan, y contiene la única sorpresa seria del barrido.

---

## 1. El resultado en una tabla

| Tajada | Ficheros | Resultado |
|---|---|---|
| compliance + seo | 121 | **limpia** |
| db + typescript | 99 | **limpia** |
| design + 3d | 199 | **limpia** |
| media + humanizer | 97 | **limpia** |
| ops + frontend | 217 | **limpia** |
| marketing | 82 | **limpia** |
| pentesting | 761 | **1 renombrado** |
| electronics | 26 | 9 rompen |
| **toolkit** (skills, agentes, bloques) | 43 | **~48 rompen · ~40 renombran · ~10 reescriben** |
| raíz (`bin/`, README, CLAUDE.md, ROADMAP, marketplace) | 12 | 10 rompen · 6 reescriben · 7 renombran |

**Más de 1.600 ficheros barridos. Seis plugins enteros no tienen ni una mención.** El trabajo está en tres sitios: el toolkit, electronics y la raíz.

---

## 2. El único sitio donde el v1 se EJECUTA

Todo lo demás es prosa que quedará desactualizada. **`bin/release.py` no describe el sistema viejo: lo invoca.**

```
bin/release.py:141   ruta fija a unmassk-toolkit/bin/git-memory-commit.py
bin/release.py:159   --trailer Touched={...}
```

**Y conviene decir qué NO es**, porque el nombre engaña: release **no guarda memoria**. Hace un commit de tipo `chore` con tres ficheros concretos (el manifiesto, el marketplace y el CHANGELOG) y pasa por el wrapper únicamente porque el gate prohíbe `git commit` directo y ese es el único camino abierto.

Así que la traducción es simple: **`gitmem work`**, que ya está en el plan (paso 2.7). El campo de ficheros tocados desaparece solo, porque se retiró.

Lo único que impone es **un requisito sobre esa pieza: `gitmem work` tiene que poder commitear solo ciertas rutas**, sin arrastrar el resto del índice. Si no, release deja de poder publicar sin tocar lo que haya a medias en el árbol.

Hoy no está roto —el wrapper que llama sobrevive al reparto— pero el día que se retire el v1 el pipeline de publicación se cae con un código de error, no con una frase desactualizada.

---

## 3. Las cuatro minas

| # | Dónde | Qué pasa | Se desactiva en |
|---|---|---|---|
| 1 | `hooks/pre-validate-commit-trailers.py:51` | Reconoce el commit legítimo comparando la ruta contra `git-memory-commit.py`. Con el generador nuevo, **bloquea todos los commits del v2** | paso 2.8 |
| 2 | `lib/parsing.py` | `sanitize_trailer_value` nació para la memoria y hoy la usan cinco módulos que no son de memoria | el v2 escribe el suyo; se apunta para el reparto |
| 3 | `hooks/session-start-boot.py` | Salud del toolkit y memoria intercaladas en la misma lista: no hay costura | el arranque del v2 se escribe de cero (3.5) |
| 4 | `bin/release.py:141,159` | **Invoca el motor viejo en producción** con ruta fija y un campo retirado. No usa la memoria: solo necesita hacer un commit, y el gate no deja otro camino | paso 2.8b |

---

## 4. Lo que hay que tocar, por sitio

### El toolkit — el grueso

- **`agents/gitto.md`** — 85-90% era el sistema viejo. **Se retiró, no se reescribió** (paso 7.7, hecho).
- **`skills/unmassk-flow/SKILL.md`** — 20 menciones, tocando triaje, ejecución, verificación y cierre.
- **`skills/unmassk-project-lifecycle/`** y su `references/start.md` — la detección de "¿hay proyecto en marcha?" depende de trailers que desaparecen, y el patrón de marcadores por fase estructura el fichero entero.
- **`skills/unmassk-close-session/SKILL.md`** — los pasos 1 a 4 de 9.
- **`skills/unmassk-core/SKILL.md`** — seis puntos concretos, no el fichero.
- **`agents/bilbo.md`** — la sección de memoria de callejones sin salida entera.
- **`lib/managed_blocks.py`** — el bloque de protocolos, que se inyecta en el `CLAUDE.md` de todos los proyectos.
- Las nueve tablas de tripulación que nombraban a Gitto: ya se les quitó esa fila.

### Electronics — nueve menciones, todas el mismo patrón

`memo(device/<id>)` como forma de guardar el perfil de un aparato, más una referencia a `git-memory-recall.py --scope`. Se traduce a `gitmem note M --zones device <id>` y `gitmem search`.

### La raíz

- **`README.md`** — la fila de memoria y la tabla de scripts. **Y ya miente hoy**: nombra `git-memory-recall.py` en una ruta donde ese fichero no existe.
- **`CLAUDE.md`** — el bloque del toolkit entero. Ojo: es un bloque gestionado, así que se toca en el generador, no en el fichero.
- **`ROADMAP.md`** — seis menciones sueltas, y una que importa: una idea congelada a propósito (el mapa visual que se autorrellena) tiene su premisa anclada al campo de ficheros tocados, **que se retira**. Cuando se descongele, el puente que iba a usar ya no existirá.
- **`marketplace.json`** — la descripción del plugin.

### Lo que NO se toca

- **`CHANGELOG.md`** — 96 menciones, todas dentro de versiones publicadas. Es historia y no se reescribe. La sección sin publicar está vacía.
- Todo el aparato de memoria **de los agentes** (`.claude/agent-memory/`) — es otro sistema y sobrevive.
- `unmassk-standards` — pese a llevar la palabra en 25 líneas, su eje es genérico. Solo tres líneas la nombran de verdad.

---

## 5. Los falsos amigos, para que nadie los toque

Cada tajada trajo su ruido, y en todos los casos es vocabulario de otro dominio:

| Dominio | Qué parecía | Qué era |
|---|---|---|
| compliance | retención, derecho al olvido, "Remember:" | RGPD y cláusulas de acuerdos de confidencialidad |
| pentesting | memoria, volcados, consolidación | RAM, forense y montículo de glibc |
| bases de datos | memoria, recuperación | RAM del motor y métricas de recuperación de vectores |
| ops | memoria, pre-commit | límites de contenedores y la herramienta genérica |
| diseño y 3d | memoria, calibración | memoria de GPU y escala física |
| media | memoria | buffers de vídeo y `useMemo` de React |
| humanizer | calibración, memorizar, corpus | su propio catálogo de tics de escritura |
| electrónica | memoria | EEPROM y flash del microcontrolador |

---

## 6. Un hueco que el barrido destapó

Varias skills escriben `test_command` y `repo_type` en `.claude/git-memory-config.json`, y ese fichero **no aparecía en ninguno de los cuatro documentos del plan**: ni se conservaba ni se sustituía.

**Resuelto:** ninguno de los dos es memoria — son configuración del proyecto. Van a `.claude/project-memory/config.json`, **fichero aparte del de zonas** (decisión del propietario: cada cosa en su sitio, no un cajón). Las zonas cambian a menudo y las escribe el sistema; la configuración cambia una vez y la pone una persona — juntarlas es cómo una escritura automática acaba pisando un ajuste hecho a mano.
