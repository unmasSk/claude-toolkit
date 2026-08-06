"""Los tres ajustes del proyecto -- contrato en docs/memoria-v2/PIEZAS.md Sec.6.3.

Fichero aparte a proposito, y no una cuarta clave dentro de zones.json
[decision del propietario, ARQUITECTURA.md Sec.6bis]: las zonas las
escribe el sistema a menudo; esto lo pone una persona una vez. Juntarlos
es como una escritura automatica acaba pisando un ajuste hecho a mano.

Los tres valores por defecto NO son comodidad, son seguridad -- es todo
el contenido de esta pieza:

- ``customs_enabled`` pasa de encenderse a apagarse a mano [decision
  del propietario, DEUDA.md B19 punto 2, 2026-08-03]: sin fichero, o
  con fichero que no menciona la clave, ``load()`` devuelve ``None`` --
  "sin ajuste explicito", ni encendida ni apagada. Quien decide el
  valor efectivo en ese caso NO es esta pieza -- es ``hooks/customs.py``,
  el unico consumidor, que enciende la aduana sola en cuanto el
  proyecto tiene su primera nota. Esta pieza solo carga un fichero;
  mirar si hay notas es responsabilidad de quien la enciende, no de
  quien carga tres ajustes. Si el fichero SI trae la clave (``true`` o
  ``false`` explicitos), ese valor manda siempre y ``load()`` lo
  devuelve tal cual -- la bandera se conserva justo para poder apagarla
  a mano si alguna vez estorba.
- Sin fichero, ``repo_type`` cae del lado protegido (``"gitflow"``),
  para que un commit directo a un repositorio que despliega solo no
  pase inadvertido.
- Un fichero corrupto FALLA EN ALTO, nunca devuelve los valores por
  defecto en silencio: si ``load`` se tragara el error de parseo, el
  sintoma seria identico al caso "no hay fichero todavia" -- una aduana
  apagada sin que nadie sepa que lo esta es un vigilante que no vigila
  y encima no lo dice. El mensaje de la excepcion nombra siempre el
  fichero que fallo, mismo principio que ``gitcmd.run`` fija para el
  error real de git [PIEZAS.md Sec.7.1].

  Esta garantia es del ``load`` de ESTA pieza -- se cumple para quien lo
  llama a el (hoy, ``customs.py``, que efectivamente falla en alto).
  ``hooks/stop-dod-gate.py`` lee el MISMO fichero (``test_command``) pero
  NO pasa por este ``load()`` -- tiene su propio parseo directo, porque
  su contrato es fail-open (nunca debe bloquear el cierre de sesion por
  un problema de infraestructura suyo, ver docstring de ese hook). Para
  ese segundo lector la garantia de "nunca en silencio" se sostiene por
  otro medio (un aviso visible por stderr, no una excepcion que falla en
  alto) -- corregido 2026-08-06, antes se tragaba el error igual que el
  caso "no configurado" y los dos eran indistinguibles. Quien añada un
  tercer lector de este fichero fuera de esta pieza debe decidir el
  mismo dilema (fallar en alto vs avisar y seguir) explicitamente, no
  asumir que hereda esta garantia gratis.

SOLO DATOS Y SU CARGA. Cero validacion de contenido de negocio: un
valor de tipo equivocado dentro de un JSON por lo demas valido (por
ejemplo ``"customs_enabled": "si"``) es tambien un fichero corrupto en
el sentido de esta pieza -- una cadena no vacia evaluaria a verdadero
en el consumidor y encenderia la aduana sin que nadie lo haya decidido,
que es exactamente el fallo que el contrato prohibe.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Los tres ajustes, con sus valores fail-closed por defecto.

    ``customs_enabled`` en ``None`` significa "sin ajuste explicito en
    el fichero" -- no "apagada". El valor efectivo en ese caso lo decide
    ``hooks/customs.py`` [DEUDA.md B19 punto 2]: esta pieza no lo
    resuelve.
    """

    customs_enabled: bool | None = None  # None = sin ajuste explicito
    repo_type: str = "gitflow"         # fail-closed: main protegido si no se declara
    test_command: str | None = None


def load(path: Path) -> Config:
    """Carga ``config.json``. Sin fichero, defaults fail-closed. Corrupto, lanza.

    Quien la llama [PIEZAS.md Sec.6.3]: ``hooks/customs.py`` lee
    ``customs_enabled`` · ``bin/memory/work.py`` lee ``repo_type`` antes
    de commitear, para saber si ``main`` esta protegido · el protocolo
    de cierre de sesion lee ``test_command``.
    """
    if not path.exists():
        return Config()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"config.py: {path.name} esta corrupto y no se pudo interpretar "
            f"como JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- se esperaba un objeto "
            f"JSON (diccionario) y llego {type(data).__name__}"
        )

    customs_enabled = data.get("customs_enabled")
    if customs_enabled is not None and not isinstance(customs_enabled, bool):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- 'customs_enabled' "
            f"debe ser booleano y llego {type(customs_enabled).__name__}"
        )

    repo_type = data.get("repo_type", "gitflow")
    if not isinstance(repo_type, str):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- 'repo_type' debe "
            f"ser texto y llego {type(repo_type).__name__}"
        )

    test_command = data.get("test_command")
    if test_command is not None and not isinstance(test_command, str):
        raise ValueError(
            f"config.py: {path.name} esta corrupto -- 'test_command' debe "
            f"ser texto o null y llego {type(test_command).__name__}"
        )

    return Config(
        customs_enabled=customs_enabled,
        repo_type=repo_type,
        test_command=test_command,
    )
