---
name: capa5-work-branch-protection-and-similarity-fix-notes
description: fixed a self-inflicted-similarity RED in test_note_script.py + added the PIEZAS.md Sec.10.1 pt.3 work.py branch-protection RED row (config.json seeding technique)
metadata:
  type: project
---

**2026-08-02, memoria-v2 capa 5, dos arreglos sobre el contrato ya
existente** (ver [[capa5-scripts-red-contract-notes]] para el contrato
original). Solo se toco `tests/memory/` -- cero produccion.

**1 · Verificar un umbral de parecido CON LA PIEZA REAL antes de tocar
un test, nunca a ojo.** `TestCreatesAllSevenNoteTypesForReal` estaba en
rojo porque sus siete notas usaban titulares/descripciones casi
identicos entre si (`"<tipo> seven types case"` / `"MARK description for
<tipo>"`) -- Jaccard entre la primera y la segunda daba 0.545, por encima
de `vocabulary.SIMILARITY_THRESHOLD=0.5`, y el rechazo real de "esto pisa
a algo ya escrito" saltaba correctamente. El sistema hacia lo correcto;
el test estaba mal montado. Antes de reescribir los titulares, escribi un
script suelto (scratchpad, nunca en el repo) que carga `model.py` +
`similar.py` + `vocabulary.py` por ruta de fichero (mismo patron que
`import_lib_memory_module`) y calcula `similar._jaccard()` par a par
entre las siete notas candidatas ANTES de pegarlas en el test -- el
maximo salio 0.109, muy por debajo del umbral. Regla: cuando el "arreglo"
es cambiar datos de un test para que dejen de disparar una comprobacion
real, mide el nuevo dato contra la funcion real primero; no confies en
"suena bastante distinto".

**2 · Desbloquear un contrato test-first cuando el default fail-closed
choca con el fixture compartido.** `PIEZAS.md` Sec.10.1 punto 3 fija que
`work.py` debe rechazar un commit directo si `repo_type` es el protegido
(`"gitflow"`, el default sin `config.json`) y la rama actual es la
principal. Los 4 tests YA EXISTENTES de `test_work_script.py` corrian
sobre `tmp_repo` (rama `main` por defecto de `git init` en esta maquina)
SIN sembrar `config.json` -- exactamente el caso que la regla, una vez
implementada, tendria que rechazar. Implementar la regla sin tocar esos
tests los habria puesto los 4 en rojo a la vez.

Arreglo: añadi `seed_config_json(repo, **fields)` a `conftest.py` (mismo
patron JSON-literal que `seed_zones_json`, escribe
`.claude/project-memory/config.json`) y se lo puse a los 4 tests
existentes con `repo_type="trunk"` (el caso en el que un commit directo a
main es legitimo). Añadi una clase nueva,
`TestProtectedRepoRejectsDirectCommitToMainBranch`, con DOS filas: (a)
`config.json` explicito con `repo_type="gitflow"`, y (b) SIN
`config.json` en absoluto (el default fail-closed, "el caso mas
peligroso: un proyecto recien instalado" -- encargo literal del
propietario). Las dos corren hoy en rojo por la causa correcta
(`work.py` no lee `repo_type` en absoluto todavia, confirmado leyendo el
fichero) -- verificado ejecutando la suite: pasa de 181 verdes/1 rojo a
182 verdes/2 rojos (el rojo viejo desaparecio, aparece la fila nueva
esperando a Ultron).

**Sin texto que fije la redaccion exacta del rechazo** (a diferencia de
los rechazos de `note.py`, que `TEXTOS.md` repite literalmente seis
veces) -- `PIEZAS.md` solo dice "rechaza y dice que hacer", no da una
plantilla. Los dos tests nuevos comprueban EFECTO, nunca un texto
inventado: codigo de retorno distinto de cero, cero `Traceback`, salida
no vacia, y sobre todo -- lo que demuestra que el rechazo es de verdad y
no solo un aviso -- **cero commits nuevos y el mismo SHA de HEAD antes y
despues** (`git rev-parse HEAD` comparado, no solo `rev-list --count`,
mismo principio que la red autouse de `conftest.py` contra escribir en
el repo real).

**Asuncion documentada, no inventada:** "la rama principal" no la fija
ningun texto de esta rama -- se usa la rama que `git init` crea por
defecto en esta maquina (verificado: `main`), la misma que ya usaban los
4 tests existentes sin que nadie lo declarara. `tmp_repo` nunca cambia de
rama, asi que no hizo falta fijarla a mano.
