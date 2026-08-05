# Textos literales del sistema

Lo que el sistema escupe, palabra por palabra. No descripciones: los textos. Si esto queda a improvisación, cada implementación lo escribe distinto y el rechazo que se lee a las tres de la mañana acaba siendo un volcado ilegible.

**El comando es `gitmem`** — fachada única con subcomandos en inglés sobre los scripts: `note`, `work`, `wip`, `remove`, `next`, `search`, `zones`, `rezones`, `rule`. `[decisión del propietario, 2026-08-03]` Cuatro cambios sobre la lista anterior: `close`→`remove`, `context`→`next`, `reindex`→`rezones` (renombrados — «cerrar» no dice que retira una nota; el comando escribe el cierre de sesión y lo que importa de él es el Next); `bench` se borra entero («no lo he autorizado en la vida»); `boot` deja de ser subcomando — se dispara solo, como el arranque de siempre; y `wip` se añade — el checkpoint sin preguntas, para que `validator.is_wip()` deje de ser una puerta sin llave.

**Emojis** — resueltos. El descarte es 🚫 y no una papelera: la papelera sugiere que se puede borrar, y el descarte es permanente.

```
🧭 D decision     ❓ Q question
📌 M memo         🚫 X discarded
⚠️  R restriction  🔥 I incident
⛔ B blocker      ⏩️ next
[WIP] 🚧 wip      🧠 rule
```

~~`[corrección del propietario, 2026-08-03]` El marcador del Next pasa de `⏩` a `🧭`.~~ **REVOCADO por el propietario el 2026-08-05.** El Next vuelve a `⏩️` —con el selector de variante, para que se pinte como emoji y no plano, igual que se hizo con el muro en B9—: *«el azul, el de las dos flechitas, es el del Next; el otro era el del context de la versión 1 y lo han vuelto a pisar»*. La brújula se queda **solo** para la decisión.

**Y el checkpoint gana su corchete** `[decisión del propietario, 2026-08-05]`: `[WIP] 🚧 <mensaje>`, para que se lea igual que el `[NEXT]`. `validator.is_wip()` sigue reconociendo la forma vieja —el emoji suelto— porque ya hay checkpoints escritos así.

`[corrección de esta pasada, 2026-08-03]` `regla` en el mapa de arriba pasa a **`rule`**: era la única de las diez etiquetas que seguía en español, contradiciendo B11 (*«deja de poner cosas en español cuando son en inglés... hablo de recuentos, avisos, restricciones»*) y el propio nombre del comando (`gitmem rule`). No es cosmético: §6.10 de este mismo documento cuenta que de una etiqueta mal puesta en este bloque salió mal el nombre de una clave en el código (`⏩` → `"context"`).

---

## 1. Los rechazos de la aduana

### 1.1 Zona que no existe

```
⛔ NOTA RECHAZADA — la zona «facturacion» no existe

zones.json tiene 34 zonas. Antes de crear una nueva, mira si ya está
con otro nombre. Las más parecidas:

  billing     18 notas   "cobros, pasarela de pago, suscripciones"
  invoices     4 notas   "documentos de factura emitidos al cliente"

Si es una de ellas, relanza con esa:
  gitmem note D --zones product billing "..." --why "..." --description "..."

~~Si de verdad falta, añádela a .claude/project-memory/zones.json~~
~~(nombre en inglés, una línea de descripción, sus alias) y relanza igual.~~
Si de verdad falta, dala de alta con el comando y relanza igual:
  gitmem zones add <nombre> --description "..." [--aliases a1 a2 ...]
No pidas permiso: el usuario lo ve en el chat.
```

`[corregido 2026-08-04]` Decía «añádela a .claude/project-memory/zones.json
(nombre en inglés, una línea de descripción, sus alias) y relanza igual» —
era falso desde que existe `gitmem zones add`: ese texto se escribió cuando
no había comando y mandaba editar el fichero a mano, saltándose las cuatro
protecciones que el comando sí tiene (rebota si el nombre ya es zona,
rebota si ya es alias de otra, escritura atómica y bajo candado) y
contradiciendo la regla del sistema de que zones.json lo escribe el
script, nunca una persona.

### 1.2 Zona de la lista negra

```
⛔ NOTA RECHAZADA — «session» no es memoria del proyecto

claude, user, session, project y workflow describen CÓMO trabajamos,
no el producto. Eso va al fichero de reglas, que se lee entero aparte
y no ensucia ninguna búsqueda:

  gitmem rule "..."

Si en realidad hablabas de una parte del producto, dale su zona real:
  gitmem note M --zones <zona1> <zona2> "..." --description "..."
```

### 1.3 La palabra ilegal

```
⛔ NOTA RECHAZADA — «audit» significa dos cosas distintas

Elige cuál:

  registro    (zona2)  el módulo de la aplicación que guarda el rastro
  codeaudit   (zona1)  las auditorías que los agentes pasan al código

Relanza con la que sea:
  gitmem note M --zones product registro "..." --description "..."
  gitmem note M --zones codeaudit <zona2> "..." --description "..."
```

### 1.4 No encaja en ningún tipo

```
⛔ NOTA RECHAZADA — no sé qué tipo es esto

"log rotation strategy and the pending vendor answer" mezcla un hecho
del proyecto con algo que espera de fuera. Una nota, una cosa.

  D  decision     se eligió entre opciones
  M  memo         un hecho estable del proyecto
  R  restriction  un muro: saltarlo rompe algo
  Q  question     pregunta abierta, sin respuesta todavía
  X  discarded    se estudió y se descartó
  I  incident     se rompió algo: causa y qué se hizo
  B  blocker      pendiente de fuera; bloquea

Pártela en dos, o elige uno, y relanza:
  gitmem note <TIPO> --zones deploy logging "..." --description "..."

Que no encaje es información: si de verdad no es ninguno de los siete,
dilo en el chat antes de forzarlo.
```

### 1.5 Falta la respuesta a la pregunta del dolor

```
⛔ NOTA RECHAZADA — falta una respuesta

Toda M y toda R contestan lo mismo antes de entrar:

  ¿puede costar datos, horas o producción caída?

  sí  →  es un muro. Entra como R y sale en TODOS los arranques.
  no  →  es un hecho. Entra como M y se lee cuando se busca su zona.

Relanza con la respuesta puesta:
  gitmem note M --zones database backups "..." --description "..." --stops no
  gitmem note R --zones database backups "..." --description "..." --stops yes
```

### 1.6 Pisa a algo ya escrito

```
⛔ NOTA RECHAZADA — esto pisa a algo que ya está escrito

Tu nota comparte terreno con estas de [product][auth]. Di qué pasa
con ellas antes de entrar:

  D-030   2026-04-11   login with JWT + Google OAuth
          keys: token, oauth, sso, signin
          Why: sesiones no escalan multi-tenant; Google evita gestionar
               passwords propios

  D-041   2026-06-02   session lifetime raised to 30 days
          keys: token, expiry, refresh
          Why: el equipo de campo se quejó de reloguear cada semana

Tres salidas, y solo tres:

  la sustituye   --replaces D-030    la vieja sale del índice a ARCHIVED
  conviven       --replaces none     las dos siguen vigentes
  es duplicado   no la guardes; si hay que matizar, cierra la vieja:
                 ~~gitmem remove D-030 "..."~~
                 gitmem remove D-030 "..." --restriction no
                 [corregido 2026-08-04: la línea de arriba tachada
                 omitía `--restriction no`, que `remove.py` exige
                 siempre (`required=True`, bin/memory/remove.py:53) --
                 tal cual, el comando rebotaba con error de argparse
                 antes de cerrar nada]

Relanza:
  gitmem note D --zones product auth "..." --why "..." \
    --description "..." --replaces D-030
```

### 1.7 Destilación sin fuentes

```
⛔ NOTA RECHAZADA — una destilación sin fuentes no es una destilación

Compactar es decir DE QUÉ. Sin Origin no hay forma de volver a lo que
resumiste ni de comprobar si lo resumiste bien.

Pon los hashes v1 de los que sale, separados por espacios:
  ~~gitmem note M --zones testing amianto "..." --description "..." \
    --origin 4f2a1bc,9de77a0,c31b8e5~~
  gitmem note M --zones testing amianto "..." --description "..." \
    --origin 4f2a1bc 9de77a0 c31b8e5
  [corregido 2026-08-04: la línea de arriba tachada separaba los hashes
  por comas -- `note.py` los quiere separados por espacios
  (`--origin`, `nargs="+"`, bin/memory/note.py:86); tal cual, los tres
  hashes entraban como un solo origen y la nota quedaba mal enlazada]

Vale para toda nota de destilación, la escriba quien la escriba.
```

### 1.8 Key marcadora mal escrita — no es rechazo, es aviso al guardar

```
✅ M-062 guardada — con una key corregida

  seguridad  →  security

Las cuatro keys marcadoras tienen una sola forma válida, para que la
búsqueda las encuentre siempre:

  antipattern    (anti-pattern, antipatron, antipatrón)
  security       (seguridad, sec)
  performance    (perf, rendimiento)
  legal          (legales, compliance)

El resto de keys son libres, en inglés. No hay que hacer nada.
```

### 1.9 La issue del acta no existe

```
⛔ ACTA RECHAZADA — la issue #47 no existe en este repo

Esta es la única vez que se comprueba. Si el número está mal, el enlace
decisión → plan queda roto para siempre y nadie lo va a notar.

  gh issue list --limit 20          ver las abiertas
  gh issue create --title "..."     crearla ahora

Relanza con el número bueno:
  gitmem note M --zones product auth "login rollout plan" \
    --description "..." --origin D-030 --issue 52
```

### 1.10 Cierre de incidencia: ¿sale muro?

```
⛔ CIERRE RETENIDO — I-014 no se cierra sin contestar esto

  ¿de esta cicatriz sale muro?

  I-014  [testing][auth]  seeds wiped the production users table
         causa: el script de seeds coge la BD de una variable de entorno,
         y en el runner de CI esa variable traía producción.

  sí  →  nace una R en esta misma zona y sale en todos los arranques
  no  →  se cierra sin más; nadie vuelve a enterarse

Relanza con la respuesta:

  gitmem remove I-014 "..." --restriction no

  gitmem remove I-014 "..." --restriction new \
    --restriction-text "seeds never read the DB url from the environment" \
    --why "..."
```

### 1.11 El titular es demasiado largo

```
⛔ NOTA RECHAZADA — el titular tiene 96 caracteres y el tope son 80

  "the backup restore script must never point at the production database
   connection string"

El titular es lo único que se ve en el índice y en el arranque: si no se
lee de un vistazo, deja de cumplir su función. No se corta solo, porque
cortarlo borraría justo la parte que suele importar.

Dos salidas:

  acórtalo          quédate con la prohibición; el detalle va a Description
  párte en dos      si dice dos cosas, son dos notas

Relanza:
  gitmem note R --zones database backups \
    "restore script must never target the production database" \
    --why "..." --description "..." --stops yes
```

### 1.11b Una regla casi repetida — no se guarda

`[decisión del propietario, 2026-08-04: «si es casi repetida, dejar solo 1». El texto lo delegó en el orquestador el mismo día —«decídelo tú»—, así que es **revocable**: se escribió con su criterio, no con sus palabras.]`

```
❌ REGLA NO GUARDADA — ya tienes una que dice casi lo mismo

  🧠 [user] sé escueto, not yapping

Lo que ibas a guardar:

  🧠 [user] sé escueto, nada de yapping

Se queda una. Las reglas se entregan **todas juntas** cada vez que las
pides, así que dos versiones de la misma no añaden nada: solo hacen la
lista más larga y más difícil de obedecer.

Dos salidas:

  no hagas nada     la que ya tenías sigue vigente y vale
  reescríbela       si de verdad dicen cosas distintas, que se note:
                    gitmem rule "..."
```

> **Ojo con el ejemplo, porque la primera versión de esta sección lo tenía mal** `[corregido por el propietario, 2026-08-04]`. Decía *«nunca mockees la base de datos en tests de integración»*, **y eso no es una regla: es un memo**, un hecho técnico del proyecto con su key `antipattern`. Una regla es **cómo quieres que trabaje Claude** —el tono, qué le pides, qué no quieres oír—, no una decisión sobre el código.
>
> **Importa más de lo que parece:** de este documento se derivan las piezas, y un ejemplo del tipo equivocado enseña a meter memos por la puerta de las reglas — que es exactamente por donde el sistema anterior acabó con **un tercio de su memoria** siendo configuración de trabajo disfrazada de memoria de proyecto, ensuciando todas las búsquedas.
>
> **El ejemplo que usa ahora esta sección lo dio el propietario** al corregirlo: *«una regla es "sé escueto, not yapping"»*. Va en sus palabras a propósito. Los otros dos buenos, también suyos, están en `PIEZAS.md` §9.7: *«solo fallos del día a día, nada de casos límite académicos»* y *«español llano, sin jerga ni metáforas inventadas»*.
>
> **La prueba para saber de qué tipo es algo, en una línea:** si le habla a **Claude sobre cómo trabajar**, es regla. Si dice algo **del proyecto**, es memo — o muro, si saltárselo rompe algo.

**Por qué se rechaza en vez de guardar las dos y avisar** `[criterio del orquestador]`: el sistema anterior acumuló **114 recordatorios duplicados**, y no fue por falta de aviso — fue porque avisar sin frenar deja el trabajo de limpiar para «luego», y luego no llega nunca. La regla que manda aquí es del propietario y es de una sola frase: *«dejar solo 1»*.

**Y por qué imprime las dos, la vieja y la que ibas a escribir:** sin ver las dos juntas no puedes juzgar si de verdad son la misma. Es el mismo criterio que el rechazo **§1.6**, que enseña las notas candidatas enteras en vez de sus identificadores.

**Lo que este texto NO decide, y queda anotado como hueco:** qué se considera «casi lo mismo». Eso lo fija `rules.similar_existing()` comparando por texto, y su umbral **no lo toca este documento**.

> **El alcance real del detector, medido ejecutándolo el 2026-08-04 — y el ejemplo de arriba se cambió por esto** `[corregido 2026-08-04]`**.** Este texto ilustraba el rechazo con el par *«sé escueto, not yapping»* → *«no te enrolles, ve al grano»*, **y ese caso el sistema NO lo detecta**: dicen lo mismo, pero **no comparten ni una palabra**, y el detector compara palabras, no significado.
>
> Un ejemplo que enseña un caso imposible es peor que no poner ejemplo: de este documento se derivan las piezas, y quien lo lea creerá que el sistema caza repeticiones que en realidad se le cuelan enteras. Probado en vivo:
>
> | Ya tienes `sé escueto, not yapping` y escribes… | ¿Lo caza? |
> |---|---|
> | `sé escueto, nada de yapping` | **sí** |
> | `escueto, not yapping` | **sí** |
> | `sé muy escueto, not yapping por favor` | **sí** |
> | `no te enrolles, ve al grano` | **no** |
>
> **Y es un límite aceptado, no un fallo:** el contraste por significado —dos frases distintas que dicen lo mismo— **no se construye a propósito**. La especificación §12 lo declara punto abierto porque excede a un script y pediría un agente. Lo que sí se caza es la repetición **por descuido**, que es la corriente: reescribir una regla que ya tenías sin acordarte, con casi las mismas palabras.

### 1.12 `git commit --amend` reescribe un commit ya cerrado

`[decisión del propietario, 2026-08-03]` — **faltaba en este documento**. Hoy el rechazo se queda en «esto reescribe historia» y ahí abandona al usuario, incumpliendo la regla de que todo rechazo lleva el comando exacto para relanzar. `--amend` y `rebase` comparten la misma salida (§1.13) porque comparten el mismo motivo: los dos cambian el mensaje **y** el código de un commit que ya se dio por cerrado.

```
⛔ COMANDO RECHAZADO — `git commit --amend` reescribe un commit ya cerrado

Nada se borra ni se reescribe jamás: toda corrección es un commit nuevo.

  el mensaje estaba mal      sustitúyelo con una nota nueva
                             gitmem note <TIPO> --zones <zona1> <zona2> "..." --description "..."
  se te olvidó un fichero    va en otro commit encima, no en el mismo
                             ~~gitmem work "..." --description "..."~~
                             gitmem work "..." --path <ruta1> [--path <ruta2> ...] [--issue N]
                             [corregido 2026-08-04: la línea de arriba tachada
                             ofrecía `--description`, que no existe en `work.py`
                             (bin/memory/work.py:56-58); `--path` es el que
                             falta y además es obligatorio (`required=True`)]
  quieres limpiar la rama    no hace falta tocar nada ahora: se comprime
                             sola al fusionar (squash al merge)

Relanza con la salida que toque; el commit ya cerrado no se toca.
```

### 1.13 `git rebase` reescribe la rama entera

`[decisión del propietario, 2026-08-03]` — misma familia que §1.12, opción A para los dos. `rebase` reescribe los commits enteros y, al resolver conflictos, cambia también el código — no solo el mensaje.

```
⛔ COMANDO RECHAZADO — `git rebase` reescribe la rama entera

Mismo motivo que `--amend`: nada se reescribe jamás, y aquí además puede
cambiar el código si hay que resolver conflictos al rebasar. Su único uso
legítimo —dejar la rama limpia antes de fusionar— ya está resuelto sin
tocar un solo commit:

  el mensaje estaba mal      sustitúyelo con una nota nueva
                             gitmem note <TIPO> --zones <zona1> <zona2> "..." --description "..."
  se te olvidó un fichero    va en otro commit encima, no reescribas
                             ~~gitmem work "..." --description "..."~~
                             gitmem work "..." --path <ruta1> [--path <ruta2> ...] [--issue N]
                             [corregido 2026-08-04: la línea de arriba tachada
                             ofrecía `--description`, que no existe en `work.py`
                             (bin/memory/work.py:56-58); `--path` es el que
                             falta y además es obligatorio (`required=True`)]
  quieres limpiar la rama    ya está resuelto: se comprime sola al
                             fusionar (squash al merge), no hace falta
                             rebasar para eso

Relanza sin rebasar: ningún commit existente se toca.
```

---

## 2. El informe de estado

### 2.1 Zona con contenido

```
════════════════════════════════════════════════════════════════════════
  ZONA auth · 14 vigentes · 6 archivadas            2026-08-01 09:12 UTC
════════════════════════════════════════════════════════════════════════

⚠️ RESTRICTIONS (3) — literales

  R-004  [testing][auth]  never run the auth test suite against production
         Why: en marzo un test de login borró 1.200 sesiones reales y se
              tardó cuatro horas en reconstruirlas desde el backup.
         Origin: I-009

  R-011  [api][auth]  refresh tokens are never logged, not even truncated
         Why: un token truncado sigue sirviendo para la mitad de los
              ataques de replay que probamos.
         Keys: security

  R-018  [deploy][auth]  no auth deploy on Friday without a tested rollback
         Why: los dos incidentes de auth de este año fueron viernes por la
              tarde y sin vuelta atrás ensayada.
         Origin: I-014

⛔ BLOCKERS (1)

  B-003  [product][auth]  google workspace admin consent still pending
         espera: el cliente (Marta, IT de Omawa)
         Description: sin el consentimiento de administrador no se puede
         probar el alta masiva de usuarios; el flujo individual sí va.

🧭 DECISIONS (2 racimos)

  D-030  login with JWT + Google OAuth                          2026-04-11
         Why: sesiones no escalan multi-tenant; Google evita gestionar
              passwords propios.
    ├─ X-012  server-side sessions                    descartada · Origin D-030
    ├─ X-013  own password login                      descartada · Origin D-030
    ├─ D-041  session lifetime raised to 30 days      vigente   · Origin D-030
    └─ #47    plan-login.md                           acta      · 2026-04-12

  D-052  logout revokes the refresh token server-side           2026-07-03
         Why: el logout de cliente dejaba el refresh vivo 30 días.
    └─ D-036  logout only clears the cookie           archivada · replaced by D-052

📌 MEMOS (4)

  M-021  google returns email_verified=false for workspace aliases
  M-033  the JWT carries tenant_id; the gateway reads it, nobody else
  M-048  password reset links live 15 minutes, not the 60 in the docs
  M-057  Auth0 was never used here, whatever the README said until June

🔥 INCIDENTS (2 · 1 abierta)

  I-014  session fixation on the tenant switcher       cerrada 2026-06-20
         → parió R-018
  I-021  login loop on Safari 17 after the cookie change
         ABIERTA desde 2026-07-28

❓ OPEN QUESTIONS (2)

  Q-007  do we support more than one Google Workspace per tenant?
         Bloquea el modelo de datos de invitaciones. Hay que contestarla
         antes de tocar el módulo de equipos.

  Q-015  is the 30-day session lifetime acceptable for the audit?
         Nació de D-041. Sin respuesta desde el 2 de junio.

────────────────────────────────────────────────────────────────────────
  Historia completa, con lo archivado:   gitmem search auth --todo
```

### 2.2 Zona sin ninguna nota

```
════════════════════════════════════════════════════════════════════════
  ZONA payments                                     2026-08-01 09:14 UTC
════════════════════════════════════════════════════════════════════════

              ⚠️  C E R O   N O T A S

  La zona existe en zones.json (dada de alta el 2026-07-30) y no tiene
  ni una: ninguna decisión, ningún muro, ningún hecho, ninguna
  incidencia, ninguna pregunta.

  Es un dato, no un fallo. O el trabajo no ha empezado, o se ha hecho
  sin escribir nada de lo que se decidió.

  Zonas parecidas que sí tienen contenido:

     billing    18 notas       gitmem search billing
     invoices    4 notas       gitmem search invoices

  Si lo que buscabas está en una de ellas, esta zona sobra en zones.json.
════════════════════════════════════════════════════════════════════════
```

### 2.3 Búsqueda por palabra suelta

```
════════════════════════════════════════════════════════════════════════
  PALABRA «stripe» · 3 zonas · 11 vigentes          2026-08-01 09:20 UTC
  ›  marca la línea que casó
════════════════════════════════════════════════════════════════════════

──── [api][billing] · 6 notas ──────────────────────────────────────────

⚠️ RESTRICTIONS (1)

› R-029  no Stripe test hits the live key, ever
         Why: en mayo un test de suscripciones cobró 340 € reales a
              catorce clientes; hubo que devolverlo a mano uno por uno.
         Origin: I-011

🧭 DECISIONS

› D-044  billing runs on Stripe Billing, not on our own invoicing
         Why: el IVA por país y las facturas rectificativas ya resueltos
              valen más que el control de tenerlo en casa.
    ├─ X-021  own invoicing engine                    descartada · Origin D-044
    ├─ X-022  Chargebee                               descartada · Origin D-044
    └─ #62    plan-billing.md                         acta      · 2026-05-19

📌 MEMOS (3)

› M-044  webhooks arrive in UTC and out of order; dedup by event id
› M-051  the customer id lives in tenants.stripe_id, nowhere else
  M-055  the tax rate comes from the customer address, not the card

──── [testing][billing] · 3 notas ──────────────────────────────────────

🔥 INCIDENTS (1 · cerrada)

› I-011  test suite charged 340 EUR to real customers   cerrada 2026-05-14
         → parió R-029

📌 MEMOS (2)

› M-038  the Stripe test clock is the only way to test renewals
  M-047  webhook fixtures live in tests/fixtures/webhooks, not inline

──── [deploy][infra] · 2 notas ─────────────────────────────────────────

📌 MEMOS (1)

› M-060  the Stripe webhook secret rotates per environment; staging
         and prod never share it

❓ OPEN QUESTIONS (1)

› Q-019  do we move to Stripe Tax before the next fiscal year?
         Nació de D-044. Sin respuesta desde el 19 de mayo.

────────────────────────────────────────────────────────────────────────
  Estado completo de una zona:   gitmem search billing
  Con lo archivado:              gitmem search stripe --todo
```

### 2.4 Una nota concreta, por su identificador

`[molde dictado por el propietario, 2026-08-03]` — **faltaba en este documento**, y por eso `search --id` llevaba desde su primer día devolviendo el inventario de la zona en vez de la nota. La especificación §8.1 sí lo pedía —*«Por ID: `D-030` → la nota y su racimo»*— pero sin este molde nadie sabía qué bytes tenía que producir.

```
════════════════════════════════════════════════════════════════════════
  D-030 · decisión · vigente                        2026-08-01 09:12 UTC
════════════════════════════════════════════════════════════════════════

🧭  login with JWT + Google OAuth
    [product] [auth]                                escrita 2026-04-11

    Why          sesiones no escalan multi-tenant; Google evita gestionar
                 passwords propios
    Description  Brainstorm sobre el login. Se valoraron sesiones de
                 servidor, login propio y JWT.
    Keys         token, oauth, sso, signin

────────────────────────────────────────────────────────────────────────
  LO QUE CUELGA DE ELLA

  🚫 X-012  server-side sessions                    descartada · nace de D-030
  🚫 X-013  own password login                      descartada · nace de D-030
  🧭 D-041  session lifetime raised to 30 days      vigente    · nace de D-030
  ⚠️  R-018  no auth deploy on Friday without rollback          nace de D-030

────────────────────────────────────────────────────────────────────────
  La zona entera:   gitmem search auth
```

**Las cinco reglas que fija este molde:**

1. **La cabecera es la nota, no la zona.** Identificador, tipo en castellano y **estado** — `vigente` o `archivada`. Que el estado salga en la primera línea es lo que impide el fallo que este molde viene a corregir: una nota cerrada leyéndose como si siguiera en pie.
2. **Todos los campos del commit, con su nombre y alineados.** `Why`, `Description`, `Keys`, y los que lleve según su tipo (`espera:` en un bloqueante, `Issue:` en un acta). Un campo vacío **no se imprime**: no se enseñan etiquetas huérfanas.
3. **Las dos zonas juntas, en su línea**, y a la derecha la fecha en que se escribió. La de la cabecera es la hora del informe; esta es la de la nota. Son dos fechas distintas y por eso van en sitios distintos.
4. **Debajo, lo que cuelga de ella** — el racimo por punteros `Origin`/`Replaces` `[spec §8.1]`, con el emoji de cada tipo, su estado y de quién nace. **Es lo único que no está en el commit** y hay que reconstruirlo. Si no cuelga nada, el bloque **no se imprime**: un titular vacío es ruido.
5. **El pie ofrece la zona**, no `--todo`. Aquí lo archivado ya sale marcado como tal en el racimo, así que ofrecer «ver lo archivado» sería mentir — y es exactamente lo que hacía la versión rota.

**Un identificador que no existe** no imprime informe: sale por error con `search.py: no existe la nota <ID>`, que es lo que ya hace hoy.

---

## 3. El arranque

`[decisión del propietario, 2026-08-03]` Las etiquetas estructurales van en inglés (`RECUENTOS`→`COUNTS`, `AVISOS`→`CHECKS`, `RESTRICCIONES`→`RESTRICTIONS`, `BLOQUEANTES`→`BLOCKERS`, `espera:`→`awaits:`, `Q sin resolver`→`open questions`, `planes con acta`→`plans with a record`, `I abiertas`→`open incidents`, `IDs sin duplicados`→`no duplicate IDs`, `índices coherentes con git`→`indexes match git`, `reglas coherentes con git`→`rules match git`, `MEMORIA · <proyecto>`→`MEMORY · <proyecto>`); el contenido explicativo (los porqués, las descripciones) se queda en español. Y el Next cambia de forma — corchete `[NEXT]` literal, su emoji `🧭`, y el contexto en prosa corrida, no en puntos: ver §5.

### 3.1 Proyecto con contenido

```
╔══════════════════════════════════════════════════════════════════════╗
║  MEMORY · omawa                                  2026-08-01 09:02 UTC ║
╚══════════════════════════════════════════════════════════════════════╝

[NEXT] ⏩️ implement discussed changes to close-session skill
       Context (cerrado 2026-07-31 19:44 UTC): Revisado el diseño del
       checkpoint: muere el automático, lo hace close-session. Punto de
       inflexión: fuera comodines — toda nota lleva dos zonas reales.
       Decidido de palabra: los planes viven en docs/ como plan-*.md.
       Quedó en el aire el alcance de facturación; hablar antes de
       empezar.

⛔ BLOCKERS (2)

   B-003  [product][auth]   google workspace admin consent still pending
          awaits: el cliente (Marta, IT)
   B-007  [deploy][infra]   the .es staging domain is not bought yet
          awaits: el usuario

⚠️ RESTRICTIONS (5)

   R-004  [testing][auth]     never run the auth test suite against production
          en marzo un test borró 1.200 sesiones reales; cuatro horas de
          reconstrucción desde el backup
   R-011  [api][auth]         refresh tokens are never logged, not even truncated
          un token truncado sigue sirviendo para replay
   R-018  [deploy][auth]      no auth deploy on Friday without a tested rollback
          los dos incidentes de auth del año fueron viernes sin vuelta atrás
   R-022  [database][amianto] never delete a measurement row; mark it void
          las mediciones son prueba legal ante inspección
   R-029  [testing][billing]  no Stripe test hits the live key, ever
          en mayo se cobró 340 € reales a catorce clientes

COUNTS
   open questions ......  6
   plans with a record .  4
   open incidents ......  1

CHECKS
   ⚠️  plan #47: 3 commits sin reflejar en la issue
   ✓  no duplicate IDs (68 notes)
   ✓  indexes match git (68 lines / 68 notes)

El mapa está puesto. Dime por dónde: el Next, una pregunta, una issue,
o lo que traigas.
```

**El aviso de coherencia, cuando hay notas archivadas** `[decisión del propietario, 2026-08-03]` — el molde de arriba solo contempla el caso sin archivadas, donde líneas de índice y notas de git coinciden. Cuando hay notas archivadas, esos dos números divergen por diseño (una nota archivada sale del índice vigente pero sigue contando como nota real en git) y el aviso lo desglosa en vez de dejar dos números que no cuadran sin explicación:

```
✓  no duplicate IDs (612 notes)
✓  indexes match git (587 live + 25 archived / 612 notes)
```

### 3.2 Proyecto recién instalado

```
╔══════════════════════════════════════════════════════════════════════╗
║  MEMORY · monyma                                 2026-08-01 09:02 UTC ║
╚══════════════════════════════════════════════════════════════════════╝

[NEXT] ninguno todavía. No hay ningún cierre de sesión escrito.
       El primero lo escribe close-session al terminar hoy.

⛔ BLOCKERS ......  C E R O
⚠️ RESTRICTIONS ....  C E R O
                      No hay ningún muro puesto. Nada te va a parar
                      porque nadie ha escrito todavía qué rompe qué.

COUNTS
   open questions ......  0
   plans with a record .  0
   open incidents ......  0

CHECKS
   ✓  no duplicate IDs (0 notes)
   ✓  indexes match git (0 lines / 0 notes)
   ·  los ocho índices existen y están vacíos
   ·  zones.json: 9 zonas de trabajo, 0 zonas de producto
      La primera nota va a pedir una zona2 que no existe. Es lo normal:
      se da de alta ahí mismo, a la vista.

Cero no es silencio: es que todavía no se ha escrito nada. La primera
nota se guarda así:

  gitmem note <TIPO> --zones <zona1> <zona2> "titular en inglés" \
    --description "..." --stops <yes|no>
```

---

## 4. Las líneas de índice

**Regla común:** la línea **es** el titular del commit, sin emoji. Un tipo por fichero, orden por identificador, solo vigentes. Sin fecha: nadie la leería del índice, y un campo que nadie lee no existe.

```
── DECISIONS.md ────────────────────────────────────────────────────────
# DECISIONS — índice. Lo escribe el script. No editar. Si diverge, manda git.

[D-030][product][auth] login with JWT + Google OAuth
[D-041][product][auth] session lifetime raised to 30 days
[D-044][api][billing] billing runs on Stripe Billing, not own invoicing
```

```
── MEMOS.md ────────────────────────────────────────────────────────────
[M-021][api][auth] google returns email_verified=false for aliases
[M-044][api][billing] webhooks arrive out of order; dedup by event id
```

```
── RESTRICTIONS.md ─────────────────────────────────────────────────────
[R-004][testing][auth] never run the auth test suite against production
[R-022][database][amianto] never delete a measurement row; mark it void
```

```
── QUESTIONS.md ────────────────────────────────────────────────────────
[Q-007][product][auth] do we support >1 Google Workspace per tenant?
```

```
── INCIDENTS.md ────────────────────────────────────────────────────────
[I-014][testing][auth] seeds wiped the production users table
```

```
── DISCARDED.md ────────────────────────────────────────────────────────
# Permanente: aquí nada se archiva. Existe para que nadie lo re-proponga.

[X-012][product][auth] server-side sessions
[X-022][api][billing] Chargebee
```

```
── BLOCKED.md ──────────────────────────────────────────────────────────
[B-003][product][auth] google workspace admin consent still pending
```

```
── ARCHIVED.md ─────────────────────────────────────────────────────────
# Todo lo retirado, en orden cronológico. El tipo viaja en la línea; al
# pasado se le pregunta por fecha. Lo escribe el script.

2026-06-02  [D-036][product][auth] 🧭 session lifetime is 7 days  →  replaced by D-041
2026-06-20  [I-014][testing][auth] 🔥 session fixation on the tenant switcher  →  closed: arreglado en #58 y con muro puesto (R-018)
2026-07-14  [M-019][api][billing] 📌 Stripe sends webhooks in local time  →  replaced by M-044
2026-07-22  [Q-004][product][billing] ❓ do we need per-seat pricing?  →  promoted to M-051
2026-07-29  [B-002][deploy][infra] ⛔ the CI runner has no docker socket  →  closed: el proveedor lo habilitó el 28
2026-07-30  [Q-009][ui][amianto] ❓ should the report export to XLSX too?  →  promoted to X-030
```

Los tres destinos, literales: `replaced by <ID>` · `closed: <motivo>` · `promoted to <ID>`.

---

## 5. Los commits, uno por tipo

### Decisión — con sus descartes en el mismo acto

```
[D-030][product][auth] 🧭 login with JWT + Google OAuth

Why: sesiones no escalan multi-tenant; Google evita gestionar passwords
 propios y quita de encima el reset y la política de contraseñas.
Keys: token, oauth, sso, signin, credentials
Description: Brainstorm sobre el login con el usuario. Se valoraron
 sesiones de servidor, login propio con contraseña y JWT + OAuth de
 Google. Pesó el multi-tenant (el mismo usuario en varias empresas) y
 que el cliente ya vive en Workspace. Se acepta la deuda de tener que
 resolver la revocación de refresh tokens a mano.
```

```
[X-012][product][auth] 🚫 server-side sessions

Why: no escalan multi-tenant sin un almacén compartido que aún no
 tenemos, y obligaría a Redis solo para esto.
Keys: session, cookie, redis, sticky
Description: Alternativa perdedora de D-030. Se descartó por el coste de
 infraestructura, no por el diseño: si algún día hay Redis por otra
 razón, merece releerse.
Origin: D-030
```

### Memo

```
[M-044][api][billing] 📌 webhooks arrive out of order; dedup by event id

Keys: webhook, idempotency, ordering, duplicate, retry
Description: Stripe reintenta hasta tres días y no garantiza el orden.
 Llegó un invoice.paid antes que su invoice.created. La tabla
 billing_events guarda el event id con índice único y descarta el
 repetido; el orden se reconstruye por created_at del payload, nunca
 por el momento de llegada.
Replaces: M-019
```

### Restricción

```
[R-029][testing][billing] ⚠️ no Stripe test hits the live key, ever

Why: en mayo un test de suscripciones cobró 340 € reales a catorce
 clientes y hubo que devolverlo a mano, uno por uno, con disculpa.
Keys: security, sandbox, apikey, charge, live
Description: Los tests solo pueden ver la clave sk_test_. La clave viva
 no está en ningún .env de desarrollo ni en los secrets del runner de
 tests: vive solo en el entorno de producción. Si un test necesita
 renovaciones, se usa el test clock de Stripe, no la clave real.
Origin: I-011
```

### Pregunta abierta

```
[Q-007][product][auth] ❓ do we support >1 Google Workspace per tenant?

Why: el modelo de datos de invitaciones cambia entero según la respuesta,
 y ya hay dos módulos escritos encima suponiendo que no.
Keys: workspace, tenant, invite, domain, multi
Description: Un cliente tiene dos dominios de Workspace (la matriz y la
 filial) y quiere un solo espacio en la aplicación. Si se soporta, la
 invitación deja de colgar del dominio y pasa a colgar del tenant, con
 tabla de dominios permitidos. Hay que contestarla antes de tocar el
 módulo de equipos.
```

### Descarte

```
[X-022][api][billing] 🚫 Chargebee

Why: el IVA por país lo resuelve igual que Stripe, pero añade un
 proveedor más y su propio webhook que mantener.
Keys: chargebee, subscription, vendor, tax
Description: Alternativa perdedora de D-044. Se probó una cuenta de
 prueba durante dos días: la gestión de rectificativas es mejor, pero no
 compensa un segundo sistema de cobro cuando el pago ya pasa por Stripe.
 No re-proponer sin que cambie una de esas dos cosas.
Origin: D-044
```

### Incidencia

```
[I-014][testing][auth] 🔥 seeds wiped the production users table

Why: se perdieron 1.200 sesiones y 40 minutos de altas; cuatro horas de
 reconstrucción desde el backup de la noche anterior.
Keys: seeds, database, truncate, env, ci
Description: El script de seeds lee la URL de la base de datos de la
 variable DATABASE_URL y hace TRUNCATE antes de sembrar. En el runner de
 CI esa variable venía del entorno del proyecto, que traía producción.
 Causa raíz: el script confía en el entorno para saber contra qué habla.
 Se arregló exigiendo la URL como argumento explícito y abortando si el
 host no es local. Diagnóstico de House, fix en #58.
```

### Bloqueante

```
[B-003][product][auth] ⛔ google workspace admin consent still pending

Awaits: el cliente — Marta, IT de Omawa
Keys: consent, admin, workspace, oauth, scope
Description: El alta masiva de usuarios necesita que un administrador de
 Workspace apruebe el scope admin.directory.user.readonly. Sin eso, el
 flujo de invitación individual funciona pero el importe de plantilla no,
 y la demo del día 12 no puede enseñarlo. Pedido el 24 de julio.
```

### Acta de plan — **es una M, no un tipo propio**

La especificación rechaza expresamente un tipo `P`/`[PLAN]` con identificador
propio (§16): *el plan es documento + issue + acta*. El acta es una **M
normal** que enlaza la decisión con la issue. Coge su M-nnn, su línea en
`MEMOS.md`, su `Origin:` la mete en el racimo de la decisión, y su `Issue:`
dispara la única verificación de GitHub que hace la aduana. Cero maquinaria
nueva y ningún índice de planes — que la especificación también prohíbe.

```
[M-063][product][auth] 📌 login rollout plan

Keys: rollout, milestone, checklist
Description: El plan de ejecución de D-030 vive en docs/plan-login.md;
 la issue #52 aloja el checklist tachable y el DoD. Tres fases: OAuth de
 Google, revocación de refresh, y migración de los usuarios existentes.
Origin: D-030
Issue: #52
```

**Hueco de la especificación que esto destapa:** §3.3 cierra la lista de
campos del cuerpo en seis y **no incluye `Issue:`**, pero §10 lo exige para
el acta y para los commits de trabajo. Hay que declararlo como campo
permitido — su lector ya existe y está declarado (`health.plans_unreflected`).

### Contexto de cierre — sin zonas, sin índice

`[decisión del propietario, 2026-08-03, DEUDA.md PARTE 1, B5]` La forma cambia: corchete `[NEXT]` literal delante del titular, con su emoji (`🧭`, no ya `⏩` — ver el bloque de emojis al principio de este documento); y el cuerpo es un único campo `Context:` en **prosa corrida**, nunca una lista de guiones. El propietario fue explícito sobre qué va en ese campo: *«el resumen de toda la sesión — lo que se habló, lo que se decidió, lo que se rompió, lo que quedó a medias, si me cabreé y por qué»*. No es un acta de lo construido (para eso están los commits): es lo que se habló y no vive en ningún otro sitio.

```
[NEXT] ⏩️ implement discussed changes to close-session skill

Keys: close-session, checkpoint, plan
Context: Revisado el diseño del checkpoint: muere el automático, lo hace
 close-session. Punto de inflexión: fuera comodines — toda nota lleva
 dos zonas reales. Decidido de palabra: los planes viven en docs/ como
 plan-*.md. Quedó en el aire el alcance de facturación; hablar antes de
 empezar.
```

**El molde aprobado por el propietario** de cómo se escribe un contexto en condiciones — el ejemplo real que fija el tamaño y el tono esperados, no una lista de viñetas telegráficas:

```
[NEXT] ⏩️ cerrar el alta masiva de usuarios y desplegar a staging

Context: Sesión larga, de nueve a tres. Se empezó revisando el login con
Google, que llevaba dos semanas parado esperando el consentimiento del
administrador — llegó el viernes y se pudo probar por fin. Funcionó a la
primera con cuentas normales, pero reventó con los alias de empresa:
Google devuelve el correo como no verificado y el alta los rechazaba en
silencio. Se tardó hora y media en dar con ello porque el log no decía
nada; quedó anotado como M-044 para no volver a perder ese tiempo.

De ahí salió una discusión sobre si el borrado de un usuario arrastra sus
mediciones o solo las marca. No se cerró. Tú te inclinabas por marcarlas
—las mediciones son prueba legal ante inspección, que es justo lo que
dice R-022— pero quedó en el aire qué pasa con las que están a medias de
firmar. Hay que hablarlo antes de tocar el modelo de datos, porque toca
tres tablas.

Por la tarde se montó el despliegue a staging y se atascó: el dominio .es
sigue sin comprarse. Se dejó preparado todo lo demás para que el día que
esté sea darle a un botón. Aprovechando el parón se limpió la rama de
facturación, que llevaba once wips, y se cerró la incidencia I-021 del
bucle de login en Safari — era la cookie de sesión, y de ahí nació R-011.

Y te cabreaste, con razón, con el aviso de las claves de catastro: caducan
el 15 y nadie lo había puesto en ningún sitio donde se viera. Por eso
ahora es un bloqueante y no una nota perdida.
```

---

## 6. Decisiones que la especificación no cerraba — todas resueltas por el propietario

1. **Los emojis.** ❓ pregunta · 🚫 descarte (no una papelera: el descarte es permanente) · 🔥 incidencia.
2. **El comando es `gitmem`**, fachada única con subcomandos en inglés sobre los scripts.
3. **La key mal escrita no es un rechazo.** Normalizar es escribir, y un hook no escribe. Se ha redactado como el aviso que sale al guardar bien. Si se quiere rechazo de verdad, la mecánica cambia.
4. **El campo del bloqueante es `Awaits:`** — en inglés y capitalizado como el resto, porque todo nombre que ve una máquina va en inglés. **En la presentación del informe de zona (§2.1/§2.3) se lee «espera:», en español** — sigue así, sin cambios. **En la presentación del arranque (§3.1) se lee «awaits:», en inglés** `[corrección del propietario, 2026-08-03]`: el arranque pasó todas sus etiquetas estructurales a inglés en el mismo lote que `RECUENTOS`→`COUNTS`/`AVISOS`→`CHECKS`, y este campo entró en ese lote. Las dos superficies divergen a propósito: una es informe (texto que se lee), la otra es la lista de etiquetas que el propietario fijó en inglés.
5. **Los muros del arranque salen con una línea de porqué**, no solo el titular. Un titular en inglés a secas no cambia la conducta de nadie a las tres de la mañana.
6. **La línea de índice es el titular literal, sin emoji ni fecha.** El identificador ya viaja dentro. El emoji solo aparece en el archivo, que es el único fichero que mezcla tipos.
8. **El emoji va DESPUÉS de los corchetes, no delante** (corrección del propietario, 2026-08-02): `[D-030][product][auth] 🧭 login with JWT...`. Todo titular de commit lleva su emoji, sin excepción. Las dos formas sin corchetes —el `🚧` del wip y, hasta el 2026-08-03, el Next— lo llevan delante porque no tienen corchetes que los precedan. El Next dejó de ser una de esas dos formas ese día: ahora lleva su propio corchete literal `[NEXT]` delante del emoji (ver punto 10 y §5). En la línea del archivo se aplica igual, después de los corchetes y detrás de la fecha.
9. **`/remember` está libre en Claude Code** — comprobado por el propietario (2026-08-02). El comando de reglas puede llamarse así.
10. **Corrección del bloque de emojis (2026-08-02):** el `⏩` estaba etiquetado como «contexto/avance». Es un error — el `⏩` marca el **Next** (§9 de la especificación: «el titular ES el Next, obligatorio, con su emoji»); el contexto es el cuerpo, sin emoji propio. De esa etiqueta salió mal el nombre de la clave `"context"` en el código. **Corregido de nuevo el 2026-08-03** `[decisión del propietario, DEUDA.md PARTE 1, B5]`: el marcador del Next pasa de `⏩` a `🧭`, y el titular lleva delante el corchete literal `[NEXT]` (`[NEXT] ⏩️ <titular>`) — ver el bloque de emojis al principio de este documento y §5.
7. **El campo de ficheros tocados NO EXISTE en el v2.** Se retiró entero: git ya guarda el diff y no se puede mentir sin él. La vista por fichero usa `git log -- <ruta>` directamente. Las notas tampoco llevan co-autor. Las notas de memoria no tocan ficheros de aplicación; la línea de índice viaja en el mismo commit pero no se declara, para no convertir ese campo en ruido en las siete plantillas.
11. **`wip` tiene productor desde el 2026-08-03** `[decisión del propietario]`: `validator.is_wip()` ya sabía reconocer y eximir el marcador de checkpoint, pero ningún comando lo escribía — una puerta abierta sin llave. `bin/memory/wip.py` (subcomando `gitmem wip`) lo cierra: antepone `🚧` al mensaje y reutiliza `notes.write_work()` tal cual.

**Y sí protege la rama principal, igual que `gitmem work`** `[decisión del propietario, 2026-08-03 — «el checkpoint protege la rama principal, con la misma protección que work.py»; ver `PIEZAS.md` §10.1 punto 4]`. La mecánica no está duplicada: vive en `lib/memory/repo_guard.py`, que los dos scripts importan.

> **Este punto decía exactamente lo contrario hasta hoy** `[corregido 2026-08-04]`: *«sin proteger la rama principal (a diferencia de `gitmem work`) — no se pidió esa protección»*. Era cierto cuando se escribió y **dejó de serlo el mismo día**, cuando el propietario la pidió expresamente. El código lleva la protección desde entonces (`bin/memory/wip.py`, líneas 109-113).
>
> **Se anota en vez de borrarse porque es el fallo más peligroso que puede tener este documento:** de aquí se derivan las piezas, no al revés. Alguien que leyera solo esta línea para saber qué hace `wip` concluiría que la protección sobra —«no se pidió»— y **la quitaría del código**, dejando que un checkpoint aterrice en `main`. Un documento que contradice una decisión del propietario no es una errata de redacción: es una instrucción para deshacerla.

---

## 7. El saludo de Claude tras leer el arranque

`[decisión del propietario, 2026-08-03]` — **faltaba en este documento**. El arranque (§3) es un documento mecánico que un script escribe; este molde es distinto: es lo que **Claude** dice al usuario justo después de leerlo entero, en su primer mensaje. El propietario lo cortó en seco cuando se probó como un resumen de tres líneas: *«no me puede ser tan breve. Con seis preguntas abiertas, yo no me entero de nada. Esto es un fallo gordísimo»* `[spec §8.3]`. No es un resumen: es el mapa completo, con un emoji por sección para distinguir las partes de un vistazo, y termina ofreciendo por dónde empezar — nunca decide él por el usuario.

Ejemplo, sobre el arranque de omawa (§3.1): el Next, los bloqueantes, el conteo de preguntas y el plan #47 salen tal cual del arranque; el detalle de **cuáles** preguntas bloquean sale de lo que ya se sabe de la zona `auth` (§2.1) — el arranque solo da el número, nombrar cuáles es trabajo de Claude, no del script:

```
🧭 Hoy toca: implementar los cambios acordados en la skill de cierre de
   sesión. Ayer quedó revisado el diseño del checkpoint (muere el
   automático, lo hace close-session) y decidido que toda nota lleva dos
   zonas reales, sin comodines. Quedó en el aire el alcance de
   facturación — hablarlo antes de tocarlo.

⛔ Bloqueantes (2):
   B-003 — el consentimiento de administrador de Google Workspace sigue
   sin llegar. Pedido el 24 de julio, todavía sin fecha de respuesta.
   B-007 — el dominio .es de staging sigue sin comprarse. Sin fecha.

❓ Preguntas abiertas (6, dos bloquean trabajo ya empezado):
   Q-007 — ¿se admite más de un Google Workspace por tenant? Bloquea el
   modelo de datos de invitaciones: ahí no se puede avanzar sin
   respuesta.
   Q-015 — ¿son aceptables los 30 días de sesión para la auditoría?
   Nació de D-041 el 2 de junio y sigue sin respuesta.
   Las otras cuatro no tienen trabajo esperando por ellas todavía.

🔥 Incidencias y planes:
   I-021 sigue abierta desde el 28 de julio (bucle de login en Safari).
   El plan #47 lleva 3 commits sin reflejar todavía en su issue.

⚠️ Muros de hoy:
   De los cinco vigentes, ninguno toca lo de hoy — la skill de cierre de
   sesión no pasa por auth, billing ni deploy. Siguen los cinco en pie
   para cuando sí toque.

¿Por dónde empezamos: el Next, alguna de las dos preguntas que bloquean,
el plan #47, o algo que traigas tú?
```

**Lo que fija este molde:** un emoji por sección (los mismos del mapa de arriba, sin inventar ninguno nuevo) — 🧭 lo de hoy con lo de ayer, ⛔ bloqueantes con fecha si la tienen, ❓ preguntas abiertas nombrando cuáles bloquean trabajo ya empezado (nunca solo un número), 🔥 incidencias abiertas y planes con commits sin reflejar, ⚠️ muros que de verdad tocan lo de hoy — y si ninguno toca, se dice así, en vez de forzar uno. Cierra siempre ofreciendo por dónde seguir; el usuario decide el rumbo, el saludo solo pone el mapa completo.

---

## 8. Los comandos de git que pueden borrar trabajo

`[decisión del propietario, 2026-08-03]` — **faltaban en este documento**; quedan fijados aquí. Quién los intercepta y los relanza sigue sin construirse (`DEUDA.md`, punto 8 de «lo decidido que falta por construir») — eso es implementación, no texto, y no es lo que este documento fija. **La regla, y es una sola:** `reset`, `restore`, `checkout <fichero>`, `clean`, `stash`, `branch -D` y `push --force` **no se bloquean — obligan a preguntarle a él**, enseñando exactamente qué desaparece. Son dos textos distintos, y la confirmación es por duplicado: dos síes, no uno.

### 8.1 El texto que le llega a Claude

No es una nota de rechazo — nada se rechaza. Es un aviso que le dice a Claude que **no puede decidir por su cuenta**, con el texto ya redactado para trasladar al usuario y el comando exacto con el que relanzar si contesta que sí.

```
⛔ ESTO NO LO CONFIRMAS TÚ — `git reset --hard HEAD~1` puede borrar trabajo sin guardar

No puedes confirmarlo tú: pregúntale al usuario y espera su respuesta.
Enséñale esto, tal cual — no lo resumas:

  [ver 8.2]

Si contesta que sí, antes de ejecutar repítele en una línea qué se
pierde — dos síes, no uno — y entonces relanza con:

  git reset --hard HEAD~1
```

### 8.2 El texto que Claude le enseña al usuario

Qué se pierde exactamente —ficheros y cuántas líneas sin guardar, cuántos commits desaparecen y cuál era el último—, cómo evitarlo, y la pregunta:

```
⚠️  git reset --hard HEAD~1 va a borrar, sin guardarlo en ningún sitio:

    3 ficheros modificados, 47 líneas sin commitear:
      lib/memory/notes.py · tests/memory/test_notes.py · DEUDA.md

    1 commit que no vuelve: a3f9c21 "wip: candado de índices"

  Para no perderlo:
    git stash                    guarda los ficheros sin commitear
    git commit -m "wip: ..."     o commitéalos antes del reset

  ¿Confirmas el reset igualmente? (sí/no)
```

### 8.3 Cuando las dos copias han cambiado por separado — `push --force`

*«Para subir y bajar cuando las dos copias han cambiado por separado, el aviso lleva además cuántos commits hay a cada lado, porque esos son los únicos que me preocupan»* — el propietario, 2026-08-03. Mismo molde que 8.2, con esta cuenta añadida:

```
⚠️  git push --force origin feat/memoria-v2 va a sustituir el remoto por tu rama local:

    tu rama local ..... 5 commits que el remoto no tiene
    el remoto .........  2 commits que desaparecen sin dejar rastro
                          el último era 9c21a3f "fix: date parsing retry"

  Para no perderlos:
    git pull --rebase origin feat/memoria-v2   trae los dos, luego push normal

  ¿Confirmas el push --force igualmente? (sí/no)
```

### 8.4 La confirmación es por duplicado — dos síes, no uno

Tras el primer sí, y antes de ejecutar nada, se repite en una sola línea qué se va a perder:

```
Confirmado. Antes de ejecutar: esto borra 47 líneas sin commitear en 3
ficheros y el commit a3f9c21. ¿Sigo? (sí/no)
```

Solo con el segundo sí se relanza el comando exacto que dio 8.1.
