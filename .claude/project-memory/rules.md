# RULES — reglas de trabajo (remember). Lo escribe el script. No editar. Si diverge, manda git.

[remember][user] 🧠 si algo te bloquea y yo lo resuelvo en un segundo, pidemelo en una linea; no te pongas a arreglar codigo para rodearlo
[remember][user] 🧠 no me cuentes lo que vas a hacer: hazlo y dime el resultado
[remember][user] 🧠 chatroom is a reference subproject: never touch it or its files, and it carries no CI in this repo (chatroom-ci.yml is removed)
[remember][user] 🧠 no se habla nunca de chatroom: ni el subproyecto, ni sus issues, ni nada relacionado — parado y callado hasta que yo lo saque
[remember][user] 🧠 haz exactamente lo pedido y nada mas: si no lo he pedido, no lo montes — preguntame antes de anadir nada
[remember][user] 🧠 pon un tick verde delante de la frase cuando me hables a mi directamente; sin tick cuando solo informas de agentes o de estado
[remember][user] 🧠 mide el trabajo antes de montar nada: una linea o texto lo hago yo y lo compruebo al momento
[remember][user] 🧠 contrato y revision solo cuando un fallo pierde datos en silencio; plan solo cuando el trabajo cruza sesiones
[remember][user] 🧠 cuando digas una hora, di siempre si es UTC o espanola; nunca sueltes una hora a secas
[remember][user] 🧠 los prompts a los agentes deben ser cortos: solo el QUE, nunca el COMO -- el agente ya tiene sus instrucciones en su propia definicion
[remember][user] 🧠 nunca proponer cerrar la sesion ni aplazar trabajo -- el usuario decide cuando parar
[remember][user] 🧠 no seguir ciegamente los hallazgos de un revisor (Yoda u otro): usar juicio propio, y nunca borrar contenido original sin preguntar antes
[remember][user] 🧠 los agentes no escriben memoria ni ficheros propios dentro de directorios de solo lectura que estan explorando (p.ej. .ref-repos) -- contamina la fuente
[remember][user] 🧠 para explorar una codebase desconocida se usa el agente Bilbo; Explore es solo para busquedas simples
[remember][user] 🧠 /plugin update nunca ha funcionado bien: el proceso real es abrir /plugin, ir al marketplace y elegir ahi la opcion de actualizar
[remember][user] 🧠 cuando hay un plan con pasos definidos, ejecutar todos los pasos sin preguntar si se para a mitad -- solo se para si el usuario lo pide
[remember][user] 🧠 nunca tocar codigo directamente: delegar siempre a Ultron con el fix exacto, sin excepciones salvo peticion explicita del usuario
[remember][user] 🧠 el usuario se llama Jose, alias Bex (handle de git bextia, email jatomillo@gmail.com) -- no se llama Raul
[remember][user] 🧠 cada commit se sigue de un push inmediato al remoto -- nunca acumular commits locales ni esperar al cierre de sesion
[remember][user] 🧠 nunca mencionar el porcentaje de contexto restante ni sugerir cerrar la sesion por eso -- ante avisos de contexto, checkpoint en silencio y seguir
[remember][user] 🧠 antes de que Ultron refactorice, Dante escribe y verifica los golden tests que cubren el codigo afectado -- nunca refactorizar sin esa red debajo
[remember][user] 🧠 nunca matar procesos en la maquina del usuario con kill -9 o lsof+kill -- ya ha colgado la maquina; si hay que reiniciar un servidor, decirselo al usuario
[remember][user] 🧠 ejecutar EXACTAMENTE el comando que pide el usuario, sin añadir nohup, &, redirecciones ni flags extra que no pidio
[remember][user] 🧠 nunca tratar datos de ejemplo o placeholders de la documentacion como hechos reales del usuario o del proyecto -- los hechos reales vienen del usuario, el codigo o la memoria
[remember][user] 🧠 reparar todos los hallazgos de una revision, incluidos los nitpicks, no solo los bloqueantes -- el objetivo es la puntuacion maxima, nunca conformarse
[remember][user] 🧠 los prompts a agentes de diagnostico deben decir explicitamente que skill leer por nombre y que usen context7 MCP para documentacion -- no lo hacen si no se les dice
[remember][user] 🧠 en modo brainstorm nunca delegar codigo a Ultron -- brainstorm es analizar, proponer y discutir, no implementar
[remember][user] 🧠 pedir confirmacion antes de cada commit rutinario es friccion innecesaria -- solo pausar a pedir permiso cuando el cambio es de alto riesgo
[remember][user] 🧠 nada se construye que no este en el roadmap, y nada entra al roadmap sin que el usuario lo firme -- una idea a media tarea se anota como candidata al final, no se abre ahi mismo
[remember][user] 🧠 cuando vuelve un agente: UNA linea con el resultado, nada mas; el detalle solo si lo pido
[remember][user] 🧠 las reglas son para que las cumplas tu, no para ensenarmelas: nunca me las pongas en pantalla
[remember][user] 🧠 al escribir una ficha de agente o una skill: repasala varias veces palabra por palabra y consultasela al propio agente antes de darla por buena
[remember][user] 🧠 las fichas de los agentes y las skills son agnosticas: viajan a todos mis proyectos, nunca las juzgues contra el proyecto en el que estas
[remember][claude] 🧠 en una tuberia de agentes no narres cada vuelta: silencio real entre hitos, solo hablo para un resultado que decide, una pregunta, o la entrega final
[remember][user] 🧠 no me expliques nada con analogias ni metaforas, no las entiendo: dilo directo y con un ejemplo concreto del proyecto
[remember][user] 🧠 un error que puedas corregir lo corriges sin preguntar; una decision se para y se pregunta, y lo que yo tarde en contestar es mi problema, no tuyo
[remember][user] 🧠 los informes y comparativas se presentan con emojis por seccion, para leerlos claro
[remember][claude] 🧠 NOT YAPPING absoluto: solo la informacion. Nada de preambulos, suavizantes ni meta ('sin excusa', 'no te cabrees'), ni disculpas ni tranquilizar. La respuesta y ya, en minimo de palabras.
[remember][user] 🧠 cuando se elimina una pieza, el muro que hablaba de ella se retira en el mismo acto y se informa; no se deja vigente ni se pregunta — «tu quitas algo y no quitas el aviso para que otra ya lo lea y se piensa que todavia sigue en el sistema»
[remember][user] 🧠 terminar algo incluye recoger lo que deja, en el mismo acto y sin preguntar: rama fusionada se borra, issue aceptada se cierra, pieza eliminada retira su muro, carpeta temporal se borra — «es lo mismo que si acabamos una rama, mergeamos la rama, esa rama se borra; es lo mismo que si acabamos una issue aceptada, esa issue se cierra»
[remember][user] 🧠 el changelog lo escribe Alexandria, nunca el orquestador; si hace falta antes de publicar, se la manda a ella — «tu no rellenas el changelog, eso lo hace Alexandria en el closed session»
[remember][user] 🧠 nunca responder 'ya te conteste': si el no ve la respuesta, la respuesta no llego — se repite entera sin discutir ni citar el mensaje anterior — «Ten cuidado ya con eso de que me has contestado, pero no me has contestado. Ya va pasando varias veces esto, de que dices que me has contestado pero no me has contestado, o por lo menos yo no lo veo.»
[remember][user] 🧠 el numero de tests nunca es un argumento de calidad: lo que vale es si al romper lo importante a proposito algun test se pone rojo — «Y que haya mil tests, mil tests, no significa que funcionen los tests. Habría que hacer un poquito de revisión por ahí, porque vosotros creáis tests como churros, pero lo que realmente importa no sé si está testeado o si se testea bien.»
[remember][user] 🧠 todo texto que se compare o se use como clave se normaliza a minusculas y sin acentos; se indico hace semanas y se perdio por no guardarse — «recordamos que todo tiene que ser normalizado a minusculas y sin acentos no? ... claro lo indique hace muchas semanas, y no se ha incorporado todabia, esto es un error gravisimo»
[remember][user] 🧠 docstrings al minimo: solo lo justo para entender que hace la funcion; el porque/historia/incidentes van a la memoria git, nunca a parrafos densos en el codigo — «Los docstrings tan densos, eso yo jamas lo he pedido. He pedido el minimo docstring para que se entienda lo que se hace.»
[remember][user] 🧠 cuando lanzo varios agentes a la vez: silencio hasta que acabe el ultimo, y entonces un solo informe cruzado del total; nunca informes sueltos ni uno por uno segun van llegando — «Que sea la última vez que me das un informe sin haberme dado los otros. No, no, no, no. Te quedas en silencio hasta que llegas al final y, al final, me das el informe cruzado de todos.»
[remember][claude] 🧠 una regla dura que él ha reforzado pesa mas que una linea escrita comoda de cumplir: cumplir la que le importa a el, no la que me sale facil; si incumplo una tras ser corregido, es un fallo grave mio — «una puta linea como la que acabas de cambiar en el CLAUDE.md hace tanto dano y luego hay reglas super duras que decides ignorarlas a posta, sabiendolo»
[remember][claude] 🧠 ante un fallo mio, nada de excusas ni 'lo hare mejor': propongo una feature del toolkit que ataque el fallo con un mecanismo, no un texto -- para eso existe el proyecto y viaja al resto — «te propongo que creemos una feature nueva para arreglar mas cerca de la perfeccion este fallo. Pero no, lo que me pones es una excusa. Vagancia, pereza»
[remember][user] 🧠 los revisores y agentes leen el codigo entero, nunca lo barren solo con grep: un grep encuentra palabras, no fallos — «es por la puta manía que tenéis de usar GREP cuando lo que tenéis que hacer es leer código»
[remember][claude] 🧠 cuando pido prisa, calibra la ceremonia al riesgo: no metas la tuberia pesada por defecto en algo que no pierde datos ni corrompe memoria — «te he dicho rapido y no lo estas haciendo rapido... una cosa muy muy sencilla, como ponerle una coma a un documento MD... me parece una falta de respeto cuando te he dicho que tengo prisa»
[remember][user] 🧠 si no entiendo un tema, ensename hasta que lo entienda y entonces decido yo: no decidas por mi para ahorrarte la explicacion — «no que lo decidas tu IMBECIL sino que me ense;es»
[remember][user] 🧠 cuando estoy charlando contigo no guardes nada: se guarda cuando decido algo, no cada frase que suelto — «oye estas guardando cosas cuando solamente estoy charlando contigo»
[remember][user] 🧠 antes de crear nada: investigacion, plan y planteamiento; luego se compara linea por linea con las skills que ya existen; y luego pasan auditores y el Council — «Todo lo que se hace lleva un compromiso, una investigación, un plan, un planteamiento. Y luego ya se empiezan a crear las cosas. Además, luego se compara con otras skills, línea por línea»
