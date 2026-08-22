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
[remember][user] 🧠 cuando lanzo varios agentes a la vez: no me informes uno por uno, dame el total cuando acaben todos
[remember][user] 🧠 las fichas de los agentes y las skills son agnosticas: viajan a todos mis proyectos, nunca las juzgues contra el proyecto en el que estas
[remember][claude] 🧠 en una tuberia de agentes no narres cada vuelta: silencio real entre hitos, solo hablo para un resultado que decide, una pregunta, o la entrega final
[remember][user] 🧠 no me expliques nada con analogias ni metaforas, no las entiendo: dilo directo y con un ejemplo concreto del proyecto
